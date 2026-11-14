"""Shared help presentation; parser registration remains the command authority."""
from __future__ import annotations

import argparse
import textwrap


class GroupedHelpFormatter(argparse.RawDescriptionHelpFormatter):
    """Group registered commands without changing their grammar or aliases."""

    def _fill_text(self, text: str, width: int, indent: str) -> str:
        # Keep copyable command lines intact while wrapping explanatory prose.
        lines = []
        for line in text.splitlines():
            if line.startswith("  ") or "https://" in line or not line.strip():
                lines.append(indent + line)
            else:
                lines.append(textwrap.fill(line, width=width, initial_indent=indent,
                                           subsequent_indent=indent, break_long_words=False,
                                           break_on_hyphens=False))
        return "\n".join(lines)

    def _split_lines(self, text: str, width: int) -> list[str]:
        return textwrap.wrap(" ".join(text.split()), width, break_long_words=False,
                             break_on_hyphens=False)

    def _format_action(self, action: argparse.Action) -> str:
        if not isinstance(action, argparse._SubParsersAction):
            return super()._format_action(action)
        groups: dict[str, list[argparse.Action]] = {}
        for choice in action._choices_actions:
            command = action.choices[choice.dest]
            group = command.get_default("cli_group") or "Commands"
            groups.setdefault(group, []).append(choice)
        parts: list[str] = []
        for group, choices in groups.items():
            parts.append(" " * self._current_indent + group + ":\n")
            self._indent()
            parts.extend(self._format_action(choice) for choice in choices)
            self._dedent()
        return "".join(parts)


def command_group(name: str) -> str:
    """Give the top-level entrypoints task-oriented headings."""
    if name in {"project", "project-backup", "project-restore", "service"}:
        return "Projects and local app"
    if name == "research":
        return "Research"
    if name == "read-aloud" or name.startswith("audio-"):
        return "Audio"
    if name in {"dashboard", "export-site", "pdf", "build"}:
        return "Reports and sharing"
    if name in {"serve", "doctor", "about", "schema", "completion", "mcp"}:
        return "Setup and automation"
    return "Manuscript analysis"


