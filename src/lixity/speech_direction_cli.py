"""Explicit-project CLI for observing and saving authored speech directions."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .config import read_explicit_project_config
from .speech_direction import MAX_BYTES, Direction, direction_id, direction_state, save_direction
from .workspace import resolve_manuscript_target


def configure(parser: argparse.ArgumentParser) -> None:
    parser.add_argument('action', nargs='?', default='inspect', choices=('inspect','add','save','remove'))
    parser.add_argument('--project', required=True, help='Explicit project root')
    parser.add_argument('--manuscript', help='Explicit manuscript within the project')
    parser.add_argument('--input', help='Direction JSON file for save; no manuscript changes')
    parser.add_argument('--replace-id', help='Observed original range ID when adjusting its bounds')
    parser.add_argument('--id', help='Observed direction ID for remove')
    parser.add_argument('--expected-source', help='Observed source_sha256 for writes')
    parser.add_argument('--expected-settings', help='Observed settings_sha256 for writes')
    parser.add_argument('--expected-direction', help='Observed direction_sha256 for writes')
    parser.add_argument('--chapter', type=int, help='Chapter number for add')
    parser.add_argument('--line', type=int, help='A source line within the passage for add')
    parser.add_argument('--instruction', help='Delivery instruction for add')
    parser.add_argument('--profile-id', help='Saved project voice profile for add')
    parser.add_argument('--pause-before', type=float, help='Silence before the directed passage, in seconds')
    parser.add_argument('--pause-after', type=float, help='Silence after the directed passage, in seconds')
    parser.add_argument('--start', type=int, help='Start offset in spoken Unicode code points for add')
    parser.add_argument('--end', type=int, help='End offset in spoken Unicode code points for add')


def run(args: argparse.Namespace) -> dict[str, Any]:
    workspace = resolve_manuscript_target(args.manuscript, project=args.project)
    settings = read_explicit_project_config(Path(workspace.root))
    language = settings.get('language','en')
    add_values = (args.chapter, args.line, args.instruction, args.profile_id,
                  args.pause_before, args.pause_after, args.start, args.end)
    if args.action == 'add':
        if any((args.input, args.id, args.replace_id, args.expected_source, args.expected_settings, args.expected_direction)):
            raise ValueError('Add resolves its own snapshot and does not replace an existing direction')
        if args.chapter is None or args.chapter < 1 or args.line is None or args.line < 1:
            raise ValueError('Add requires a positive --chapter and --line')
        if not (args.instruction and args.instruction.strip()) and all(
                item is None for item in (args.profile_id, args.pause_before, args.pause_after)):
            raise ValueError('Add requires an instruction, profile or pause')
        current = direction_state(workspace.root, workspace.manuscript, language=language)
        matches = [p for p in current['passages'] if p['chapter'] == args.chapter and
                   p['anchor']['start_line'] <= args.line <= p['anchor']['end_line']]
        if len(matches) != 1:
            raise ValueError('The chapter and line must select exactly one spoken passage')
        direction: dict[str, Any] = {'anchor': matches[0]['anchor']}
        direction.update({key: item for key, item in (
            ('instructions', args.instruction), ('profile_id', args.profile_id),
            ('pause_before', args.pause_before), ('pause_after', args.pause_after),
            ('start', args.start), ('end', args.end)) if item is not None})
        candidate_id = direction_id(Direction.model_validate(direction))
        if any(item['id'] == candidate_id for item in current['directions']):
            raise ValueError('This passage range already has a direction; inspect and explicitly replace it')
        return save_direction(workspace.root, workspace.manuscript, direction,
            expected_source_sha256=current['source_sha256'], expected_settings_sha256=current['settings_sha256'],
            expected_direction_sha256=current['direction_sha256'], language=language)
    if any(item is not None for item in add_values):
        raise ValueError('Chapter, line, instruction, profile, pause and offsets are only available for add')
    if args.action == 'inspect':
        if any((args.input,args.id,args.replace_id,args.expected_source,args.expected_settings,args.expected_direction)):
            raise ValueError('Inspect takes no mutation arguments')
        return direction_state(workspace.root,workspace.manuscript,language=language)
    if not all((args.expected_source,args.expected_settings,args.expected_direction)):
        raise ValueError('Writes require all three observed snapshot hashes from inspect')
    value = None
    if args.action == 'save':
        if not args.input or args.id:
            raise ValueError('Save requires --input, without --id')
        with Path(args.input).open('rb') as source:
            raw = source.read(MAX_BYTES+1)
        if len(raw)>MAX_BYTES:
            raise ValueError('Direction JSON exceeds 4 MiB')
        value=json.loads(raw)
        if not isinstance(value,dict):
            raise ValueError('Supply one direction JSON object')
    elif not args.id or args.input or args.replace_id:
        raise ValueError('Remove requires --id, without --input')
    return save_direction(workspace.root,workspace.manuscript,value,
        expected_source_sha256=args.expected_source, expected_settings_sha256=args.expected_settings,
        expected_direction_sha256=args.expected_direction, language=language,
        remove_id=args.id if args.action=='remove' else None, replace_id=args.replace_id)
