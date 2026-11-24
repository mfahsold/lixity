"""Project-local author intentions bound to an inspected manuscript revision."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Any, Literal, get_args
from uuid import uuid4

from pydantic import Field, StringConstraints

from .io import FileUtils
from .models import CorpusConfig
from .research.models import Digest, StrictModel
from .research.repository import Repository, ResearchConflictError

IntentKind = Literal["question", "delayed_answer", "turning_point", "reveal", "resolution"]
INTENT_KINDS: tuple[IntentKind, ...] = get_args(IntentKind)
INTENT_TEXT_LIMIT = 600
INTENT_VOICE_LIMIT = 160
_STATE_PATH = Path(".lixity/analysis-intents.json")
_MAX_BYTES = 4 * 1024 * 1024
_MAX_CARDS = 1000
_POLICY = "analysis-intents-context/1"

CardId = Annotated[str, Field(pattern=r"^[0-9a-f]{32}$")]
SceneId = Annotated[str, Field(pattern=r"^[1-9][0-9]*:[1-9][0-9]*$", max_length=32)]
IntentText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=INTENT_TEXT_LIMIT)]
Hypothesis = Annotated[str, StringConstraints(strip_whitespace=True, max_length=INTENT_TEXT_LIMIT)]
Voice = Annotated[str, StringConstraints(strip_whitespace=True, max_length=INTENT_VOICE_LIMIT)]


class IntentTextFields(StrictModel):
    scene_id: SceneId
    kind: IntentKind
    intent: IntentText
    hypothesis: Hypothesis = ""
    voice: Voice = ""


class IntentCard(IntentTextFields):
    id: CardId
    source_path: Annotated[str, Field(min_length=1, max_length=4096)]
    source_sha256: Digest
    analysis_sha256: Digest
    scene_title: str


class IntentState(StrictModel):
    schema_version: Literal["lixity-analysis-intents-state/1"] = "lixity-analysis-intents-state/1"
    cards: Annotated[list[IntentCard], Field(max_length=_MAX_CARDS)] = Field(default_factory=list)


class IntentExpectation(StrictModel):
    expected_source_sha256: Digest
    expected_analysis_sha256: Digest
    expected_intents_sha256: Digest


class SaveIntent(IntentExpectation, IntentTextFields):
    action: Literal["save"]
    id: CardId | None = None


class DeleteIntent(IntentExpectation):
    action: Literal["delete"]
    id: CardId


class SaveIntentOrder(IntentExpectation):
    action: Literal["save_order"]
    ids: Annotated[list[CardId], Field(max_length=_MAX_CARDS)]


IntentMutation = Annotated[SaveIntent | DeleteIntent | SaveIntentOrder, Field(discriminator="action")]


@dataclass(frozen=True)
class IntentContext:
    source_sha256: str
    analysis_sha256: str
    scenes: Mapping[str, str]


def scene_intent_context(source_sha256: str, scenes: Mapping[str, Any], config: CorpusConfig) -> IntentContext:
    """Use the scene rows from the rendered analysis, without reparsing or measuring prose."""
    rows = scenes.get("items", ())
    context = {"policy": _POLICY, "config": config.model_dump(mode="json"), "scenes": rows,
               "available": "items" in scenes}
    identity = json.dumps(context, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
    return IntentContext(source_sha256, hashlib.sha256(identity.encode()).hexdigest(),
                         {row["id"]: row["scene_title"] for row in rows})


def _read(repository: Repository) -> tuple[IntentState, str]:
    path = repository.safe(repository.root / _STATE_PATH)
    try:
        raw, _stat = FileUtils.read_bounded_regular_bytes(path, maximum=_MAX_BYTES)
    except FileNotFoundError:
        return IntentState(), hashlib.sha256(b"").hexdigest()
    state = IntentState.model_validate_json(raw)
    if len({card.id for card in state.cards}) != len(state.cards):
        raise ValueError("The author intention file has duplicate card identities")
    return state, hashlib.sha256(raw).hexdigest()


def has_retained_scene_intents(project: str | Path, source: Path) -> bool:
    """Keep the board discoverable for a draft whose scene measurements disappeared."""
    repository = Repository(project)
    try:
        relative = repository.safe(source).relative_to(repository.root).as_posix()
    except (OSError, ValueError):
        return False
    try:
        state, _ = _read(repository)
    except (OSError, ValueError, RuntimeError):
        # The board can report an unreadable store through the regular endpoint.
        return True
    return any(card.source_path == relative for card in state.cards)


def _view(context: IntentContext, cards: Sequence[IntentCard], state_hash: str) -> dict[str, Any]:
    return {"schema_version": "lixity-analysis-intents/1", "source_sha256": context.source_sha256,
            "analysis_sha256": context.analysis_sha256, "intents_sha256": state_hash,
            "cards": [{**card.model_dump(exclude={"source_path", "source_sha256", "analysis_sha256"}),
                       "review_status": "current" if (
                           card.source_sha256 == context.source_sha256
                           and card.analysis_sha256 == context.analysis_sha256
                           and card.scene_id in context.scenes
                       ) else "stale",
                       "scene_available": card.scene_id in context.scenes}
                      for card in cards]}


def _require_source(repository: Repository, source: Path, context: IntentContext) -> None:
    try:
        current = FileUtils.read_source_snapshot(str(repository.safe(source)))[1]
    except FileNotFoundError as exc:
        raise ResearchConflictError("The displayed manuscript is no longer available") from exc
    if current != context.source_sha256:
        raise ResearchConflictError("The manuscript differs from the displayed analysis; refresh before reviewing")


def read_scene_intents(project: str | Path, source: Path, context: IntentContext) -> dict[str, Any]:
    repository = Repository(project)
    _require_source(repository, source, context)
    state, state_hash = _read(repository)
    relative = source.relative_to(repository.root).as_posix()
    return _view(context, [card for card in state.cards if card.source_path == relative], state_hash)


def _updated_cards(cards: list[IntentCard], mutation: IntentMutation, context: IntentContext,
                   relative: str) -> list[IntentCard]:
    by_id = {card.id: card for card in cards}
    if isinstance(mutation, SaveIntentOrder):
        if len(mutation.ids) != len(cards) or set(mutation.ids) != by_id.keys():
            raise ValueError("A rehearsal order must include each card for this manuscript exactly once")
        return [by_id[card_id] for card_id in mutation.ids]
    if mutation.id and mutation.id not in by_id:
        raise ValueError("Choose an existing intention for this manuscript")
    if isinstance(mutation, DeleteIntent):
        return [card for card in cards if card.id != mutation.id]
    title = context.scenes.get(mutation.scene_id)
    if title is None:
        raise ValueError("Choose a measured scene from the displayed analysis")
    saved = IntentCard(id=mutation.id or uuid4().hex, scene_id=mutation.scene_id,
                       kind=mutation.kind, intent=mutation.intent,
                       hypothesis=mutation.hypothesis, voice=mutation.voice, scene_title=title,
                       source_path=relative, source_sha256=context.source_sha256,
                       analysis_sha256=context.analysis_sha256)
    if mutation.id is None:
        return [*cards, saved]
    return [saved if card.id == saved.id else card for card in cards]


def write_scene_intents(project: str | Path, source: Path, context: IntentContext,
                        mutation: IntentMutation, *, require_settings: Callable[[], None]) -> dict[str, Any]:
    """Apply one explicit author action under source, analysis and state guards."""
    repository = Repository(project)
    with repository.locked():
        target = repository.safe(repository.root / _STATE_PATH)
        _require_source(repository, source, context)
        FileUtils.require_distinct_output(str(source), str(target))
        require_settings()
        state, state_hash = _read(repository)
        if (mutation.expected_source_sha256, mutation.expected_analysis_sha256, mutation.expected_intents_sha256) != (
            context.source_sha256, context.analysis_sha256, state_hash,
        ):
            raise ResearchConflictError("The manuscript, analysis or saved intentions changed; reload before saving")
        relative = source.relative_to(repository.root).as_posix()
        current = [card for card in state.cards if card.source_path == relative]
        updated = _updated_cards(current, mutation, context, relative)
        if updated == current:
            return _view(context, current, state_hash)
        next_state = IntentState(cards=[card for card in state.cards if card.source_path != relative] + updated)
        raw = next_state.model_dump_json().encode("utf-8")
        if len(raw) > _MAX_BYTES:
            raise ValueError("The author intention file exceeds the 4 MiB limit")

        def check() -> None:
            _require_source(repository, source, context)
            FileUtils.require_distinct_output(str(source), str(target))
            require_settings()
            if _read(repository)[1] != state_hash:
                raise ResearchConflictError("Saved intentions changed before publication; reload before saving")

        FileUtils.atomic_write_bytes_if_changed(str(target), raw, before_replace=check)
    return _view(context, updated, hashlib.sha256(raw).hexdigest())
