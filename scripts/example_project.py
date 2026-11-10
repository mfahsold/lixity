"""Create an editable synthetic project through the normal Lixity APIs.

No browser fixtures, screenshots or publication wrappers belong to this module.
"""

import argparse
import json
import re
import shutil
import sys
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory

BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR / "src"))
DEMO_MANUSCRIPT = BASE_DIR / "samples/first-look.md"


def manuscript_title(text: str, fallback: str = "Manuscript") -> str:
    """Use the selected manuscript's title, independently of its language."""
    heading = re.search(r"(?m)^#\s+(.+?)\s*$", text)
    return heading[1] if heading else fallback


def reviewed_visual_sources(asset_dir: Path | None = None) -> list[tuple[dict, bytes]]:
    """Fail closed unless the two reviewed visual references match their manifest."""
    from lixity.research.images import validate_image

    asset_dir = asset_dir or BASE_DIR / "docs/assets/research"
    manifest = json.loads((asset_dir / "sources.json").read_text(encoding="utf-8"))
    expected = {"hamburg-free-port-1900.jpg", "hamburg-harbour-1890-1900.jpg"}
    if {item["filename"] for item in manifest["sources"]} != expected or len(manifest["sources"]) != 2:
        raise ValueError("The reviewed research visual manifest must identify the two approved JPEGs")
    sources = []
    for item in manifest["sources"]:
        content = (asset_dir / item["filename"]).read_bytes()
        if sha256(content).hexdigest() != item["sha256"]:
            raise ValueError(f"Image differs from its reviewed SHA-256: {item['filename']}")
        image = validate_image(content, filename=item["filename"])
        if (image["width"], image["height"]) != (item["width"], item["height"]):
            raise ValueError(f"Image differs from its reviewed dimensions: {item['filename']}")
        sources.append((item, content))
    return sources


