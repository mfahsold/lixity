"""Authored geography follows dossier revisions, evidence and archive boundaries."""

import copy
import json

import pytest
from pydantic import ValidationError

from lixity.research import api
from lixity.research.models import Dossier
from lixity.research.repository import Repository, ResearchConflictError, ResearchError, encode
from lixity.server.pdf_context import research_context_token
from tests.research_support import capture_research, retained_files, revise_record
from tests.support import LoopbackServer, make_handler


@pytest.fixture
def project(tmp_path):
    root = tmp_path / "project"
    api.init(root, title="Synthetic geographic notes")
    return root


def geography():
    return {"type": "FeatureCollection", "features": [
        {"type": "Feature", "geometry": {"type": "Point", "coordinates": [13.4, 52.5]},
         "properties": {"label": "Synthetic gate", "description": "Basalt archway",
                        "time_period": "1924", "feature_type": "landmark"}},
        {"type": "Feature", "geometry": {"type": "LineString", "coordinates": [[13.4, 52.5], [13.41, 52.51]]},
         "properties": {"label": "Canal journey", "actors": ["Mira"], "transport": "walking",
                        "waypoint_labels": ["Departure", "Arrival"]}},
        {"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [
            [[13.3, 52.4], [13.5, 52.4], [13.5, 52.6], [13.3, 52.4]]]},
         "properties": {"label": "Marshland", "feature_type": "wetland"}},
        {"type": "Feature", "geometry": None, "properties": {"label": "Unlocated estate"}},
    ]}


def test_geography_summary_is_derived_from_the_exact_dossier_revision(project):
    identifier = api.create_dossier(project, "Synthetic places", "# Places\n\nNotes.", geography=geography())["dossier_id"]
    before = retained_files(project)
    summary = api.get_dossier(project, identifier)["geography_summary"]
    assert summary["schema_version"] == "research-geography-summary-local/1"
    assert summary["feature_count"] == 4
    assert summary["located_feature_count"] == 3
    assert summary["unlocated_feature_count"] == 1
    assert summary["geometry_counts"] == {"Point": 1, "LineString": 1, "Polygon": 1, "unknown": 1}
    assert summary["distance_method"] == "haversine_sphere"
    assert summary["earth_radius_km"] == 6371.0088
    assert summary["limitations"] == ["authored_coordinates", "shortest_great_circle_segments",
        "not_road_routing", "not_travel_time", "not_historical_verification", "no_elevation"]
    route = summary["features"][1]
    assert route == {"index": 1, "geometry_type": "LineString", "position_count": 2,
        "segment_count": 1, "named_waypoint_count": 2, "route_length_km": pytest.approx(1.3018, abs=.001),
        "label": "Canal journey", "time_period": None, "actors": ["Mira"],
        "transport": "walking", "feature_type": None, "waypoint_labels": ["Departure", "Arrival"]}
    assert summary["route_length_km"] == route["route_length_km"]
    assert summary["features"][2]["position_count"] == 4  # Includes the polygon's closing coordinate.
    assert summary["features"][2]["route_length_km"] is None
    assert summary["features"][2]["segment_count"] is None
    assert "description" not in summary["features"][0]
    assert summary["features"][3]["geometry_type"] == "unknown"
    assert summary["features"][3]["position_count"] == 0
    assert api.get_dossier(project, identifier, summary=True)["geography_summary"] == summary
    assert api.get_record(project, "dossier", identifier)["geography_summary"] == summary
    assert "geography_summary" not in api.get_dossier(project, identifier, section="Places")
    assert "geography_summary" not in api.get_record(project, "dossier", identifier)["record"]
    assert retained_files(project) == before
    revise_record(project, "dossier", identifier, {"geography": None})
    assert api.get_dossier(project, identifier)["geography_summary"] is None
    assert api.get_dossier(project, identifier, revision=1)["geography_summary"] == summary
    assert api.get_record(project, "dossier", identifier, revision=1)["geography_summary"] == summary


@pytest.mark.parametrize(("coordinates", "expected"), [
    ([[0, 0], [1, 0], [1, 1]], 222.390160467),
    ([[179, 0], [-179, 0]], 222.390160467),
    ([[13, 52], [13, 52]], 0),
    ([[180, 42], [-180, 42]], 0),
    ([[0, 0], [180, 0]], 20015.114442),
    ([[0, 90], [180, 90]], 0),
])
def test_geography_route_length_measures_authored_spherical_segments(project, coordinates, expected):
    value = {"type": "FeatureCollection", "features": [{"type": "Feature", "properties": {"label": "Synthetic path"},
        "geometry": {"type": "LineString", "coordinates": coordinates}}]}
    identifier = api.create_dossier(project, "Route", "Synthetic.", geography=value)["dossier_id"]
    summary = api.get_dossier(project, identifier, summary=True)["geography_summary"]
    if expected == 0:
        assert summary["route_length_km"] == 0
    else:
        assert summary["route_length_km"] == pytest.approx(expected, abs=.000001)
    assert summary["features"][0]["route_length_km"] == summary["route_length_km"]
    assert summary["features"][0]["named_waypoint_count"] == 0
    json.dumps(summary, allow_nan=False)


