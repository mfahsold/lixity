"""Bounded project contexts on one HTTP server, using the existing native routes."""
from __future__ import annotations

import re
from html import escape
from pathlib import Path
from secrets import token_hex
from threading import RLock
from typing import TYPE_CHECKING, Any

from ..workspace_labels import WORKSPACE_LABELS

if TYPE_CHECKING:
    from .handler import LixityServerHandler

MAX_WORKSPACES = 16
_SELECTIONS = frozenset({'project-open', 'project-create', 'load'})
_STATE = (
    'source_input', 'workspace_root', 'exports_dir', 'research_dir', 'language',
    'title', 'title_custom', 'thresholds', 'project_open_overrides', 'debug',
)


class WorkspaceRegistry:
    """Retain independent state/locks, not extra listeners or model processes.

    A request adapter shares only the already parsed HTTP transport. Its class
    owns project state, so existing class-bound transitions and async speech
    validity checks keep referring to that project after another tab opens one.
    """

    def __init__(self, initial: type[LixityServerHandler]) -> None:
        self._lock = RLock()
        self._contexts: dict[str, type[LixityServerHandler]] = {}
        self._pending: dict[str, type[LixityServerHandler]] = {}
        self._initial = initial
        self.default = self._create(initial, publish=True)
        self.default.refresh()

    def _create(self, source: type[LixityServerHandler], *, publish: bool = False) -> type[LixityServerHandler]:
        with self._lock:
            if len(self._contexts) + len(self._pending) >= MAX_WORKSPACES:
                raise ValueError('Close an open workspace before opening another')
            identifier = token_hex(16)
            state = {key: getattr(source, key) for key in _STATE}
            state.update(_workspace_lock=RLock(), dashboard_html='', dashboard_info={},
                         _speech_generation=0, api_base=f'/w/{identifier}/api')
            # Launch overrides belong to the startup view; new projects use their own configuration.
            state['project_open_overrides'] = dict(source.project_open_overrides) if publish else {}
            context = type('ProjectWorkspace', (self._initial,), state)
            (self._contexts if publish else self._pending)[identifier] = context
            return context

    def publish(self, context: type[LixityServerHandler]) -> None:
        """Make a successfully prepared candidate reachable exactly once."""
        identifier = context.api_base.split('/')[2]
        with self._lock:
            if self._pending.get(identifier) is not context:
                raise ValueError("Workspace candidate is no longer available")
            self._contexts[identifier] = self._pending.pop(identifier)

    def items(self) -> list[dict[str, Any]]:
        with self._lock:
            contexts = list(self._contexts.items())
        return [{'id': key, 'url': f'/w/{key}/',
                 'title': context.title or (Path(context.source_input).stem if context.source_input else 'Lixity'),
                 'closable': context is not self.default,
                 'manuscript_loaded': bool(context.source_input)} for key, context in contexts]

    def contains(self, context: type[LixityServerHandler]) -> bool:
        with self._lock:
            return context in self._contexts.values()

    def close(self, identifier: str) -> None:
        """Forget an idle view; never remove project files or retained research."""
        with self._lock:
            context = self._contexts.get(identifier)
            if context is None or context is self.default:
                raise ValueError("Choose an open non-startup workspace")
            self._contexts.pop(identifier)

    def dispatch(self, request: LixityServerHandler, method: str) -> bool:
        """Dispatch explicit prefixes without mutating the server's selection."""
        path, separator, query = request.path.partition('?')
        context = self.default
        scoped = re.fullmatch(r'/w/([a-f0-9]{32})(/.*)?', path)
        if scoped:
            with self._lock:
                found = self._contexts.get(scoped[1])
            if found is None:
                if method == 'GET' and (scoped[2] or '/') == '/':
                    labels = WORKSPACE_LABELS.get(request.language, WORKSPACE_LABELS['en'])
                    body = ('<!doctype html><html><meta charset="utf-8"><meta name="viewport" content="width=device-width">'
                            '<title>Lixity</title><main><h1>Lixity</h1><p>' + escape(labels['runtime_scope_note']) +
                            '</p><a href="/">' + escape(labels['runtime_workspaces']) + '</a></main></html>')
                    request._send(410, body.encode('utf-8'), 'text/html; charset=utf-8')
                else:
                    request._json({'ok': False, 'message': 'Workspace expired; reopen the project from the app home.'}, 410)
                return True
            context = found
            path = scoped[2] or '/'
        elif path.startswith('/w/'):
            request._json({'ok': False, 'message': 'Unknown workspace'}, 404)
            return True
        elif method == 'GET' and path in ('/', '/index.html'):
            request._send(303, b'', 'text/plain', headers={'Location': self.default.api_base.removesuffix('/api') + '/'})
            return True
        elif not path.startswith(('/api', '/artifact/')):
            return False

        selection = method == 'POST' and path.removeprefix('/api/').strip('/') in _SELECTIONS
        if selection:
            try:
                context = self._create(context)
            except ValueError as exc:
                request._json({'ok': False, 'message': str(exc)}, 409)
                return True
        # The delegate does not initialize another socket or parse another HTTP
        # request. All input/output streams and response lifecycle stay owned by
        # the one real handler; only workspace-bound method lookup differs.
        bound = object.__new__(context)
        bound.__dict__.update(request.__dict__)
        bound.path = path + (separator + query if separator else '')
        bound._workspace_dispatched = True
        bound._workspace_selection = selection
        bound._workspace_selection_ok = False
        try:
            getattr(bound, 'do_' + method)()
        finally:
            request.close_connection = bound.close_connection
            if selection and not bound._workspace_selection_ok:
                with self._lock:
                    self._pending.pop(context.api_base.split('/')[2], None)
        return True