# Canonical manuals, workflow notes and parseable example invocations.
COMMAND_HELP: dict[str, tuple[str, str, tuple[str, ...]]] = {
    'project-backup': (
        'PROJECT_BACKUP.md',
        'Stop project writers first. Only explicitly selected visible files and retained research '
        'are included. Output is a new directory; exclusions are reported as JSON.',
        ('lixity project-backup --project ./novel --manuscript manuscript.md --output ./backup',),
    ),
    'project-restore': (
        'PROJECT_BACKUP.md',
        'Verify SHA-256 inventory and research integrity before placing a new project. '
        'Existing destinations are refused. Reports JSON.',
        ('lixity project-restore --from ./backup --to ./restored-novel',),
    ),
    'project': (
        'USAGE.md#lixity-project',
        (
            'Inspects bounded project metadata; does not create folders or rewrite files. An explicit '
            'root uses only its local configuration. Findings are structural observations, not repair '
            'instructions.'
        ),
        ('lixity project --project ./novel', 'lixity project --project ./novel --json'),
    ),
    'analyze': (
        'USAGE.md#lixity-analyze',
        (
            'Prints corpus measurements without editing the manuscript. English is the default unless '
            'project settings choose another language; auto explicitly requests detection. Review '
            'units, coverage and unavailable values. Shared style/tense threshold switches do not alter '
            'these corpus metrics; use style or profile for those comparisons.'
        ),
        ('lixity analyze manuscript.md --language en',
         'lixity analyze --project ./novel --json -o analysis.json'),
    ),
    'profile': (
        'USAGE.md#lixity-profile',
        (
            'Without --layer, output is the paragraph profile as JSON. With --layer, output is a text '
            'explanation unless --json is supplied. Tense cues and differences support review; they are '
            'not confirmed errors.'
        ),
        ('lixity profile manuscript.md --language en',
         'lixity profile manuscript.md --layer asl --evidence --json'),
    ),
    'analysis-review': (
        'USAGE.md#lixity-analysis-review',
        (
            'Inspection writes nothing. Saving requires an observation, a status and all three current '
            "--expected-*-sha256 values from the inspection. changed is the author's assertion, not a "
            'verified manuscript edit.'
        ),
        ('lixity analysis-review --project ./novel --json',),
    ),
    'dialogue': (
        'USAGE.md#lixity-dialogue',
        (
            'Reports recognized quoted speech; it does not infer every speaker or detect all dialogue '
            'conventions. Manuscript language defaults to project settings or en.'
        ),
        ('lixity dialogue manuscript.md --language en', 'lixity dialogue --project ./novel --json'),
    ),
    'characters': (
        'USAGE.md#lixity-characters',
        (
            'Uses supplied names or root-local configured character profiles. Counts mentions, not '
            'inferred identities or relationships.'
        ),
        ('lixity characters manuscript.md --names Anna,Ben', 'lixity characters --project ./novel --json'),
    ),
    'pacing': (
        'USAGE.md#lixity-pacing',
        (
            'Measures scene structure and lexical ending cues. These are heuristic reading aids, not a '
            'validated suspense or pacing score.'
        ),
        ('lixity pacing manuscript.md --language en', 'lixity pacing --project ./novel --json'),
    ),
    'scenes': (
        'USAGE.md#scene-registers-and-project-targets',
        (
            'Select one scene or chapter without narrowing the comparison baseline. latest means the '
            'last measured scene in document order, not the most recently edited scene.'
        ),
        ('lixity scenes --project ./novel --latest', 'lixity scenes manuscript.md --scene 1:1 --json'),
    ),
    'canvas': (
        'WORKSPACE.md',
        'Export narrative scenes and chapter progression into an open JSON Canvas 1.0 file (.canvas).',
        ('lixity canvas --project ./novel', 'lixity canvas --project ./novel -o ./story.canvas'),
    ),
    'motifs': (
        'USAGE.md#lixity-motifs',
        (
            'Repeat --motif NAME=REGEX to declare multiple motifs. Quote patterns in the shell. Results '
            'do not establish whether repetition is accidental.'
        ),
        ('lixity motifs manuscript.md --motif "weather=rain|wind"',
         'lixity motifs --project ./novel --phrases 3 --json'),
    ),
    'showing': (
        'USAGE.md#lixity-showing',
        (
            'Compares lexical cue groups, quotation and short-sentence signals. This does not classify '
            'prose as showing or telling and does not prescribe a rewrite.'
        ),
        ('lixity showing manuscript.md --language en', 'lixity showing --project ./novel --json'),
    ),
    'style': (
        'USAGE.md#lixity-style',
        (
            "Compares usable chapters against this manuscript's reference. Unknown values remain "
            'unavailable; a difference is not a literary-quality score. Explicit overrides take '
            'precedence over project settings.'
        ),
        ('lixity style manuscript.md --language en', 'lixity style --project ./novel --json'),
    ),
    'diff': (
        'USAGE.md#lixity-diff',
        (
            'Compare two manuscript files or recorded revisions across words, sentence dispersion, '
            'length entropy, sticky sentences, and indirect speech.'
        ),
        ('lixity diff draft1.md draft2.md --json', 'lixity diff manuscript.md --json'),
    ),
    'dashboard': (
        'USAGE.md#lixity-dashboard',
        (
            'Writes a self-contained manuscript/analysis snapshot; it has no live project writes. Use '
            'service start --open for the interactive app, or export-site for a project reading '
            'website. Review embedded manuscript text before sharing.'
        ),
        ('lixity dashboard manuscript.md --language en -o dashboard.html',),
    ),
    'pdf': (
        'USAGE.md#lixity-pdf',
        (
            'Writes a printable PDF; default layout is report (analysis). Choose editor for annotated '
            'A4, book for A5, sheet for a submission grid or document for neutral A4 prose.'
        ),
        ('lixity pdf manuscript.md --layout editor -o editorial.pdf',
         'lixity pdf --project ./novel --layout book -o reading.pdf'),
    ),
    'export-site': (
        'WORKSPACE.md#export-a-reading-website',
        (
            'Choose --preflight for inspection or --output for an export directory. The default review '
            'mode can include research; reader/companion require --publication-profile. Analysis and '
            'saved chapter audio are reader-only opt-ins. Chapter limits remove later content before '
            'assembly; hidden notes are not access control.'
        ),
        ('lixity export-site --project ./novel --preflight --json',
         'lixity export-site --project ./novel --output ./reading-copy'),
    ),
    'build': (
        'USAGE.md#lixity-build',
        (
            'Runs analysis and compares the artifact set with existing exports. --dry-run performs '
            'those reads/computations but writes nothing. A normal build writes changed exports and '
            'archives replaced artifacts; it never rewrites the manuscript.'
        ),
        ('lixity build --project ./novel --dry-run', 'lixity build manuscript.md --language en'),
    ),
    'serve': (
        'INSTALLATION.md#running-the-server',
        (
            'Runs in the foreground. Ctrl+C stops this process; service stop only manages instances '
            'created by the service controller. Use --no-project for an empty workspace.'
        ),
        ('lixity serve --no-project', 'lixity serve ./novel --port 9000'),
    ),
    'doctor': (
        'USAGE.md#lixity-doctor',
        (
            'Inspects installation metadata and local service state without repairs or restarts. A '
            'healthy stopped service is valid. Exit 1 means reported issues or unavailable diagnostics; '
            'it does not authorize a repair.'
        ),
        ('lixity doctor', 'lixity doctor --port 9000 --json'),
    ),
    'about': (
        'AGENTS.md',
        (
            'Describes this installed interface and its heuristic limits. --section implies JSON. This '
            'is command/feature discovery, not an analysis-result JSON Schema.'
        ),
        ('lixity about --json', 'lixity about --section commands'),
    ),
    'schema': (
        'AGENTS.md',
        (
            'Same metadata as about --json. For research entity JSON Schema, use lixity research '
            'schema.'
        ),
        ('lixity schema', 'lixity schema --section configuration'),
    ),
    'mcp': (
        'AGENTS.md#21-mcp-server-read-only',
        (
            'Runs the read-only Model Context Protocol (MCP) server over standard input and output '
            'using JSON-RPC 2.0. Exposes tools for corpus analysis, style profiles, pacing, dialogue, '
            'showing-vs-telling, motifs, characters, and review markers. Completely offline and safe.'
        ),
        ('lixity mcp',),
    ),
    'completion': (
        'INSTALLATION.md#optional-shell-completion',
        (
            'Prints a shell completion script to stdout; it does not install or source it. Redirect it '
            'to a user-writable shell completion directory using the installation instructions.'
        ),
        ('lixity completion bash', 'lixity completion zsh'),
    ),
    'read-aloud': (
        'AUDIO.md#lixity-read-aloud',
        (
            'Native rendering requires a separately installed matching worker; an explicit external '
            'profile sends speech text to its configured provider. FFmpeg is required for MP3 and tempo '
            'other than 1.0. New default profiles use speed 1.2. Invocations do not save profile '
            'overrides. Rendering normally reads/writes private segment cache; previews bypass it. '
            'Explicit --project plus --chapter retains completed WAV audio in .lixity/audio/exports/. '
            'Plan/export modes make no synthesis request and need no worker.'
        ),
        ('lixity read-aloud --project ./novel --preview --plan-only',
         'lixity read-aloud --project ./novel --preview --speed 1.0 -o preview.wav'),
    ),
    'audio-export-plan': (
        'AUDIO.md#audio-export-and-external-providers-unreleased',
        (
            'Defaults to timeline JSON on stdout; use -o to write a file. Reads project settings and '
            'saved directions but no saved reference audio. No worker/provider is contacted. --ssml is '
            'a lossy projection and reports unsupported controls on stderr. Rendering-only --progress, '
            '--speech-target, --no-audio-cache and --fresh-audio remain accepted but have no effect. '
            '--plan-only does not switch this command away from its default timeline; use read-aloud '
            '--plan-only for the native plan.'
        ),
        ('lixity audio-export-plan --project ./novel -o manuscript.timeline.json',
         'lixity audio-export-plan --project ./novel --chapter 2 --ssml -o chapter-2.ssml'),
    ),
    'audio-status': (
        'AUDIO.md',
        (
            "Omitting --project probes Qwen endpoints by default; --engine chooses another engine's "
            'endpoints. Explicit projects supply root-local profiles. External-provider status remains '
            'unknown and does not contact the provider. This is a read-only snapshot; it does not start '
            'workers or certify later rendering.'
        ),
        ('lixity audio-status --project ./novel --json', 'lixity audio-status --engine qwen3-base --json'),
    ),
    'audio-microphone': (
        'AUDIO.md',
        (
            'Default action status and devices inspect hardware only. set changes the ALSA mixer '
            'immediately and requires --gain. calibrate records an 8-second sample after 4 seconds, '
            'optionally setting gain first; it suggests but does not apply a subsequent adjustment. '
            'Optional local capture tools are required. --card and --control apply only to set; status '
            'always inspects default card 1/control Mic. --device applies only to calibrate; recording '
            'fallbacks may use other inputs.'
        ),
        ('lixity audio-microphone devices --json',
         'lixity audio-microphone set --card 1 --control Mic --gain 35'),
    ),
    'audio-calibrate': (
        'AUDIO.md',
        (
            'Uses local capture tools; records 1-30 seconds (default: 8) after a default 4-second '
            'countdown. --gain attempts an immediate ALSA mixer change on card 1/control Mic; '
            'recommended gain is not applied. The recording is not retained. --device is a preferred '
            'input and fallbacks may use another device. Measurements are uncalibrated heuristics, not '
            'recording certification.'
        ),
        ('lixity audio-calibrate --duration 8 --countdown 4 --json', 'lixity audio-calibrate --gain 35'),
    ),
    'audio-reference': (
        'AUDIO.md',
        (
            'All actions except calibration-text require --project. create needs --audio and '
            '--transcript-file and saves immutable audio plus exact transcript under '
            '.lixity/audio-references/. inspect needs --reference-id and only reads it. record uses '
            'optional local capture tools; a supplied transcript saves a reference, while no transcript '
            'requires -o to retain the raw WAV. generate calls the local Qwen VoiceDesign worker and '
            'saves a synthetic reference; its default text is phonetic calibration text. '
            'calibration-text prints plain text; other actions emit JSON. Review transcript fidelity '
            'yourself.'
        ),
        ('lixity audio-reference calibration-text --language en --variant short',
         'lixity audio-reference create --project ./novel --audio reference.wav --transcript-file '
         'reference.txt'),
    ),
    'audio-import': (
        'AUDIO.md#retain-or-import-chapter-audio-unreleased',
        (
            'Requires an explicit project and reviewed source_sha256 from audio-direction inspect; '
            'select the same --manuscript for both. Copies up to 200 MiB of mono/stereo 16-bit PCM WAV '
            'at 8-192 kHz into .lixity/audio/exports/, replacing the prior recording for that chapter. '
            'Does not convert formats or verify spoken chapter fidelity. Prints chapter-audio JSON.'
        ),
        ('lixity audio-direction inspect --project ./novel',
         'lixity audio-import --project ./novel --chapter 2 --audio chapter-2.wav --source-sha256 '
         'REVIEWED_FULL_MANUSCRIPT_SHA256'),
    ),
    'audio-import-transcript': (
        'AUDIO.md',
        (
            'Reads an ASR JSON object containing words[] or segments[].words[] and hashes the audio; '
            'does not run recognition, decode the audio, or certify word/timing fidelity. Output is '
            'lixity-audio-transcript/1 JSON on stdout or in -o. Invalid entries may be skipped; '
            'multi-token words are split and overlapping times adjusted. Run audio-verify against the '
            'matching timeline to validate comparison inputs. A top-level word array is currently '
            'rejected by the CLI JSON loader.'
        ),
        ('lixity audio-import-transcript chapter-2.wav whisper-output.json --language en -o '
         'chapter-2.words.json',
         'lixity audio-import-transcript chapter-2.wav whisper-output.json --model local-recognizer'),
    ),
    'audio-inspect': (
        'AUDIO.md',
        (
            'Reads WAV/FLAC/MP3 and prints lixity-audio-audit/1 JSON without speech recognition or '
            'network calls. FFmpeg is needed for compressed formats and unsupported WAV encodings. '
            '--plan and matching --transcript together enable text/pause comparison; otherwise those '
            'results remain unknown. Signal observations are heuristics, not a quality score. No '
            'retained project files are written; decoding may use discarded temporary audio.'
        ),
        ('lixity audio-inspect chapter-2.wav',
         'lixity audio-inspect chapter-2.wav --plan chapter-2.timeline.json --transcript '
         'chapter-2.words.json --language en'),
    ),
    'audio-verify': (
        'AUDIO.md',
        (
            'Requires --plan; use audio-export-plan to create it. Prints lixity-audio-audit/1 JSON. '
            'Text and plan-pause checks remain unknown unless --transcript supplies '
            'lixity-audio-transcript/1 word timings bound to this audio SHA-256. Does not run '
            'recognition or establish spoken fidelity. FFmpeg is needed for compressed formats and '
            'unsupported WAV encodings; no retained project files are written.'
        ),
        ('lixity audio-verify chapter-2.wav --plan chapter-2.timeline.json',
         'lixity audio-verify chapter-2.wav --plan chapter-2.timeline.json --transcript '
         'chapter-2.words.json --language en'),
    ),
    'audio-direction': (
        'AUDIO.md',
        (
            'inspect is the read-only default and returns passage anchors plus '
            'source/settings/direction hashes. add requires --chapter, --line, and an instruction, '
            'saved profile or pause; it resolves its own current snapshot and writes a new range. save '
            'requires a direction JSON object; remove requires --id. save/remove require all three '
            'observed --expected-* hashes. Writes update .lixity/audio-directions.json without editing '
            'manuscript text. No synthesis runs.'
        ),
        ('lixity audio-direction inspect --project ./novel',
         "lixity audio-direction add --project ./novel --chapter 1 --line 5 --instruction 'Read calmly.'"),
    ),
    'audio-migrate': (
        'AUDIO.md',
        (
            'Default preview prints JSON without writes. Schema switches are mutually exclusive and '
            'cannot be combined with --replace/--instructions. Applying requires the reviewed snapshot '
            'token plus a new ZIP path outside the project; it backs up configuration then updates '
            'root-local audio settings. Backup contains configuration, not manuscripts or retained '
            'voice/direction data. Changed inputs or migration choices invalidate the snapshot.'
        ),
        ('lixity audio-migrate --project ./novel --to-schema-5',
         'lixity audio-migrate --project ./novel --to-schema-5 --apply --expected-snapshot REVIEWED_TOKEN '
         '--backup ../novel-audio-schema5.zip'),
    ),
    'service': (
        'INSTALLATION.md#running-the-server',
        "",
        (),
    ),
    'research': (
        'research/USAGE.md',
        "",
        (),
    ),
}