def test_geography_summary_distinguishes_absent_empty_and_unlocated(project):
    absent = api.create_dossier(project, "No geography", "Synthetic.")["dossier_id"]
    empty = api.create_dossier(project, "Empty geography", "Synthetic.",
        geography={"type": "FeatureCollection", "features": []})["dossier_id"]
    unlocated = api.create_dossier(project, "Unplaced", "Synthetic.", geography={"type": "FeatureCollection", "features": [
        {"type": "Feature", "geometry": None, "properties": {"label": "Unknown <place>"}}]})["dossier_id"]
    assert api.get_dossier(project, absent, summary=True)["geography_summary"] is None
    empty_summary = api.get_dossier(project, empty)["geography_summary"]
    assert empty_summary["feature_count"] == 0 and empty_summary["features"] == []
    assert empty_summary["route_length_km"] is None
    unknown = api.get_dossier(project, unlocated)["geography_summary"]
    assert unknown["located_feature_count"] == 0 and unknown["unlocated_feature_count"] == 1
    assert unknown["features"][0]["label"] == "Unknown <place>"
    assert unknown["route_length_km"] is None


def test_first_geography_write_opts_in_and_legacy_reencoding_stays_unchanged(project):
    identifier = api.create_dossier(project, "Synthetic dossier", "# Places\n\nOriginal notes.")["dossier_id"]
    repository = Repository(project)
    before = repository.snapshot()
    original = before.latest(identifier, Dossier)
    original_bytes = encode(original)
    assert b'"geography"' not in original_bytes
    assert before.manifest.schema_version == "research-manifest-local/1"
    assert "geography" not in api.get_record(project, "dossier", identifier)["record"]
    assert Repository(project).snapshot().digest == before.digest

    changed = revise_record(project, "dossier", identifier, {"geography": geography()})
    assert changed["record"]["schema_version"] == "research-local/8"
    assert changed["record"]["revision"] == 2
    assert changed["record"]["geography"]["features"][1]["geometry"]["coordinates"] == [[13.4, 52.5], [13.41, 52.51]]
    snapshot = repository.snapshot()
    assert snapshot.manifest.schema_version == "research-manifest-local/8"
    assert encode(snapshot.revisions[(identifier, 1)]) == original_bytes
    assert api.get_dossier(project, identifier)["geography"]["features"][0]["properties"]["label"] == "Synthetic gate"
    summary = api.get_dossier(project, identifier, summary=True)
    assert summary["geography_feature_count"] == 4 and "geography" not in summary
    assert "geography" not in api.get_dossier(project, identifier, section="Places")
    assert api.record_history(project, "dossier", identifier)["revisions"][0]["geography_feature_count"] == 4

    cleared = revise_record(project, "dossier", identifier, {"geography": None})
    assert cleared["record"]["geography"] is None
    assert cleared["record"]["schema_version"] == "research-local/8"
    changed_again = revise_record(project, "dossier", identifier, {"body": "Reviewed notes."})
    assert changed_again["record"]["schema_version"] == "research-local/8"
    assert repository.snapshot().manifest.schema_version == "research-manifest-local/8"
    assert api.audit(project)["ok"]


def test_geography_creation_requires_v8_but_ordinary_revisions_keep_v2(project):
    identifier = api.create_dossier(project, "Located note", "Synthetic.", geography=geography())["dossier_id"]
    record = api.get_record(project, "dossier", identifier)["record"]
    assert record["revision"] == 1 and record["schema_version"] == "research-local/8"
    assert record["change"] is None
    with pytest.raises(ValidationError):
        Dossier.model_validate({**record, "schema_version": "research-local/1"})
    plain = api.create_dossier(project, "Plain note", "Synthetic.")["dossier_id"]
    revised = revise_record(project, "dossier", plain, {"body": "Corrected."})
    assert revised["record"]["schema_version"] == "research-local/2"
    assert "geography" not in revised["record"]


