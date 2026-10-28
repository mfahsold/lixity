"""Model-independent, source-bound speech direction and Qwen plan compilation.

Directions are author choices, never inferred from prose or diagnostic scores.
Offsets address Unicode code points in the advertised spoken projection.
"""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass
from itertools import pairwise
from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .config import read_explicit_project_config
from .io import FileUtils
from .markdown_parser import counting_inline_text
from .pipeline import document_paragraph_texts, paragraph_identity, resolve_document_config
from .research.repository import Repository, ResearchConflictError
from .speech_controls import apply_pronunciation, combine_delivery, speech_control_support
from .speech_profiles import AudioProfile, parse_audio_settings

POLICY = 'lixity-speech-plan/1'
MAX_BYTES = 4 * 1024 * 1024


class _Strict(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True, allow_inf_nan=False, hide_input_in_errors=True)


class PassageAnchor(_Strict):
    start_line: Annotated[int, Field(ge=1)]
    end_line: Annotated[int, Field(ge=1)]
    paragraph_sha256: Annotated[str, Field(pattern=r'^[0-9a-f]{64}$')]


class Direction(_Strict):
    anchor: PassageAnchor
    start: Annotated[int, Field(ge=0)] = 0
    end: Annotated[int, Field(ge=1)] | None = None
    profile_id: Annotated[str, Field(min_length=1, max_length=64)] | None = None
    instructions: Annotated[str, Field(max_length=2000)] = ''
    pause_before: Annotated[float, Field(ge=0, le=10)] = 0.0
    pause_after: Annotated[float, Field(ge=0, le=10)] | None = None

    @field_validator('instructions')
    @classmethod
    def normalized_instructions(cls, value: str) -> str:
        return AudioProfile(instructions=value).instructions


class _Stored(_Strict):
    source_path: str
    direction: Direction


class _State(_Strict):
    schema_version: Literal['lixity-audio-directions/1'] = 'lixity-audio-directions/1'
    entries: Annotated[list[_Stored], Field(max_length=10000)] = Field(default_factory=list)


@dataclass(frozen=True)
class SpeechSegment:
    text: str
    profile: AudioProfile
    pause_before: float = 0.0
    pause_after: float = 0.0
    anchor: dict[str, Any] | None = None


def _digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                    separators=(',', ':'), default=str).encode()).hexdigest()


def direction_id(direction: Direction) -> str:
    return _digest([direction.anchor.model_dump(), direction.start, direction.end])


def spoken_projection(text: str, *, skip_markers: bool = True) -> str:
    if skip_markers:
        text = re.sub(r'\[(TODO|PRÜFEN|ACHTUNG|SACHCHECK)[^\]]*\]', '', text, flags=re.IGNORECASE)
    return counting_inline_text(text).strip()


def speech_passages(text: str, language: str, project_config: Mapping[str, Any] | None = None,
                    *, skip_markers: bool = True) -> list[dict[str, Any]]:
    config, _resolved = resolve_document_config(text, language, project_config=project_config)
    return [{'anchor': paragraph_identity(p), 'chapter': p.chapter_num,
             'text': spoken_projection(p.text, skip_markers=skip_markers)}
            for p in document_paragraph_texts(text, config)]


def _boundary(text: str, index: int) -> bool:
    # Do not cut a combining sequence, variation selector or joined emoji.
    return index in (0, len(text)) or not (unicodedata.category(text[index]).startswith('M') or
            text[index] == '\u200d' or text[index - 1] == '\u200d')


def _ranges(passages: list[dict[str, Any]], directions: list[Direction]) -> dict[str, list[Direction]]:
    lookup = {_digest(p['anchor']): p for p in passages}
    result: dict[str, list[Direction]] = defaultdict(list)
    for d in directions:
        key = _digest(d.anchor.model_dump())
        p = lookup.get(key)
        if p is None:
            raise ValueError('A directed passage changed or is stale; review its saved direction')
        content = p['text']
        end = d.end if d.end is not None else len(content)
        if not d.start < end <= len(content) or not _boundary(content, d.start) or not _boundary(content, end):
            raise ValueError('Direction range must select complete Unicode characters in the spoken passage')
        if not content[d.start:end].strip():
            raise ValueError('Direction range must contain spoken text')
        result[key].append(d)
    for rows in result.values():
        rows.sort(key=lambda d: d.start)
        for a, b in pairwise(rows):
            if b.start < (a.end if a.end is not None else len(lookup[_digest(a.anchor.model_dump())]['text'])):
                raise ValueError('Speech direction ranges overlap; choose one direction for each passage')
    return dict(result)