def finish_command_help(parser: argparse.ArgumentParser, name: str) -> None:
    """Append task help after command-specific parser construction is complete."""
    from .site import docs_url

    manual, notes, examples = COMMAND_HELP[name]
    sections: list[str] = []
    if notes:
        sections.append(textwrap.fill(notes, width=76, break_long_words=False, break_on_hyphens=False))
    if name in {"read-aloud", "audio-export-plan", "audio-direction"}:
        sections.append(textwrap.fill(
            "VoiceDesign generates segments independently; role-specific instructions can change "
            "the perceived voice. Compare short read-aloud --preview samples before a chapter render. "
            "Base uses a saved reference but does not accept free-form direction. Neither model "
            "guarantees speaker continuity. read-aloud --no-direction omits saved passage direction, range "
            "voices and pauses; profile pronunciation rules, tempo and standard pauses remain active.",
            width=76, break_long_words=False, break_on_hyphens=False))
    if name in {"read-aloud", "audio-export-plan"}:
        from .speech_profiles import QWEN_VOICES

        sections.append(textwrap.fill(
            "qwen3 uses preset voices: " + ", ".join(QWEN_VOICES) + ". "
            "Qwen lists no German-native preset; review pronunciation in a short preview. "
            "qwen3-design uses a description; qwen3-base uses a saved reference. "
            "IMS-Toucan supports reference voices with IPA and structured prosody; free-text "
            "acting prompts are unsupported. Existing F5 profiles remain readable, but the "
            "bundled F5 loader is unavailable. See the audio manual for engine-specific limits.",
            width=76, break_long_words=False, break_on_hyphens=False))
    if parser.epilog:
        sections.append(parser.epilog)
    if examples:
        sections.append("Examples:\n" + "\n".join("  " + example for example in examples))
    if docs_url(manual) not in (parser.epilog or ""):
        sections.append("Manual: " + docs_url(manual))
    parser.epilog = "\n\n".join(sections)
    parser.formatter_class = GroupedHelpFormatter
    parser.set_defaults(cli_group=command_group(name))
    group_options(parser, name)