@pytest.mark.parametrize("geometry", [
    {"type": "Point", "coordinates": [181, 52]},
    {"type": "Point", "coordinates": [13, -91]},
    {"type": "Point", "coordinates": [True, 52]},
    {"type": "Point", "coordinates": [13, float("nan")]},
    {"type": "Point", "coordinates": [float("inf"), 52]},
    {"type": "Point", "coordinates": [13, 52, 1]},
    {"type": "LineString", "coordinates": [[13, 52]]},
    {"type": "Polygon", "coordinates": [[[13, 52], [14, 52], [14, 53], [13, 53]]]},
    {"type": "Polygon", "coordinates": []},
    {"type": "MultiPoint", "coordinates": [[13, 52]]},
    {"type": "Point", "coordinates": [13, 52], "crs": "EPSG:4326"},
])
def test_invalid_geometries_fail_before_any_canonical_write(project, geometry):
    identifier = api.create_dossier(project, "Plain note", "Synthetic.")["dossier_id"]
    invalid = {"type": "FeatureCollection", "features": [
        {"type": "Feature", "geometry": geometry, "properties": {"label": "Invalid"}}]}
    before = retained_files(project)
    with pytest.raises(ResearchError):
        api.create_dossier(project, "Bad capture", "Synthetic.", geography=invalid)
    with pytest.raises(ResearchError):
        revise_record(project, "dossier", identifier, {"geography": invalid})
    assert retained_files(project) == before


@pytest.mark.parametrize("properties", [
    {}, {"label": ""}, {"label": " "}, {"label": "x" * 501},
    {"label": "Gate", "description": "x" * 4001},
    {"label": "Gate", "actors": ["x" * 101]},
    {"label": "Gate", "transport": "teleporting"},
    {"label": "Gate", "waypoint_labels": ["One"]},
    {"label": "Gate", "url": "https://example.org"},
])
def test_invalid_feature_properties_fail_without_write(project, properties):
    invalid = geography()
    invalid["features"][1]["properties"] = properties
    before = retained_files(project)
    with pytest.raises(ResearchError):
        api.create_dossier(project, "Bad capture", "Synthetic.", geography=invalid)
    assert retained_files(project) == before


def test_geography_bounds_and_unknown_members_fail_without_write(project):
    one = geography()["features"][0]
    large_coordinates = {"type": "Feature", "properties": {"label": "Long path"},
                         "geometry": {"type": "LineString", "coordinates": [[0, 0]] * 10001}}
    for invalid in (
        {"type": "FeatureCollection", "features": [one] * 201},
        {"type": "FeatureCollection", "features": [large_coordinates]},
        {"type": "FeatureCollection", "features": [one], "bbox": [0, 0, 1, 1]},
        {"type": "FeatureCollection", "features": [{**one, "id": "new-global-id"}]},
    ):
        before = retained_files(project)
        with pytest.raises(ResearchError):
            api.create_dossier(project, "Bad capture", "Synthetic.", geography=invalid)
        assert retained_files(project) == before


@pytest.mark.parametrize("update", [False, True])
def test_oversized_geography_records_fail_before_publishing_any_objects(project, update):
    identifier = api.create_dossier(project, "Synthetic note", "Original notes.")["dossier_id"]
    oversized = {"type": "FeatureCollection", "features": [
        {"type": "Feature", "geometry": {"type": "LineString", "coordinates": [[0, 0]] * 10000},
         "properties": {"label": "Synthetic route", "waypoint_labels": ["\0" * 500] * 10000}},
    ]}
    # Individually valid field lengths can exceed the object byte limit after JSON escaping.
    body = "\0" * 750000
    before = retained_files(project)
    snapshot = Repository(project).snapshot().digest
    with pytest.raises(ResearchError, match="exceeds the supported size"):
        if update:
            revise_record(project, "dossier", identifier, {"body": body, "geography": oversized})
        else:
            api.create_dossier(project, "Oversized synthetic note", body, geography=oversized)
    assert retained_files(project) == before
    assert Repository(project).snapshot().digest == snapshot
    assert api.get_dossier(project, identifier)["body"] == "Original notes."


@pytest.mark.parametrize("remove_from", ["collection", "feature", "geometry"])
def test_geojson_type_members_are_required_without_silent_inference(project, remove_from):
    value = geography()
    target = (value if remove_from == "collection" else value["features"][0]
              if remove_from == "feature" else value["features"][0]["geometry"])
    del target["type"]
    before = retained_files(project)
    with pytest.raises(ResearchError):
        api.create_dossier(project, "Missing discriminator", "Synthetic.", geography=value)
    assert retained_files(project) == before


