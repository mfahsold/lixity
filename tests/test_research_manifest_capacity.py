"""Current manifest capacity remains bounded by entries and canonical JSON bytes."""

from typing import get_args

import pytest
from pydantic import ValidationError

from lixity.research.models import Entry, Kind, Manifest, Reference
from lixity.research.repository import MAX_RESEARCH_OBJECT_BYTES, encode


def test_current_capacity_schema_and_longest_entry_shape_fit_byte_limit():
    entry = Entry(kind=max(get_args(Kind), key=len),
                  ref=Reference(id='urn:uuid:ffffffff-ffff-4fff-8fff-ffffffffffff', revision=100000), sha256='f' * 64)
    manifest = Manifest(project_id=entry.ref.id, generation=100000, parent='f' * 64, entries=[entry] * 100000)
    assert Manifest.model_json_schema()['properties']['entries']['maxItems'] == 100000
    assert len(encode(manifest)) < MAX_RESEARCH_OBJECT_BYTES
    assert len(manifest.entries) == 100000
    with pytest.raises(ValidationError):
        Manifest(project_id=entry.ref.id, generation=1, parent=None, entries=[entry] * 100001)
