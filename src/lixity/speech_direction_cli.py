"""Explicit-project CLI for observing and saving authored speech directions."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .config import read_explicit_project_config
from .speech_direction import MAX_BYTES, direction_state, save_direction
from .workspace import resolve_manuscript_target


def configure(parser: argparse.ArgumentParser) -> None:
    parser.add_argument('action', nargs='?', default='inspect', choices=('inspect','save','remove'))
    parser.add_argument('--project', required=True, help='Explicit project root')
    parser.add_argument('--manuscript', help='Explicit manuscript within the project')
    parser.add_argument('--input', help='Direction JSON file for save; no manuscript changes')
    parser.add_argument('--replace-id', help='Observed original range ID when adjusting its bounds')
    parser.add_argument('--id', help='Observed direction ID for remove')
    parser.add_argument('--expected-source', help='Observed source_sha256 for writes')
    parser.add_argument('--expected-settings', help='Observed settings_sha256 for writes')
    parser.add_argument('--expected-direction', help='Observed direction_sha256 for writes')


def run(args: argparse.Namespace) -> dict[str, Any]:
    workspace = resolve_manuscript_target(args.manuscript, project=args.project)
    settings = read_explicit_project_config(Path(workspace.root))
    language = settings.get('language','en')
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