def test_repository_refuses_dossier_schema_downgrade_after_geography_opt_in(project):
    identifier = api.create_dossier(project, "Place note", "Synthetic.", geography=geography())["dossier_id"]
    repository = Repository(project)
    snapshot = repository.snapshot()
    current = snapshot.latest(identifier, Dossier)
    values = current.model_dump(mode="json")
    values.update(schema_version="research-local/2", revision=2,
                  change={"change_kind": "correction", "reason": "Invalid schema downgrade.", "previous_revision": 1})
    del values["geography"]
    lower = Dossier.model_validate(values)
    before = retained_files(project)
    with pytest.raises(ResearchError, match="version 8"):
        repository.commit([lower], {}, snapshot)
    assert retained_files(project) == before


def test_geography_preview_conflicts_batches_and_stale_tokens_are_serializable(project):
    identifier = api.create_dossier(project, "Place note", "Synthetic.")["dossier_id"]
    before = retained_files(project)
    preview = api.prepare_record_revision(project, "dossier", identifier, base_revision=1, changes={"geography": geography()})
    assert preview["ready"] and preview["changes"]["geography"]["features"][0]["properties"]["label"] == "Synthetic gate"
    json.dumps(preview, allow_nan=False)
    assert retained_files(project) == before
    changed = revise_record(project, "dossier", identifier, {"geography": geography()})
    mine = geography()
    mine["features"][0]["properties"]["label"] = "Alternative gate"
    conflict = api.prepare_record_revision(project, "dossier", identifier, base_revision=1, changes={"geography": mine})
    assert conflict["conflicts"][0]["field"] == "geography"
    json.dumps(conflict, allow_nan=False)
    before = retained_files(project)
    with pytest.raises(ResearchConflictError):
        api.revise_record(project, "dossier", identifier, changes={"geography": None},
                          expected_snapshot=preview["current"]["snapshot"], expected_revision=1,
                          change_kind="correction", reason="Stale preview.")
    assert retained_files(project) == before
    operations = [{"kind": "dossier", "id": identifier, "expected_revision": 2,
                   "changes": {"geography": None}, "change_kind": "correction", "reason": "Remove draft path."}]
    batch = api.prepare_record_revisions(project, operations)
    json.dumps(batch, allow_nan=False)
    api.apply_record_revisions(project, batch["operations"], expected_snapshot=changed["snapshot"])
    assert api.get_record(project, "dossier", identifier)["record"]["geography"] is None


def test_structured_metadata_search_and_export_restore_preserve_geography(project, tmp_path):
    identifier = api.create_dossier(project, "Synthetic note", "Unrelated prose.", geography=geography())["dossier_id"]
    for term in ("Basalt", "Mira", "walking", "Departure", "wetland", "1924"):
        results = api.search(project, term, scope="dossiers", ensure_fresh=True)
        assert [item["record_id"] for item in results["hits"]] == [identifier]
    bundle = tmp_path / "research.tar.gz"
    api.export_archive(project, bundle)
    restored = tmp_path / "restored"
    api.restore_archive(bundle, restored)
    assert api.get_dossier(restored, identifier)["geography"] == api.get_dossier(project, identifier)["geography"]
    assert api.audit(restored)["ok"]


def test_cli_accepts_inline_file_and_null_geography_with_revision_guards(project, tmp_path):
    source = tmp_path / "geography.json"
    source.write_text(json.dumps(geography()), encoding="utf-8")
    status, output, errors = capture_research("dossier", "--project", str(project), "--title", "Synthetic location",
                                            "--body", "Synthetic prose.", "--geography", str(source))
    assert status == 0, errors
    identifier = json.loads(output)["dossier_id"]
    changed = copy.deepcopy(geography())
    changed["features"][0]["properties"]["label"] = "Reviewed archway"
    for number, value in ((1, json.dumps(changed)), (2, "null")):
        status, output, errors = capture_research("dossier", "--project", str(project), "--dossier-id", identifier,
            "--update", "--expected-revision", str(number), "--change-kind", "correction", "--reason", "Reviewed.",
            "--geography", value)
        assert status == 0, errors
    assert json.loads(output)["record"]["geography"] is None


def test_existing_http_dossier_endpoint_preserves_structured_geography(project):
    handler = make_handler(project, research_dir=project)
    handler.refresh()
    with LoopbackServer(handler) as server:
        payload = {"title": "Synthetic location", "body": "Synthetic notes.", "geography": geography(),
                   "research_token": research_context_token(project)}
        response = server.request("/api/research-dossier", payload=payload, headers={"Origin": server.base})
        assert response.status == 200 and response.json["ok"]
        identifier = response.json["dossier_id"]
        read = server.request("/api/research/dossiers?id=" + identifier)
        assert read.status == 200 and read.json["geography"]["features"][0]["properties"]["label"] == "Synthetic gate"