def build_speech_plan(text: str, profile: AudioProfile, *, directions: list[Direction] | None = None,
                      profiles: Mapping[str, AudioProfile] | None = None, chapter: int | str | None = None,
                      project_config: Mapping[str, Any] | None = None,
                      skip_markers: bool = True) -> list[SpeechSegment]:
    """Compile explicit ranges to effective per-segment controls, never spoken tags."""
    from .speech import _speech_segments, extract_audio_cues
    passages = speech_passages(text, profile.language, project_config, skip_markers=skip_markers)
    ranges = _ranges(passages, directions or [])
    if directions and not skip_markers:
        authored = {_digest(p['anchor']): p['text'] for p in speech_passages(text, profile.language, project_config)}
        if any(p['text'] != authored.get(_digest(p['anchor'])) for p in passages if _digest(p['anchor']) in ranges):
            raise ValueError('Saved direction uses marker-stripped offsets; use --no-direction with --keep-markers')
    cues = extract_audio_cues(text, profile.language, chapter, skip_markers, project_config, segment=False)
    projections = {_digest(p['anchor']): p['text'] for p in passages}
    plan = []
    matched: set[str] = set()
    for cue in cues:
        anchor = cue.anchor
        key = _digest(anchor) if anchor else ''
        if key in projections:
            cue.text = projections[key]
        records = ranges.get(key, [])
        if records:
            matched.add(key)
        default_pause = profile.scene_pause if cue.kind == 'scene_break' else profile.paragraph_pause if cue.kind != 'heading' and cue.pause_after else cue.pause_after
        cursor = 0
        chunks: list[tuple[str, AudioProfile, float, float | None]] = []
        for d in records:
            if cursor < d.start:
                chunks.append((cue.text[cursor:d.start], profile, 0.0, None))
            selected = (profiles or {}).get(d.profile_id) if d.profile_id else profile
            if selected is None:
                raise ValueError('A saved direction references an unavailable voice profile')
            instructions = combine_delivery(selected.instructions, d.instructions)
            selected = AudioProfile.model_validate({**selected.model_dump(), 'instructions': instructions})
            end = d.end if d.end is not None else len(cue.text)
            chunks.append((cue.text[d.start:end], selected, d.pause_before, d.pause_after))
            cursor = end
        if cursor < len(cue.text) or not chunks:
            chunks.append((cue.text[cursor:], profile, 0.0, None))
        for index, (raw_content, effective, before, after) in enumerate(chunks):
            content = raw_content
            content = apply_pronunciation(content, effective.pronunciations)
            pieces = _speech_segments(content, effective.language) or ['']
            for n, piece in enumerate(pieces):
                pause = after if after is not None else (effective.paragraph_pause if cue.kind not in ('heading', 'scene_break') else default_pause) if index == len(chunks)-1 else 0.0
                plan.append(SpeechSegment(piece, effective, before if n == 0 else 0.0,
                                          pause if n == len(pieces)-1 else 0.0, anchor))
    # A valid anchor must never silently disappear due to a projection mismatch.
    selected_keys = {_digest(p['anchor']) for p in passages if chapter is None or p['chapter'] in {cue.chapter_num for cue in cues}}
    if (set(ranges) & selected_keys) - matched:
        raise ValueError('A directed passage cannot be matched to the spoken projection')
    return plan


def plan_json(plan: list[SpeechSegment]) -> dict[str, Any]:
    support = speech_control_support('qwen3')
    return {'schema_version': POLICY, 'controls': {'instructions': support.direction.replace('_', '-'),
            'pauses': support.pauses.replace('_', '-'), 'phonemes': support.phonemes, 'ssml': support.ssml},
            'segments': [{'text': row.text, 'profile': row.profile.model_dump(),
                          'pause_before': row.pause_before, 'pause_after': row.pause_after,
                          'anchor': row.anchor} for row in plan]}


def _read(root: Path) -> tuple[_State, str]:
    repo = Repository(root)
    try:
        raw = repo.read(repo.safe(root / '.lixity/audio-directions.json'), maximum=MAX_BYTES)
    except FileNotFoundError:
        return _State(), hashlib.sha256(b'').hexdigest()
    state = _State.model_validate_json(raw)
    keys = [(e.source_path, direction_id(e.direction)) for e in state.entries]
    if len(keys) != len(set(keys)):
        raise ValueError('Speech direction state repeats a range')
    return state, hashlib.sha256(raw).hexdigest()


def direction_snapshot(project: str | Path) -> str:
    """Read the bounded ledger identity without parsing manuscript paragraphs."""
    return _read(Path(project).resolve())[1]