AUDIO_OPTION_HELP: dict[str, dict[str, str]] = {'read-aloud': {'--output': 'WAV/MP3 target for rendering; plan/SSML/timeline file for export (export '
                            'default: stdout; audio default: workspace-root/<slug>[-preview|-chapter-N].wav)',
                '--chapter': 'Select a 1-based manuscript chapter for rendering or export; also constrains '
                             'previews',
                '--language': 'Override speech language for this invocation (default: saved profile, then '
                              'project setting or en)',
                '--plan-only': 'Print the native speech-plan JSON, or write it with -o; no synthesis',
                '--fresh-audio': 'Recompute speech segments and refresh enabled cache entries instead of '
                                 'reusing them',
                '--speech-target': 'Native execution target (default: local); Jetson supports Qwen only and '
                                   'needs its configured SSH forward; external profiles use their provider '
                                   'URL',
                '--engine': 'Select a native engine or openai-compatible provider; native worker must match '
                            'the selected model',
                '--voice': 'Qwen preset, design for VoiceDesign, reference for reference engines, thorsten '
                           "for Coqui, or the external provider's voice identifier"},
 'audio-microphone': {'action': 'status (default): inspect default mixer; devices: list inputs; set: change '
                                'gain; calibrate: record an 8-second test',
                      '--gain': 'set/calibrate: requested ALSA raw gain (implementation accepts 0-100; '
                                'actual mixer range depends on hardware)',
                      '--card': 'set only: ALSA mixer card index or ID (default: 1)',
                      '--control': 'set only: ALSA mixer control (default: Mic)',
                      '--device': 'calibrate only: preferred capture device; default initial ALSA input '
                                  'plughw:CARD=I3000,DEV=0'},
 'audio-calibrate': {'--duration': 'Recording length in seconds, 1-30 (default: 8)',
                     '--gain': 'Attempt to set default ALSA capture gain before recording (accepted 0-100; '
                               'hardware range varies)',
                     '--device': 'Preferred capture device (initial ALSA default: plughw:CARD=I3000,DEV=0); '
                                 'fallback may use other inputs'},
 'audio-reference': {'--project': 'Existing explicit project root; required except for calibration-text',
                     '--audio': 'create: 1-30 second mono 16-bit PCM WAV at 24 kHz (maximum 2 MiB)',
                     '--duration': 'record: 1-30 seconds (default: 15; 24 with --calibration-text and '
                                   'phonetic variant)',
                     '--gain': 'record: attempt default ALSA mixer gain before capture (accepted 0-100; '
                               'hardware range varies)',
                     '--language': 'generate/calibration-text/record --calibration-text: text language '
                                   '(default: de)',
                     '--variant': 'calibration-text or record --calibration-text: passage variant (default: '
                                  'phonetic); generate ignores this option',
                     '--transcript-file': 'create/record: exact UTF-8 transcript (record prefers a nonempty '
                                          '--transcript)',
                     '--output': 'record only: write raw WAV; without a transcript this is the only retained '
                                 'audio'},
 'audio-import-transcript': {'transcript': 'External ASR JSON object with words[] or segments[].words[]',
                             '--model': 'Recognizer provenance label (default: model/asr_model field, '
                                        'otherwise unknown)',
                             '--output': 'Write converted transcript JSON to this file (default: stdout)'},
 'audio-direction': {'--expected-source': 'save/remove: observed source_sha256 from inspect',
                     '--expected-settings': 'save/remove: observed settings_sha256 from inspect',
                     '--expected-direction': 'save/remove: observed direction_sha256 from inspect',
                     '--pause-before': 'add: silence before the selected range, 0-10 seconds',
                     '--pause-after': 'add: silence after the selected range, 0-10 seconds',
                     '--start': 'add: inclusive 0-based offset in passage spoken Unicode code points '
                                '(default: 0)',
                     '--end': 'add: exclusive offset in passage spoken Unicode code points (default: passage '
                              'end)'},
 'audio-migrate': {'--replace': 'Piper replacement mode: choose PROFILE=QWEN_PRESET for every removed '
                                'profile; repeat as needed',
                   '--instructions': 'Piper replacement mode: explicit PROFILE=TEXT delivery instructions '
                                     '(default: empty)',
                   '--backup': 'Apply only: new non-overwriting configuration backup ZIP outside the project',
                   '--expected-snapshot': 'Apply only: exact snapshot from the reviewed preview with '
                                          'identical choices'}}

