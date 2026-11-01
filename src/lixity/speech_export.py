"""Provider-neutral timeline exchange and explicitly lossy W3C SSML 1.0 export.

Timeline source ranges address the established cleaned spoken projection, not
Markdown byte offsets. Audio durations cannot be inferred from a direction plan.
SSML voice names are processor-specific; binding and delivery losses are reported.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
import unicodedata
from collections.abc import Sequence
from decimal import Decimal
from typing import Any
from xml.sax.saxutils import escape, quoteattr

from .speech_direction import SpeechSegment

TIMELINE_SCHEMA = 'lixity-audio-timeline/1'
_TIMING_REASON = 'Audio has not been measured; a text plan does not determine speech duration.'


def _speaker(row: SpeechSegment) -> tuple[str, dict[str, Any]]:
    """Keep voice identity separate from passage delivery and synthesis tempo."""
    profile = row.profile.model_dump()
    identity: dict[str, Any] = {key: profile[key] for key in (
        'name', 'engine', 'language', 'voice', 'voice_description', 'reference_id', 'base_url', 'model',
    ) if key in profile}
    if row.export_info and row.export_info.direction and row.export_info.direction.profile_id:
        identity['profile_id'] = row.export_info.direction.profile_id
    encoded = json.dumps(identity, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
    return 'speaker-' + hashlib.sha256(encoded).hexdigest(), identity


def _warning(code: str, message: str, **context: Any) -> dict[str, Any]:
    return {'code': code, 'message': message, **context}


def timeline_json(plan: Sequence[SpeechSegment]) -> dict[str, Any]:
    """Serialize authored choices without requiring a worker or reference bytes.

    Use ``build_speech_plan(..., for_export=True)`` for full source provenance.
    Older render plans remain exportable with their missing provenance explicit.
    """
    speakers: dict[str, dict[str, Any]] = {}
    segments = []
    warnings = []
    for index, row in enumerate(plan, 1):
        speaker_id, speaker = _speaker(row)
        speakers.setdefault(speaker_id, speaker)
        info = row.export_info
        source_range = None
        if info is not None and row.anchor is not None:
            source_range = {'start': info.start, 'end': info.end,
                            'unit': 'unicode-code-point', 'projection': 'spoken-projection'}
        if info is None:
            warnings.append(_warning('source_provenance_unavailable',
                                     'This render segment has no retained pre-substitution source range.', segment=index))
        segments.append({
            'id': f'segment-{index}', 'speaker_id': speaker_id,
            'text': row.text, 'spoken_text': row.text,
            'original_text': info.original_text if info else None,
            'anchor': dict(row.anchor) if row.anchor is not None else None,
            'source_range': source_range,
            'source_reason': None if source_range is not None else
                'No paragraph anchor is available for this structural cue.' if info else
                'The render plan did not retain source provenance.',
            'chapter': info.chapter if info else None, 'kind': info.kind if info else None,
            'profile': row.profile.model_dump(),
            'instructions': info.instructions if info else row.profile.instructions,
            'direction': info.direction.model_dump() if info and info.direction else None,
            'substitutions': [{'start': start, 'end': end, 'original': info.original_text[start:end],
                               'replacement': replacement} for start, end, replacement in info.substitutions] if info else [],
            'pause_before': row.pause_before, 'pause_after': row.pause_after,
            'start_seconds': None, 'end_seconds': None, 'duration_seconds': None,
            'timing_reason': _TIMING_REASON,
        })
    return {
        'schema_version': TIMELINE_SCHEMA,
        'source_projection': 'Cleaned spoken text before pronunciation substitutions; offsets are Unicode code points.',
        'substitution_offsets': 'Relative to each segment original_text, before substitution.',
        'speakers': speakers, 'segments': segments,
        'timing': {'status': 'unmeasured', 'duration_seconds': None, 'reason': _TIMING_REASON,
                   'explicit_pause_seconds': math.fsum(row.pause_before + row.pause_after for row in plan)},
        'warnings': warnings,
    }


def _xml(value: str) -> str:
    """Refuse XML-forbidden characters rather than silently alter spoken data."""
    if any(not (char in '\t\n\r' or 0x20 <= ord(char) <= 0xD7FF or
                0xE000 <= ord(char) <= 0xFFFD or 0x10000 <= ord(char) <= 0x10FFFF) for char in value):
        raise ValueError('Speech export contains a character not representable in XML 1.0')
    return value


def _language(value: str) -> str:
    if not re.fullmatch(r'[A-Za-z]{1,8}(?:-[A-Za-z0-9]{1,8})*', value):
        raise ValueError('SSML language must be a language tag such as en or de-DE')
    return value


def _word_character(value: str) -> bool:
    return bool(value) and (value.isalnum() or value == '_' or unicodedata.category(value).startswith('M'))


def _content(row: SpeechSegment, index: int, warnings: list[dict[str, Any]]) -> str:
    info = row.export_info
    if info is None or not info.substitutions:
        return escape(_xml(row.text))
    parts = []
    spoken: list[str] = []
    cursor = 0
    for start, end, replacement in info.substitutions:
        original = info.original_text
        if not cursor <= start < end <= len(original):
            raise ValueError('Speech export has an invalid pronunciation source span')
        # SSML processors may tokenize across element boundaries differently.
        # Preserve the already-substituted text when a literal rule cuts a word.
        before = original[start - 1:start] if start else info.left_context[-1:]
        after = original[end:end + 1] if end < len(original) else info.right_context[:1]
        if ((_word_character(original[start:start + 1]) and _word_character(before)) or
                (_word_character(original[end - 1:end]) and _word_character(after))):
            warnings.append(_warning('pronunciation_markup_unavailable',
                                     'A partial-word substitution is exported as spoken text; its source mapping remains in the timeline.',
                                     segment=index))
            return escape(_xml(row.text))
        parts.append(escape(_xml(original[cursor:start])))
        parts.append(f'<sub alias={quoteattr(_xml(replacement))}>{escape(_xml(original[start:end]))}</sub>')
        spoken.extend((original[cursor:start], replacement))
        cursor = end
    parts.append(escape(_xml(info.original_text[cursor:])))
    spoken.append(info.original_text[cursor:])
    if ''.join(spoken) != row.text:
        warnings.append(_warning('pronunciation_markup_unavailable',
                                 'Spoken text differs from the retained substitution projection; exporting spoken text.', segment=index))
        return escape(_xml(row.text))
    return ''.join(parts)


def _pause(seconds: float) -> str:
    if not math.isfinite(seconds) or seconds < 0:
        raise ValueError('Speech export pauses must be finite and nonnegative')
    milliseconds = format(Decimal(str(seconds)) * 1000, 'f')
    if '.' in milliseconds:
        milliseconds = milliseconds.rstrip('0').rstrip('.')
    return f'<break time="{milliseconds}ms" />'


def ssml_export(plan: Sequence[SpeechSegment], *, default_lang: str = 'en') -> dict[str, Any]:
    """Return SSML plus explicit portability/loss warnings; timeline is authoritative.

    SSML 1.0 numeric rate values are multipliers. They request prosody changes,
    unlike the renderer's post-synthesis tempo adjustment, so equivalence is not
    promised. Reference/design and ambiguous voice names use stable speaker handles.
    """
    warnings: list[dict[str, Any]] = []
    lines = [f'<speak xmlns="http://www.w3.org/2001/10/synthesis" version="1.0" xml:lang={quoteattr(_language(default_lang))}>']
    voice_speakers: dict[str, set[str]] = {}
    for row in plan:
        if row.text.strip():
            speaker_id, _identity = _speaker(row)
            voice_speakers.setdefault(row.profile.voice, set()).add(speaker_id)
    warned_speakers: set[str] = set()
    for index, row in enumerate(plan, 1):
        before, after = _pause(row.pause_before), _pause(row.pause_after)
        if row.pause_before > 0:
            lines.append('  ' + before)
        if row.text.strip():
            speaker_id, _identity = _speaker(row)
            voice_name = (speaker_id if row.profile.voice in ('design', 'reference') or
                          any(char.isspace() for char in row.profile.voice) or
                          len(voice_speakers[row.profile.voice]) > 1 else row.profile.voice)
            if speaker_id not in warned_speakers:
                warnings.append(_warning('voice_binding_required',
                                         'SSML voice names are processor-specific; map this speaker to a voice in the receiving engine.',
                                         speaker_id=speaker_id, voice=voice_name))
                warned_speakers.add(speaker_id)
            instructions = row.export_info.instructions if row.export_info else row.profile.instructions
            if instructions:
                warnings.append(_warning('unsupported_instructions',
                                         'Free-text delivery instructions are retained in the timeline and cannot be represented faithfully in standard SSML.',
                                         segment=index))
            content = _content(row, index, warnings)
            if row.profile.speed != 1.0:
                content = f'<prosody rate="{row.profile.speed:.15g}">{content}</prosody>'
                warnings.append(_warning('rate_is_advisory',
                                         'SSML prosody rate is advisory and is not an exact post-synthesis tempo adjustment.', segment=index))
            lines.append(f'  <voice name={quoteattr(_xml(voice_name))} xml:lang={quoteattr(_language(row.profile.language or default_lang))}>{content}</voice>')
        if row.pause_after > 0:
            lines.append('  ' + after)
    lines.append('</speak>')
    return {'ssml': '\n'.join(lines), 'warnings': warnings}