def _populate(work_dir: Path) -> dict:
    from lixity.research import api as research_api

    research_proj = work_dir / "research-demo"
    manuscript_bytes = DEMO_MANUSCRIPT.read_bytes()
    research_api.init(research_proj, title=manuscript_title(manuscript_bytes.decode("utf-8")), language="en")
    (research_proj / "lixity.toml").write_text(
        'manuscript = "harbour-manuscript.md"\nlanguage = "en"\n'
        'author_name = "Example Author"\n\n[characters.Mara]\n\n[characters.Ivo]\n\n[characters.Hansen]\n',
        encoding="utf-8",
    )
    source_text = """## Section 1: Port Authority Log – October 1923

At ten ten on the evening of October 14, 1923, the night watchman reported two unidentified figures attempting to force the external lock at the eastern gate of Warehouse 4.
The autumn mist obscured the water beyond the quay lamps. The figures ran towards the basin when challenged. No customs seals on the inner warehouse doors were broken.

## Preliminary entry: dictated before the transfer

Officer Hansen opened the crate beside the gate and found forty bundles of untaxed tobacco. The abandoned crate was prepared for transfer to the customs station at dawn.

## Follow-up: station inspection, October 15

Correction to the preliminary entry: the crate was first opened at the customs station at six ten. The count of forty tobacco bundles belongs to that inspection, not to the quay. Hansen signed this amendment after checking the transfer sheet.

A loose base board shifted while the crate was moved away from the drain. One lid plank cracked. The damaged lid was bound to prevent spillage; opening was deferred until arrival at the station. Mara identified the blood on the lid as hers. A blue label fragment and the older board number seventeen were retained separately.

## Witness limits

The watchman saw the two figures leave towards the basin. Mara saw a launch light and heard its engine after the light disappeared. Neither witness saw a crate loaded aboard, identified passengers or recovered a tool. The proposed crowbar and launch connection remain unconfirmed.
"""
    customs_file = work_dir / "customs_log_1923.txt"
    customs_file.write_text(source_text, encoding="utf-8")
    customs_res = research_api.ingest(
        research_proj,
        customs_file,
        title="Port Authority Customs Log (synthetic)",
        context={
            "genre": "Official Customs Register",
            "created_period": "1923",
            "depicted_period": "October 1923",
            "place": "Hamburg Free Port Zone",
            "perspective": "Third-Person Administrative",
            "provenance_note": "Synthetic demonstration text and Zotero identity metadata; not an archival document or verified historical account. "
                               "No live Zotero connection was used. The retained bytes remain available independently of Zotero.",
            "external_reference": {"provider": "zotero", "server_id": "synthetic-offline-example", "library": "users/0",
                                   "item_key": "DEMOLOG1", "attachment_key": "DEMOTXT1", "item_version": 1, "attachment_version": 1},
            "tags": ["Customs", "Warehouse 4"],
        },
        allow_retention=True,
    )
    weather_file = work_dir / "harbor_weather_notes.txt"
    weather_file.write_text(
        "## Harbor Weather Notes\n\n"
        "Mist covered the harbor before sunrise. A light wind carried drizzle "
        "across the eastern pier, and the quay lamps remained lit.\n\n"
        "## Setting Observations\n\n"
        "Wet cobblestones reflect a lamp more clearly than a face. From the eastern gate, "
        "the lamp lights the lock and crate but leaves the water in darkness. An engine "
        "can remain audible after the launch light disappears. This does not establish a route or boarding.\n\n"
        "## Office notebook: two entries for cart seventeen\n\n"
        "Mara copied a dispatch at eight in the evening. The ledger also lists cart seventeen "
        "as returned at six forty that evening, without a receiving signature. The earlier "
        "entry is squeezed into the margin. Reused boards, a copied number or a later ledger "
        "entry could explain the discrepancy; the notebook does not identify a culprit.\n\n"
        "## Reference limits\n\n"
        "These invented notes support a fictional scene; they are not historical evidence. "
        "The circa-1900 map and 1890–1900 harbour view are setting references. They cannot "
        "establish the lamp position, weather, warehouse layout or journey on this invented night in 1923.\n",
        encoding="utf-8",
    )
    weather_res = research_api.ingest(
        research_proj,
        weather_file,
        title="Harbor Weather Notes (synthetic)",
        context={
            "genre": "Fictional setting and office notes",
            "place": "Imaginary harbor",
            "provenance_note": "Synthetic demonstration text; not an archival document or verified historical account.",
            "tags": ["Weather", "Setting"],
        },
        allow_retention=True,
    )
    research_api.reindex(research_proj)
    search_res = research_api.search(research_proj, "warehouse customs", limit=1)
    matches = search_res["hits"]
    if not matches:
        raise RuntimeError("Synthetic research source must produce a real passage citation")

    def retained_passage(source: dict, phrase: str) -> str:
        return next(passage["id"] for passage in source["passages"] if phrase in passage["verbatim"])

    customs_source = research_api.get_source(research_proj, customs_res["source_id"])
    weather_source = research_api.get_source(research_proj, weather_res["source_id"])
    passage_id = retained_passage(customs_source, "night watchman reported two unidentified figures")
    early_inspection = retained_passage(customs_source, "opened the crate beside the gate")
    corrected_inspection = retained_passage(customs_source, "crate was first opened at the customs station")
    damaged_lid = retained_passage(customs_source, "opening was deferred until arrival")
    witness_limits = retained_passage(customs_source, "Neither witness saw a crate loaded aboard")
    weather_passage = retained_passage(weather_source, "Mist covered the harbor")
    visibility_passage = retained_passage(weather_source, "An engine can remain audible")
    receipt_passage = retained_passage(weather_source, "ledger also lists cart seventeen")

    # Read-only browser responses below are serialized from this disposable,
    # API-created archive. The dashboard itself is the real controls UI.
    dossier_res = research_api.create_dossier(
        research_proj,
        title="Warehouse 4 case notes",
        body="Fictional case file for the six-chapter harbour story. Times and testimony belong to the invented case.\n\n"
        "## Timeline\n\n"
        "| Time | Working sequence | Status |\n| --- | --- | --- |\n"
        "| 14 October, 18:40 | Cart seventeen entered as returned | Receiving signature missing |\n"
        "| 20:00 | Mara copies the dispatch | Crate not seen by Mara |\n"
        "| 22:10 | Watchman calls for customs | Two figures leave towards the basin |\n"
        "| Before dawn | Cracked lid bound; crate transferred | Contents still unknown to Mara |\n"
        "| 15 October, 06:10 | Station inspection counts tobacco | Corrected log entry |\n\n"
        "## Accounts to compare\n\n"
        "The preliminary customs entry places the opening beside the gate. The signed follow-up "
        "moves it to the station. Preserve both passages: the correction changes the author’s "
        "working interpretation, not the retained earlier wording. The launch is heard, but boarding is not observed.\n\n"
        "## Open Questions\n\n"
        "- Who entered the return before Mara copied the dispatch?\n"
        "- Does seventeen identify this crate, a cart, or a reused board?\n"
        "- Why did Ivo reach for the label, and who told him to keep the gate clear?\n"
        "- Is the blank receiving line an omission or a deliberate removal?\n\n"
        "## Scene decisions\n\n"
        "Keep the crate closed on the quay. Let handling account for the blood and cracked plank. "
        "Introduce the number before the office scene; end with the missing signature rather than naming a culprit.\n\n"
        "## Evidence trail\n\nThese are explicit author associations, not automatic fact checks.\n\n"
        "```mermaid\nflowchart LR\n subgraph Retained evidence\n  P[Customs log passage]\n end\n"
        " P --> C[Authored claim]\n C --> Q[Manuscript quotation]\n C --> D[Author decision]\n```\n\n"
        "## Historical map\n\nCirca-1900 reference; not evidence of the invented 1923 incident.\n\n"
        "## Historical harbour view\n\n1890–1900 photochrom reference; not a photograph of the fictional event.",
        tags=["Warehouse", "Timeline"],
        evidence_ids=[passage_id, early_inspection, corrected_inspection, damaged_lid, receipt_passage],
        geography=json.loads((BASE_DIR / "docs/research/examples/harbour-geography.json").read_text(encoding="utf-8")),
    )
    weather_dossier = research_api.create_dossier(
        research_proj,
        title="Harbor setting notes",
        body="Fictional atmosphere and sightline notes. The weather and setting are fictional examples, not verified historical claims.\n\n"
        "## Weather\n\nMist closes the water view before it silences the launch. Rain has begun after the office closes; "
        "the covered cart seat can register as a small unexplained detail. Wet boots and a cold stove carry the night into the office scene.\n\n"
        "## Visibility and sound\n\n"
        "| Position | Available impression | Limit |\n| --- | --- | --- |\n"
        "| Quay lamp | Lock scratches, label, blood | Does not illuminate a face across the basin |\n"
        "| Eastern gate | Launch light, then engine | No witnessed boarding or cargo transfer |\n"
        "| Office desk | Paper edges, ink, ledger entries | Similar paper does not identify a sender |\n\n"
        "## Scene Planning\n\nUse the long harbour sentences before the short rescue beats. "
        "Keep Ivo’s movements visible without supplying his thoughts. Mara tries the label against her receipt; "
        "the edges do not fit. The later ledger discrepancy must therefore remain a question, not a solved identification.\n\n"
        "## Revision question\n\n"
        "Does chapter 2's shorter rhythm fit the action? Compare “A board moved. Mara turned.” with "
        "chapter 1's harbour description. Short sentences separate the physical actions; the longer opening "
        "lets Mara notice the quay before she has to act. This is an authored contrast, not a model's finding of good pace.\n\n"
        "A useful review can end with keeping those beats. If the passage feels mechanically chopped when read aloud, "
        "try joining an action to its consequence and compare the reading again. Neither shorter sentences nor "
        "matching the manuscript median is a goal. The measurement identifies what was counted; the author decides what works.\n\n"
        "## Reference boundaries\n\nThe historical map and harbour image establish their own dated visual context. "
        "The approximate walking and driving sketches are author-entered examples, not calculated routes or sightlines.\n\n"
        "## Next research questions\n\nWhich details of customs procedure need historical checking before a longer novel uses them? "
        "Could an actual warehouse layout support these movements? Leave both questions open in this fictional demonstration.\n\n"
        "## Reader introduction\n\nThe harbour in this story is an invented place within a real city's visual history. "
        "The quay, office and Warehouse 4 belong to the fiction. The old map and harbour view below offer a wider setting, "
        "rather than a plan of the characters' movements.\n\n"
        "## Reader weather\n\nLight reaches the lock more clearly than the water. Beyond the quay lamp, a sound may remain "
        "distinct after its source has disappeared into the mist. Keep that difference in mind as the witnesses describe the night.\n\n"
        "## Reader witness limits\n\nSeeing a light, hearing an engine and seeing someone board a boat are different observations. "
        "The three quay chapters leave gaps between them. The companion does not fill those gaps with an unseen journey.\n\n"
        "## Reader final clue\n\nA blank signature is an absence, not a name. The two ledger entries, reused board and torn paper "
        "leave several possible connections. The morning handover preserves the question instead of identifying a culprit.",
        tags=["Weather", "Setting"],
        evidence_ids=[weather_passage, visibility_passage, receipt_passage, witness_limits],
    )
    image_resources = {}
    for item, visual_bytes in reviewed_visual_sources():
        dossier_current = research_api.get_dossier(research_proj, dossier_res["dossier_id"])
        caption_title = item["title"]
        if item["created_period"].casefold() not in caption_title.casefold():
            caption_title += f" ({item['created_period']})"
        credit = item["creator"] or "Library of Congress, Photochrom Print Collection"
        attached = research_api.attach_dossier_image(
            research_proj, dossier_res["dossier_id"], visual_bytes, filename=item["filename"],
            expected_snapshot=dossier_current["snapshot"], expected_revision=dossier_current["revision"],
            allow_retention=True, alt=item["alt"], title=item["title"],
            section="Historical map" if item["id"] == "hamburg-free-port-1900" else "Historical harbour view",
            caption=f"{caption_title}. {credit}. Public domain.",
            context={"genre": item["genre"], "created_period": item["created_period"], "place": item["place"],
                     "origin_url": item["origin_url"], "tags": ["Historical visual reference"],
                     "provenance_note": f"{item['provenance_note']}\nCredit: {item['credit']}\n"
                                        f"Rights: {item['rights']}\nCatalogue: {item['source_url']}"},
        )
        captured_id = attached["capture"]["source_id"]
        image = next(image for image in attached["images"] if image["source_id"] == captured_id)
        image_resources[image["url"]] = {"media_type": "image/jpeg", "asset_path": "docs/assets/research/" + item["filename"]}
    research_api.create_claim(
        research_proj,
        title="Reformed customs seal",
        statement="The watchman reports intact seals on the inner warehouse doors, despite scratches on the external lock.",
        confidence="hypothetical", time_period="1922–1924", place="Hamburg Free Port Zone",
        dossier_id=dossier_res["dossier_id"],
    )
    research_api.create_claim(
        research_proj,
        title="Harbour tour research notes",
        statement="A future research visit could check the fictional warehouse layout against dated plans and surviving buildings.",
        confidence="hypothetical", time_period="present day", place="Hamburg",
    )
    claim_res = research_api.create_claim(
        research_proj,
        title="Attempted warehouse entry",
        statement="The customs log describes an attempted entry at Warehouse 4 in October 1923.",
        confidence="evidenced", time_period="1923", place="Hamburg Free Port Zone",
        actors=["Night watchman", "Customs officers"], dossier_id=dossier_res["dossier_id"],
    )
    research_api.link_evidence(
        research_proj, claim_id=claim_res["claim_id"], passage_id=passage_id,
        relation="supports", rationale="The initial fictional log reports the attempted entry; it does not identify the people.",
    )
    inspection = research_api.create_claim(
        research_proj, title="Where the crate was opened",
        statement="Hansen opened the crate on the quay before it was transferred to the customs station.",
        confidence="hypothetical", time_period="1923-10-14", place="Eastern quay",
        dossier_id=dossier_res["dossier_id"],
    )
    research_api.link_evidence(
        research_proj, claim_id=inspection["claim_id"], passage_id=early_inspection,
        relation="supports", rationale="The preliminary entry places the inspection beside the gate.",
    )
    research_api.link_evidence(
        research_proj, claim_id=inspection["claim_id"], passage_id=corrected_inspection,
        relation="contradicts", rationale="The signed correction explicitly places the first opening at the station.",
    )
    research_api.revise_record(
        research_proj, "claim", inspection["claim_id"], expected_revision=1,
        changes={"statement": "The crate was first opened at the customs station after dawn; the preliminary quay inspection entry was corrected.",
                 "confidence": "evidenced", "time_period": "1923-10-15", "place": "Customs station"},
        change_kind="supersession", reason="Prefer the signed follow-up while preserving the earlier interpretation and its conflicting citations.",
    )
    research_api.link_evidence(
        research_proj, claim_id=inspection["claim_id"], passage_id=corrected_inspection,
        relation="supports", rationale="This citation is explicitly linked to the revised interpretation, not silently transferred from version 1.",
    )
    lid = research_api.create_claim(
        research_proj, title="The cracked lid delayed inspection",
        statement="The damaged lid was bound for transport, and opening was deferred until the station.",
        confidence="evidenced", time_period="1923-10-14 / 1923-10-15", place="Eastern quay",
        dossier_id=dossier_res["dossier_id"],
    )
    research_api.link_evidence(
        research_proj, claim_id=lid["claim_id"], passage_id=damaged_lid, relation="supports",
        rationale="The follow-up records the cracked plank, binding and deferred opening in the fictional sequence.",
    )
    receipt = research_api.create_claim(
        research_proj, title="The missing receiving signature",
        statement="Cart seventeen appears as returned before the dispatch Mara copied; the missing signature leaves the connection unresolved.",
        confidence="hypothetical", time_period="1923-10-14", place="Warehouse office",
        actors=["Mara", "Foreman"], dossier_id=dossier_res["dossier_id"],
    )
    research_api.link_evidence(
        research_proj, claim_id=receipt["claim_id"], passage_id=receipt_passage, relation="contextualizes",
        rationale="The fictional working notebook keeps several explanations open; it does not identify a culprit.",
    )
    research_api.create_claim_relation(
        research_proj, lid["claim_id"], inspection["claim_id"], relation="causes",
        rationale="Author interpretation for the scene: securing the damaged lid moves the inspection to the station. This link does not verify causality.",
    )
    manuscript = research_proj / "harbour-manuscript.md"
    manuscript.write_bytes(manuscript_bytes)
    manuscript_hash = sha256(manuscript_bytes).hexdigest()
    for claim_id, revision, query in (
        (claim_res["claim_id"], 1, "Someone had tried the eastern gate of Warehouse 4."),
        (claim_res["claim_id"], 1, "Fresh scratches crossed the lock"),
        (lid["claim_id"], 1, "One plank cracked."),
        (inspection["claim_id"], 2, "The crate was first opened at the customs station at six ten."),
        (receipt["claim_id"], 1, "Cart seventeen: returned, six forty in the evening."),
    ):
        anchor = research_api.resolve_manuscript_anchor(research_proj, manuscript, query=query)
        research_api.link_manuscript_claim(
            research_proj, manuscript, claim_id, claim_revision=revision,
            selection={key: anchor[key] for key in ("start_line", "end_line", "paragraph_sha256", "start", "end", "quote")},
            expected_project_id=anchor["project_id"], expected_snapshot=anchor["snapshot"],
            expected_source_sha256=manuscript_hash, allow_retention=True,
            note="Explicit author association in a synthetic manuscript; not evidence that the fictional incident happened.",
        )
    research_api.revise_record(
        research_proj, "claim", claim_res["claim_id"], expected_revision=1,
        changes={"statement": "The customs log reports an attempted entry at Warehouse 4 in October 1923; the implement, people and launch connection remain unconfirmed."},
        change_kind="correction", reason="Distinguish the reported attempt from unobserved details; preserve both manuscript associations at their reviewed version 1.",
    )
    research_api.link_evidence(
        research_proj, claim_id=claim_res["claim_id"], passage_id=passage_id,
        relation="supports", rationale="The current wording describes the report, not independent verification of this invented incident.",
    )
    research_api.link_evidence(
        research_proj, claim_id=claim_res["claim_id"], passage_id=witness_limits,
        relation="qualifies", rationale="The witnesses do not establish a weapon, passengers or the launch connection.",
    )
    research_api.record_decision(
        research_proj, title="Keep the inspection at dawn",
        rationale="Use the signed station correction while preserving the contradictory preliminary entry in the research record.",
        claim_id=inspection["claim_id"], dossier_ids=[dossier_res["dossier_id"]],
        impact_on_plot="The crate stays closed through the quay scenes; the formal note reveals the tobacco after transfer.",
    )
    research_api.record_decision(
        research_proj, title="Move the discovery scene",
        rationale="Let Mara arrive before customs so her handling changes the physical evidence; this is an explicit fictional staging choice.",
        claim_id=claim_res["claim_id"], dossier_ids=[dossier_res["dossier_id"], weather_dossier["dossier_id"]],
        deviation_from_fact=True,
        impact_on_plot="The cut, cracked plank and label make her an involved witness rather than a distant observer.",
    )
    research_api.record_decision(
        research_proj, title="Leave the receiving signature blank",
        rationale="The two ledger entries and reused board support a question, not a solved identification.",
        claim_id=receipt["claim_id"], dossier_ids=[dossier_res["dossier_id"], weather_dossier["dossier_id"]],
        impact_on_plot="Mara stops the foreman closing the book; the unresolved receiving line ends the story.",
    )
    from lixity.config import prepare_project_settings

    current_case = research_api.get_dossier(research_proj, dossier_res["dossier_id"])
    prepare_project_settings(research_proj, {
        "site_publications": {"readers": {
            "title": "Warehouse 4 — a reader's companion",
            "introduction": "Keep this context beside the story. Choose the last chapter you have finished to reveal the notes prepared for that point.",
            "entries": [
                {"dossier_id": weather_dossier["dossier_id"], "revision": 1, "section": "Reader introduction", "title": "The harbour around the story", "reveal_after_chapter": 0},
                {"dossier_id": dossier_res["dossier_id"], "revision": current_case["revision"], "section": "Historical map", "title": "A map from another time", "reveal_after_chapter": 0},
                {"dossier_id": dossier_res["dossier_id"], "revision": current_case["revision"], "section": "Historical harbour view", "title": "The harbour in colour", "reveal_after_chapter": 0},
                {"dossier_id": weather_dossier["dossier_id"], "revision": 1, "section": "Reader weather", "title": "Light and sound", "reveal_after_chapter": 1},
                {"dossier_id": weather_dossier["dossier_id"], "revision": 1, "section": "Reader witness limits", "title": "What a witness can tell", "reveal_after_chapter": 3},
                {"dossier_id": weather_dossier["dossier_id"], "revision": 1, "section": "Reader final clue", "title": "The receiving signature", "reveal_after_chapter": 6},
            ],
        }},
        "dossier_collections": {
            "case_records": {
                "name": "Warehouse Case Files",
                "dossier_ids": [dossier_res["dossier_id"]],
            },
            "setting": {
                "name": "Atmosphere & Geography",
                "dossier_ids": [weather_dossier["dossier_id"]],
            },
        },
        "register_profiles": {
            "harbour_investigation": {
                "asl": [12.0, 22.0],
                "dialog_pct": [35.0, 65.0],
            },
            "quay_action": {
                "asl": [8.0, 16.0],
                "staccato_pct": [20.0, 50.0],
            },
        },
        "chapter_registers": {
            "1": "harbour_investigation",
            "2": "quay_action",
            "3": "harbour_investigation",
        },
    }).commit()
    return {"project": research_proj, "image_resources": image_resources,
            "primary_claim_id": claim_res["claim_id"]}


def create_example_project(destination: Path) -> dict:
    """Create a new ordinary project; never overwrite an existing destination."""
    destination = Path(destination)
    if destination.exists() or destination.is_symlink():
        raise FileExistsError(f"Example destination already exists: {destination}")
    with TemporaryDirectory(prefix="lixity-example-project-") as directory:
        result = _populate(Path(directory))
        shutil.copytree(result["project"], destination)
    return {**result, "project": destination}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True,
                        help="New project directory; existing destinations are refused")
    options = parser.parse_args()
    result = create_example_project(options.output)
    print(f"Created editable example project: {result['project']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