AUDIO_OPTION_HELP["audio-export-plan"] = {
    **AUDIO_OPTION_HELP["read-aloud"],
    "--output": "Write timeline JSON or SSML to this file (default: stdout)",
    "--plan-only": "Already enabled; use read-aloud --plan-only for native speech-plan JSON",
}


def group_options(parser: argparse.ArgumentParser, name: str) -> None:
    """Present dense option lists by task, preserving actions and exclusions."""
    groups: list[tuple[str, str, tuple[str, ...]]] = []
    if name in {"read-aloud", "audio-export-plan"}:
        groups = [
            ("Text and output", "Choose the source, scope and destination", (
                "--project", "--output", "--chapter", "--preview", "--preview-line", "--language")),
            ("Voice and delivery", "Overrides apply to this invocation; they do not save profiles", (
                "--profile", "--engine", "--voice", "--reference-id", "--voice-description",
                "--instructions", "--speed", "--no-direction", "--keep-markers")),
            ("Plan export", "No synthesis request; valid project/profile settings are still required", (
                "--plan-only", "--timeline", "--ssml")),
            ("Worker, provider and cache", "Rendering-only flags do not generate audio in plan-export mode", (
                "--speech-target", "--base-url", "--model", "--api-key-env", "--supports-instructions",
                "--no-audio-cache", "--fresh-audio", "--progress")),
        ]
    elif name == "audio-reference":
        groups = [
            ("Project reference", "Read or explicitly retain a reference in this project", (
                "--project", "--reference-id", "--audio", "--transcript-file", "--transcript")),
            ("Microphone recording", "Options for record; no browser microphone permission is involved", (
                "--duration", "--gain", "--device", "--calibration-text", "--output")),
            ("Reading text and synthetic voice", "Check each option's applicable actions", (
                "--language", "--variant", "--voice-description")),
        ]
    elif name == "export-site":
        groups = [
            ("Project and destination", "Inspect with --preflight or write with --output", (
                "--project", "--manuscript", "--language", "--output", "--preflight", "--json")),
            ("Reader selection", "Review is the default; reader/companion require a publication profile", (
                "--mode", "--publication-profile", "--max-chapter", "--analysis", "--include-audio")),
            ("Retained research", "Review the selected content and permissions before sharing", (
                "--include-research", "--include-source-files")),
        ]
    thresholds = ("--preset", "--z-mild", "--z-strong", "--fdr-q", "--fdr-method",
                  "--dim-threshold", "--flag-min-severity", "--min-chapters")
    if name not in {"service", "research"} and "--preset" in parser._option_string_actions:
        note = ("These shared switches do not change this command's measurements"
                if name in {"analyze", "dialogue", "pacing", "showing"}
                else "Optional overrides; displayed defaults are built-in values, before project settings")
        groups.append(("Review thresholds", note, thresholds))
    for title, description, options in groups:
        actions = [parser._option_string_actions[option] for option in options
                   if option in parser._option_string_actions]
        if not actions:
            continue
        group = parser.add_argument_group(title, description)
        for action in actions:
            if action in parser._optionals._group_actions:
                parser._optionals._group_actions.remove(action)
                group._group_actions.append(action)
