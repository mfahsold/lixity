"""Disposable synthetic native workspace for editor browser tests."""
import hashlib
import sys
from pathlib import Path

from lixity.research import api
from lixity.research.repository import Repository
from tests.support import LoopbackServer, make_handler

root = Path(sys.argv[1])
api.init(root, title="Synthetic editor research")
claim = api.create_claim(root, title="River observation", statement="The morning was quiet.")["claim_id"]
quote = "A quiet morning beside the river."
archive = Repository(root).snapshot()
api.link_manuscript_claim(root, root / "book.md", claim, claim_revision=1,
    selection={"start_line":3,"end_line":3,"paragraph_sha256":hashlib.sha256(quote.encode()).hexdigest(),
               "start":0,"end":len(quote),"quote":quote},
    expected_project_id=archive.project.id, expected_snapshot=archive.digest,
    expected_source_sha256=hashlib.sha256((root / "book.md").read_bytes()).hexdigest(), allow_retention=True)
handler = make_handler(root, source_input=root / "book.md")
handler.refresh()
with LoopbackServer(handler) as server:
    print(server.base, flush=True)
    sys.stdin.read()
