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
RESEARCH_ASSETS = BASE_DIR / "docs/assets/research"
WATCHMAN_STATEMENT = (
    "For the time being, all I can say is that there were two people by the gate. "
    "When I called, they ran towards the basin."
)


def manuscript_title(text: str, fallback: str = "Manuscript") -> str:
    """Use the selected manuscript's title, independently of its language."""
    heading = re.search(r"(?m)^#\s+(.+?)\s*$", text)
    return heading[1] if heading else fallback


def reviewed_visual_sources(asset_dir: Path | None = None) -> list[tuple[dict, bytes]]:
    """Fail closed unless the two reviewed visual references match their manifest."""
    from lixity.research.images import validate_image

    asset_dir = asset_dir or RESEARCH_ASSETS
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
    from lixity.speech_direction import direction_state, save_direction

    research_proj = work_dir / "research-demo"
    manuscript_bytes = DEMO_MANUSCRIPT.read_bytes()
    manuscript_text = manuscript_bytes.decode("utf-8")
    if any(sentence not in manuscript_text for sentence in WATCHMAN_STATEMENT.split(". ")):
        raise ValueError("The reviewed synthetic recording must match the watchman’s dialogue")
    research_api.init(research_proj, title=manuscript_title(manuscript_text), language="en")
    (research_proj / "lixity.toml").write_text(
        'manuscript = "harbour-manuscript.md"\nlanguage = "en"\n'
        'author_name = "Example Author"\n\n[characters.Mara]\n\n[characters.Ivo]\n\n[characters.Hansen]\n\n'
        '[motif_regexes]\n"For the time being" = \'\\bfor the time being\\b\'\n\n'
        '[audio]\nschema_version = "lixity-audio-settings/5"\nselected = "narrator"\n\n'
        '[audio.profiles.narrator]\nname = "Narrator"\nengine = "qwen3"\n'
        'voice = "Ryan"\nlanguage = "en"\nspeed = 1.0\nparagraph_pause = 0.65\nscene_pause = 1.2\n',
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

    witness_file = work_dir / "watchman-reconstruction.txt"
    witness_file.write_text(
        "## Gate statement\n\n" + WATCHMAN_STATEMENT + "\n\n"
        "## Scope of the statement\n\n"
        "The watchman describes people leaving in the direction of the basin. He gives no name, "
        "boat identification or witnessed boarding. Mara separately describes a light and an engine.\n",
        encoding="utf-8",
    )
    witness_source = research_api.ingest(
        research_proj, witness_file, title="Watchman’s gate statement (synthetic transcript)",
        context={
            "genre": "Fictional witness transcript", "depicted_period": "October 1923",
            "place": "Eastern gate", "perspective": "Night watchman",
            "provenance_note": "Adapted from the authored dialogue in Questions on the Quay. The companion clip "
                               "uses synthetic narration of these words. The interview and its speaker are fictional.",
            "tags": ["Witness", "Transcript"],
        },
        allow_retention=True,
    )
    transfer_file = work_dir / "transfer-and-receipt-notes.txt"
    transfer_file.write_text(
        "## Transfer counterfoil\n\n"
        "The transfer sheet records handover after the lid was secured. The crate was handed over still closed. "
        "The station count belongs to the first opening at 06:10 on 15 October. Departure time and route are absent "
        "from the retained entries.\n\n"
        "## Receipt and ledger comparison\n\n"
        "The office register gives a return entry at 18:40 and a dispatch copied at 20:00 on 14 October. "
        "Both use seventeen. The label and receipt are cut from similar blue stock, but their torn edges do not fit. "
        "These observations leave the crate, reused board, and cart identities unresolved.\n\n"
        "## Morning handover\n\n"
        "The morning review preserves the line without a receiving signature. Mara can attest to copying the "
        "dispatch number. The receiving line leaves the carrier unidentified.\n",
        encoding="utf-8",
    )
    transfer_source = research_api.ingest(
        research_proj, transfer_file, title="Transfer and receipt notes (synthetic)",
        context={
            "genre": "Fictional transfer and office record", "depicted_period": "October 1923",
            "place": "Eastern quay, station and office",
            "provenance_note": "Author-created notes for the Warehouse 4 example. The time labels and observations "
                               "describe the fictional record. The exhibit images are authored facsimiles.",
            "tags": ["Transfer", "Receipt", "Warehouse 4"],
        },
        allow_retention=True,
    )
    witness_detail = research_api.get_source(research_proj, witness_source["source_id"])
    transfer_detail = research_api.get_source(research_proj, transfer_source["source_id"])
    watchman_passage = retained_passage(witness_detail, "When I called, they ran towards the basin")
    transfer_passage = retained_passage(transfer_detail, "The crate was handed over still closed")
    comparison_passage = retained_passage(transfer_detail, "their torn edges do not fit")
    morning_passage = retained_passage(transfer_detail, "The receiving line leaves the carrier unidentified")

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
        "| 15 October, 06:10 | Station inspection counts tobacco | Corrected log entry |\n"
        "| Morning | Mara limits her account to the dispatch she copied | Receiver still unidentified |\n\n"
        "## Accounts to compare\n\n"
        "The preliminary customs entry places the opening beside the gate. The signed follow-up "
        "moves it to the station. Preserve both passages: the correction changes the author’s "
        "working interpretation, not the retained earlier wording. The launch is heard, but boarding is not observed.\n\n"
        "## Custody and release of information\n\n"
        "The first three chapters stay with the quay witnesses. The formal note records the crate’s first opening "
        "at the station. The receipt and ledger then raise a separate office question. Keep the times in the "
        "fictional counterfoil beside the scene order; the archive chronology groups dated claims by day.\n\n"
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
    exhibits = research_api.create_dossier(
        research_proj, title="Warehouse 4 exhibit book",
        body="Authored facsimiles and witness reconstruction for the fictional Warehouse 4 case. "
        "Each exhibit helps inspect a particular limit of the case record.\n\n"
        "## Watchman’s statement\n\n"
        "Synthetic narration of dialogue from chapter 3. The watchman reports two figures and their direction "
        "of flight. The route beyond the basin remains open.\n\n"
        f"**Transcript.** “{WATCHMAN_STATEMENT}”\n\n"
        "## Transfer counterfoil\n\n"
        "The transfer records the closed crate moving from the quay to the station and places the count at the "
        "station. The sheet gives neither an exact departure time nor the cart’s path. Use the corresponding "
        "claim and the signed correction in the case notes to compare the location of first opening.\n\n"
        "## Dispatch receipt\n\n"
        "Mara can say she copied seventeen at eight. The receiving line is empty. The fictional receipt shows "
        "that limited act of copying and leaves the identity of the load unresolved.\n\n"
        "## Office ledger\n\n"
        "Read the 18:40 return against the 20:00 dispatch. Both carry seventeen. An empty signature leaves the "
        "carrier unidentified, and the register leaves the relationship between the crate and the cart unresolved.",
        evidence_ids=[watchman_passage, transfer_passage, comparison_passage, morning_passage],
        tags=["Warehouse", "Facsimiles", "Witness"],
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
    exhibit_assets = (
        (
            "warehouse-4-watchman.mp4", "290bff73d4844591b1f63f53a2857cd20eddc9f0cb0f62d4fce12a0f2ed1cbd4",
            "Watchman’s statement", "Gate statement (synthetic reconstruction)",
            "Captioned reconstruction of the fictional watchman reporting two figures and their direction of flight.",
            "Synthetic narration of the chapter 3 dialogue. Read the matching transcript in this section.",
            "Authored reconstruction voiced with the local Qwen Aiden preset and captioned in FilmCraft. "
            "The transcript preserves the stated direction toward the basin.",
        ),
        (
            "warehouse-4-receipt.png", "ad16a26f1f48b613137d306ff093ded2db8514ad382bb80b84623ca3729d77c7",
            "Dispatch receipt", "Dispatch receipt (authored facsimile)",
            "Fictional dispatch receipt dated 14 October 1923. Mara entered seventeen at 20:00. The receiving line is blank.",
            "Mara’s copied dispatch. The blank line leaves the receiver unknown.",
            "Authored facsimile of a fictional document. Its details are limited to the dispatch copied by Mara.",
        ),
        (
            "warehouse-4-ledger.png", "cad6f1f0f01c4049c533258d9365e71f06e8705c3490e629c555d6ebdb009ff8",
            "Office ledger", "Office ledger (authored facsimile)",
            "Fictional ledger dated 14 October 1923. Cart 17 returns at 18:40. A dispatch marked 17 follows at 20:00. The receiving line is blank.",
            "The return predates the copied dispatch. The missing receiving signature leaves the carrier unidentified.",
            "Authored facsimile of the fictional office register. The shared number leaves the cart and crate identities unresolved.",
        ),
    )
    current_exhibits = research_api.get_dossier(research_proj, exhibits["dossier_id"])
    exhibit_snapshot, exhibit_revision = current_exhibits["snapshot"], current_exhibits["revision"]
    for filename, digest, section, title, alt, caption, provenance in exhibit_assets:
        content = (RESEARCH_ASSETS / filename).read_bytes()
        if sha256(content).hexdigest() != digest:
            raise ValueError(f"Exhibit differs from its reviewed SHA-256: {filename}")
        attached = research_api.attach_dossier_media(
            research_proj, exhibits["dossier_id"], content,
            filename=filename, expected_snapshot=exhibit_snapshot,
            expected_revision=exhibit_revision, allow_retention=True,
            section=section, title=title, alt=alt, caption=caption,
            context={"genre": "Fictional scene exhibit", "depicted_period": "October 1923",
                     "provenance_note": provenance, "tags": ["Synthetic exhibit", "Warehouse 4"]},
        )
        exhibit_snapshot, exhibit_revision = attached["snapshot"], attached["latest_revision"]
        captured_id = attached["capture"]["source_id"]
        resource = next(item for item in [*attached["images"], *attached["media"]]
                        if item["source_id"] == captured_id)
        image_resources[resource["url"]] = {"media_type": resource["media_type"],
                                             "asset_path": "docs/assets/research/" + filename}
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
    witness_claim = research_api.create_claim(
        research_proj, title="The watchman’s view ends at the basin",
        statement="The watchman reports two people by the eastern gate leaving towards the basin. "
                  "The fictional statement establishes the direction he reports and leaves their later movements unknown.",
        confidence="evidenced", time_period="1923-10-14", place="Eastern gate",
        actors=["Night watchman"], dossier_id=exhibits["dossier_id"],
    )
    research_api.link_evidence(
        research_proj, claim_id=witness_claim["claim_id"], passage_id=watchman_passage, relation="supports",
        rationale="The retained transcript gives the witness’s limited description of the figures and direction.",
    )
    research_api.link_evidence(
        research_proj, claim_id=witness_claim["claim_id"], passage_id=witness_limits, relation="qualifies",
        rationale="The customs record separates the watchman’s observation from Mara’s report of light and sound.",
    )
    custody = research_api.create_claim(
        research_proj, title="Custody passes to the customs station",
        statement="The transfer sheet records handover of the closed crate. The signed inspection counts the "
                  "contents at the station at 06:10. The cart’s precise route remains unknown.",
        confidence="evidenced", time_period="1923-10-15", place="Eastern quay and customs station",
        actors=["Hansen"], dossier_id=exhibits["dossier_id"],
    )
    research_api.link_evidence(
        research_proj, claim_id=custody["claim_id"], passage_id=transfer_passage, relation="supports",
        rationale="The fictional counterfoil records the handover between the two locations and leaves the departure time open.",
    )
    morning = research_api.create_claim(
        research_proj, title="The morning review leaves the carrier unidentified",
        statement="The missing signature leaves the carrier unidentified. Mara’s account establishes the number she copied. "
                  "The shared paper and number leave the load’s identity open.",
        confidence="evidenced", time_period="1923-10-15", place="Warehouse office",
        actors=["Mara", "Hansen", "Foreman"], dossier_id=exhibits["dossier_id"],
    )
    research_api.link_evidence(
        research_proj, claim_id=morning["claim_id"], passage_id=morning_passage, relation="supports",
        rationale="The fictional review records what Mara accepts responsibility for and preserves the signature gap.",
    )
    research_api.link_evidence(
        research_proj, claim_id=morning["claim_id"], passage_id=comparison_passage, relation="contextualizes",
        rationale="The observations explain why the dispatch receipt and ledger number still admit several interpretations.",
    )
    research_api.create_claim_relation(
        research_proj, lid["claim_id"], inspection["claim_id"], relation="causes",
        rationale="Author interpretation for the scene: securing the damaged lid moves the inspection to the station. This link does not verify causality.",
    )
    manuscript = research_proj / "harbour-manuscript.md"
    manuscript.write_bytes(manuscript_bytes)
    manuscript_hash = sha256(manuscript_bytes).hexdigest()
    direction = direction_state(research_proj, manuscript)
    witness_passage = next(passage for passage in direction["passages"]
                           if passage["chapter"] == 3 and "When I called, they ran towards the basin." in passage["text"])
    save_direction(
        research_proj, manuscript,
        {"anchor": witness_passage["anchor"], "instructions": "Keep the witness matter-of-fact. Let the answer end plainly.",
         "pause_after": 0.8},
        expected_source_sha256=direction["source_sha256"], expected_settings_sha256=direction["settings_sha256"],
        expected_direction_sha256=direction["direction_sha256"],
    )
    for claim_id, revision, query in (
        (claim_res["claim_id"], 1, "Someone had tried the eastern gate of Warehouse 4."),
        (claim_res["claim_id"], 1, "Fresh scratches crossed the lock"),
        (lid["claim_id"], 1, "One plank cracked."),
        (inspection["claim_id"], 2, "The crate was first opened at the customs station at six ten."),
        (receipt["claim_id"], 1, "Cart seventeen: returned, six forty in the evening."),
        (witness_claim["claim_id"], 1, "When I called, they ran towards the basin."),
        (morning["claim_id"], 1, "She brought the torn edges together. They did not fit."),
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
        claim_id=receipt["claim_id"], dossier_ids=[dossier_res["dossier_id"], exhibits["dossier_id"]],
        impact_on_plot="Mara takes responsibility for what she copied. The blank receiving line leaves a focused question for the ending.",
    )
    research_api.record_decision(
        research_proj, title="End the witnessed route at the basin",
        rationale="Let the watchman name a direction and let the engine supply a separate auditory clue. Keep the subsequent movement open.",
        claim_id=witness_claim["claim_id"], dossier_ids=[dossier_res["dossier_id"], exhibits["dossier_id"]],
        impact_on_plot="Mara can cross out the escape-by-boat inference. The next scene turns her attention back to the paper trail.",
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
                {"dossier_id": exhibits["dossier_id"], "revision": exhibit_revision, "section": "Watchman’s statement", "title": "The watchman’s statement", "reveal_after_chapter": 3},
                {"dossier_id": exhibits["dossier_id"], "revision": exhibit_revision, "section": "Transfer counterfoil", "title": "The transfer counterfoil", "reveal_after_chapter": 4},
                {"dossier_id": exhibits["dossier_id"], "revision": exhibit_revision, "section": "Dispatch receipt", "title": "Mara’s dispatch receipt", "reveal_after_chapter": 5},
                {"dossier_id": weather_dossier["dossier_id"], "revision": 1, "section": "Reader final clue", "title": "The receiving signature", "reveal_after_chapter": 6},
                {"dossier_id": exhibits["dossier_id"], "revision": exhibit_revision, "section": "Office ledger", "title": "The two ledger entries", "reveal_after_chapter": 6},
            ],
        }},
        "dossier_collections": {
            "case_records": {
                "name": "Warehouse Case Files",
                "dossier_ids": [dossier_res["dossier_id"], exhibits["dossier_id"]],
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
    research_api.reindex(research_proj)
    if not research_api.search(research_proj, "warehouse customs", limit=1)["hits"]:
        raise RuntimeError("Synthetic research source must produce a real passage citation")
    return {"project": research_proj, "image_resources": image_resources,
            "primary_claim_id": claim_res["claim_id"], "character_evidence_id": witness_limits}


def create_example_project(destination: Path) -> dict:
    """Create a new ordinary project; never overwrite an existing destination."""
    destination = Path(destination)
    if destination.exists() or destination.is_symlink():
        raise FileExistsError(f"Example destination already exists: {destination}")
    with TemporaryDirectory(prefix="lixity-example-project-") as directory:
        # Temporary roots may use macOS /var aliases or Windows short names.
        result = _populate(Path(directory).resolve())
        shutil.copytree(result["project"], destination)
    return {**result, "project": destination}


def save_example_character_dossier(project: Path, evidence_id: str) -> tuple[str, int]:
    """Prepare the same reviewed Warehouse 4 dossier for the video and PDF."""
    from lixity.research import api
    from lixity.research.character_evidence import character_dossier_text
    from lixity.research.dossier_analysis import prepare_character_analysis
    from lixity.research.dossiers import read_dossier_manuscript

    manuscript = project / "harbour-manuscript.md"
    drafts = api.manuscript_dossier_drafts(project, manuscript, kind="character")
    mara = next(draft for draft in drafts["drafts"] if draft["evidence_hints"]["character"] == "Mara")
    dossier = api.create_dossier_from_manuscript(
        project, manuscript, draft_id=mara["id"], preview_sha256=mara["preview_sha256"],
        expected_project_id=drafts["project_id"],
    )
    text, source_sha256, settings = read_dossier_manuscript(manuscript, project)
    analysis = character_dossier_text(text, source_sha256, character="Mara", language="en", settings=settings)
    body = prepare_character_analysis(mara["body"], analysis["body"], "en")
    identifier = dossier["dossier_id"]
    revision = api.revise_record(
        project, "dossier", identifier, expected_revision=1, change_kind="correction",
        reason="Review the character passages and retain the related witness statement.",
        changes={"body": body, "evidence_ids": [evidence_id]},
    )
    return identifier, int(revision["record"]["revision"])


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