def check_profile_removals(project: str | Path, audio: object) -> None:
    """Reject removal of profiles still referenced by any retained direction.

    Call under the project's repository writer lock, immediately before committing
    the prepared project settings. This includes stale and other-source entries.
    """
    root = Path(project).resolve()
    previous = parse_audio_settings(read_explicit_project_config(root).get('audio')).profiles
    replacement = parse_audio_settings(audio).profiles
    removed = previous.keys() - replacement.keys()
    if removed:
        state, _ = _read(root)
        if any(entry.direction.profile_id in removed for entry in state.entries):
            raise ValueError('A removed voice profile is used by saved speech direction; '
                             'review or remove that direction before deleting the profile')


def direction_state(project: str | Path, source: str | Path, *, language: str = 'en') -> dict[str, Any]:
    root = Path(project).resolve()
    path = Path(source).resolve()
    relative = path.relative_to(root).as_posix()
    text, source_hash = FileUtils.read_source_snapshot(str(path))
    settings = read_explicit_project_config(root)
    state, digest = _read(root)
    passages = speech_passages(text, language, settings)
    directions = []
    for entry in state.entries:
        if entry.source_path != relative:
            continue
        try:
            _ranges(passages, [entry.direction])
            stale = False
        except ValueError:
            stale = True
        directions.append({**entry.direction.model_dump(), 'id': direction_id(entry.direction), 'stale': stale})
    return {'schema_version': 'lixity-audio-direction-view/1', 'source_sha256': source_hash,
            'settings_sha256': _digest(settings), 'direction_sha256': digest,
            'source_path': relative, 'passages': passages, 'directions': directions}


def saved_directions(view: Mapping[str, Any]) -> list[Direction]:
    return [Direction.model_validate({k:v for k,v in item.items() if k not in ('id','stale')})
            for item in view['directions']]


def save_direction(project: str | Path, source: str | Path, value: Mapping[str, Any] | None, *,
                   expected_source_sha256: str, expected_settings_sha256: str,
                   expected_direction_sha256: str, language: str = 'en', remove_id: str | None = None,
                   replace_id: str | None = None) -> dict[str, Any]:
    root = Path(project).resolve()
    repo = Repository(root)
    with repo.locked():
        current = direction_state(root, source, language=language)
        def check() -> None:
            latest = direction_state(root, source, language=language)
            if any(latest[k] != v for k,v in (('source_sha256',expected_source_sha256),
                    ('settings_sha256',expected_settings_sha256), ('direction_sha256',expected_direction_sha256))):
                raise ResearchConflictError('Manuscript, settings or speech directions changed; reload before saving')
        check()
        state, _digest_before = _read(root)
        if (value is None) == (remove_id is None) or (value is None and replace_id is not None):
            raise ValueError('Choose one direction to save or remove')
        if value is not None:
            d = Direction.model_validate(value)
            settings = read_explicit_project_config(root)
            profiles = parse_audio_settings(settings.get('audio'), language=language).profiles
            if d.profile_id is not None and d.profile_id not in profiles:
                raise ValueError('Choose an existing saved voice profile')
            if replace_id is not None and not any(e.source_path == current['source_path'] and direction_id(e.direction) == replace_id for e in state.entries):
                raise ValueError('Choose an existing direction to replace')
            target_id = replace_id if replace_id is not None else direction_id(d)
        else:
            if remove_id is None:
                raise ValueError("Choose an existing direction to remove")
            target_id = remove_id
        retained = [e for e in state.entries if not (e.source_path == current['source_path'] and direction_id(e.direction) == target_id)]
        if value is None and len(retained) == len(state.entries):
            raise ValueError('Choose an existing direction to remove')
        if value is not None:
            remaining = [e.direction for e in retained if e.source_path == current['source_path']]
            # Stale records are preserved for explicit review, not silently reassigned.
            fresh = [item for item in remaining if any(item.anchor.model_dump()==p['anchor'] for p in current['passages'])]
            _ranges(current['passages'], [*fresh,d])
            retained.append(_Stored(source_path=current['source_path'], direction=d))
        retained.sort(key=lambda e: (e.source_path, e.direction.anchor.start_line, e.direction.start, e.direction.end or 0))
        updated = _State(entries=retained)
        raw = updated.model_dump_json(indent=2).encode()
        if len(raw) > MAX_BYTES:
            raise ValueError('Speech direction state exceeds 4 MiB')
        FileUtils.atomic_write_bytes_if_changed(str(repo.safe(root / '.lixity/audio-directions.json')), raw, before_replace=check)
    return direction_state(root, source, language=language)
