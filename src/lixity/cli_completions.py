"""Shell completion script templates and builder for Bash and Zsh."""
from __future__ import annotations

from collections.abc import Sequence

from .status import LAYER_FEATURES

_BASH_COMPLETION = """# bash completion for lixity – source this file or add it to bash_completion.d/
#   lixity completion bash > /etc/bash_completion.d/lixity   # system
#   lixity completion bash > ~/.local/share/bash-completion/completions/lixity
_lixity_complete() {
    local cur prev
    COMPREPLY=()
    cur="${COMP_WORDS[COMP_CWORD]}"
    prev="${COMP_WORDS[COMP_CWORD-1]}"
    local cmds="__LIXITY_COMMANDS__"
    local opts="--help --version --project --language --json --output -o --dry-run --names --motif --phrases --name"
    local style_opts="--z-mild --z-strong --fdr-q --fdr-method --dim-threshold --flag-min-severity --min-chapters"
    if [[ $COMP_CWORD -eq 1 ]]; then
        COMPREPLY=( $(compgen -W "$cmds --help --version" -- "$cur") )
        return 0
    fi
    case "${COMP_WORDS[1]}" in
        project-backup)
            case "$prev" in
                --project|--output) COMPREPLY=( $(compgen -d -- "$cur") ) ;;
                --manuscript|--settings|--attachment) COMPREPLY=( $(compgen -f -- "$cur") ) ;;
                *) COMPREPLY=( $(compgen -W "--help --project --manuscript --settings --attachment --output" -- "$cur") ) ;;
            esac
            return 0
            ;;
        project-restore)
            case "$prev" in
                --from|--to) COMPREPLY=( $(compgen -d -- "$cur") ) ;;
                *) COMPREPLY=( $(compgen -W "--help --from --to" -- "$cur") ) ;;
            esac
            return 0
            ;;
        read-aloud|audio-export-plan)
            case "$prev" in
                --language) COMPREPLY=( $(compgen -W "zh en ja ko de fr ru pt es it" -- "$cur") ) ;;
                --speech-target) COMPREPLY=( $(compgen -W "local jetson" -- "$cur") ) ;;
                --voice) COMPREPLY=( $(compgen -W "Vivian Serena Uncle_Fu Dylan Eric Ryan Aiden Ono_Anna Sohee design reference thorsten" -- "$cur") ) ;;
                --engine) COMPREPLY=( $(compgen -W "qwen3 qwen3-design qwen3-base coqui coqui-reference f5-tts ims-toucan openai-compatible mlx-audio" -- "$cur") ) ;;
                --project) COMPREPLY=( $(compgen -d -- "$cur") ) ;;
                -o|--output) COMPREPLY=( $(compgen -f -- "$cur") ) ;;
                --profile|--instructions|--voice-description|--reference-id|--chapter|--preview-line|--speed|--base-url|--model|--api-key-env) ;;
                *)
                    COMPREPLY=( $(compgen -W "--help --project -o --output --chapter --language --profile --engine --instructions --voice --voice-description --reference-id --speed --speech-target --no-audio-cache --fresh-audio --keep-markers --plan-only --ssml --timeline --base-url --model --api-key-env --supports-instructions --no-direction --preview --preview-line --progress" -- "$cur") )
                    COMPREPLY+=( $(compgen -f -- "$cur") )
                    ;;
            esac
            return 0
            ;;
        audio-inspect|audio-verify)
            case "$prev" in
                --plan|--transcript) COMPREPLY=( $(compgen -f -- "$cur") ) ;;
                --language) COMPREPLY=( $(compgen -W "en de fr es it pt nl generic" -- "$cur") ) ;;
                *) COMPREPLY=( $(compgen -W "--help --plan --transcript --language --json" -- "$cur") ); COMPREPLY+=( $(compgen -f -- "$cur") ) ;;
            esac
            return 0
            ;;
        audio-transcribe)
            case "$prev" in
                -o|--output) COMPREPLY=( $(compgen -f -- "$cur") ) ;;
                --base-url|--model|--language) ;;
                *) COMPREPLY=( $(compgen -W "--help -o --output --base-url --model --language" -- "$cur") ); COMPREPLY+=( $(compgen -f -- "$cur") ) ;;
            esac
            return 0
            ;;
        audio-import-transcript)
            case "$prev" in
                -o|--output) COMPREPLY=( $(compgen -f -- "$cur") ) ;;
                --language) COMPREPLY=( $(compgen -W "en de fr es it pt nl generic" -- "$cur") ) ;;
                *) COMPREPLY=( $(compgen -W "--help -o --output --model --language" -- "$cur") ); COMPREPLY+=( $(compgen -f -- "$cur") ) ;;
            esac
            return 0
            ;;
        audio-status)
            case "$prev" in
                --project) COMPREPLY=( $(compgen -d -- "$cur") ) ;;
                --engine) COMPREPLY=( $(compgen -W "qwen3 qwen3-design qwen3-base coqui coqui-reference f5-tts ims-toucan openai-compatible mlx-audio" -- "$cur") ) ;;
                *) COMPREPLY=( $(compgen -W "--help --project --engine --json" -- "$cur") ) ;;
            esac
            return 0
            ;;
        audio-microphone)
            case "$prev" in
                --gain|--card|--control|--device) ;;
                *) COMPREPLY=( $(compgen -W "status set devices calibrate --help --gain --card --control --device --json" -- "$cur") ) ;;
            esac
            return 0
            ;;
        audio-calibrate)
            case "$prev" in
                --gain|--duration|--countdown|--device) ;;
                *) COMPREPLY=( $(compgen -W "--help --gain --duration --countdown --device --json" -- "$cur") ) ;;
            esac
            return 0
            ;;
        audio-reference)
            case "$prev" in
                --project) COMPREPLY=( $(compgen -d -- "$cur") ) ;;
                --audio|--transcript-file|-o|--output) COMPREPLY=( $(compgen -f -- "$cur") ) ;;
                --language) COMPREPLY=( $(compgen -W "de en" -- "$cur") ) ;;
                --variant) COMPREPLY=( $(compgen -W "phonetic short" -- "$cur") ) ;;
                --gain|--duration|--device|--transcript|--reference-id|--voice-description) ;;
                *) COMPREPLY=( $(compgen -W "create inspect record generate calibration-text --help --project --audio --transcript-file --transcript --reference-id --duration --gain --device --calibration-text --variant --language --voice-description -o --output" -- "$cur") ) ;;
            esac
            return 0
            ;;
        audio-direction)
            case "$prev" in
                --project) COMPREPLY=( $(compgen -d -- "$cur") ) ;;
                --input|--manuscript) COMPREPLY=( $(compgen -f -- "$cur") ) ;;
                --id|--replace-id|--expected-source|--expected-settings|--expected-direction|--chapter|--line|--instruction|--profile-id|--pause-before|--pause-after|--start|--end) ;;
                *) COMPREPLY=( $(compgen -W "inspect add save remove --help --project --manuscript --input --id --replace-id --expected-source --expected-settings --expected-direction --chapter --line --instruction --profile-id --pause-before --pause-after --start --end" -- "$cur") ) ;;
            esac
            return 0
            ;;
        audio-migrate)
            case "$prev" in
                --project) COMPREPLY=( $(compgen -d -- "$cur") ) ;;
                --backup) COMPREPLY=( $(compgen -f -- "$cur") ) ;;
                --replace)
                    if [[ $cur == *=* ]]; then
                        local candidate replacement="${cur%%=*}="
                        for candidate in $(compgen -W "Vivian Serena Uncle_Fu Dylan Eric Ryan Aiden Ono_Anna Sohee" -- "${cur#*=}"); do
                            COMPREPLY+=( "$replacement$candidate" )
                        done
                    fi
                    ;;
                --instructions|--expected-snapshot) ;;
                *) COMPREPLY=( $(compgen -W "--help --project --to-schema-3 --to-schema-4 --to-schema-5 --replace --instructions --apply --backup --expected-snapshot" -- "$cur") ) ;;
            esac
            return 0
            ;;
    esac
    case "$prev" in
        service)
            COMPREPLY=( $(compgen -W "start stop restart status" -- "$cur") )
            return 0
            ;;
        research)
            COMPREPLY=( $(compgen -W "__LIXITY_RESEARCH_COMMANDS__" -- "$cur") )
            return 0
            ;;
        --project|--research-project|--research-dir)
            COMPREPLY=( $(compgen -d -- "$cur") )
            return 0
            ;;
        --file|--manuscript)
            COMPREPLY=( $(compgen -f -- "$cur") )
            return 0
            ;;
        --language)
            COMPREPLY=( $(compgen -W "auto de en fr es it pt nl generic" -- "$cur") )
            return 0
            ;;
        --layer)
            if [[ ${COMP_WORDS[1]} == profile ]]; then
                COMPREPLY=( $(compgen -W "__LIXITY_PARAGRAPH_LAYERS__" -- "$cur") )
                return 0
            fi
            ;;
        --section)
            if [[ ${COMP_WORDS[1]} == about || ${COMP_WORDS[1]} == schema ]]; then
                COMPREPLY=( $(compgen -W "__LIXITY_ABOUT_SECTIONS__" -- "$cur") )
                return 0
            fi
            ;;
        --fdr-method)
            COMPREPLY=( $(compgen -W "bh by" -- "$cur") )
            return 0
            ;;
        --backend)
            COMPREPLY=( $(compgen -W "auto process systemd" -- "$cur") )
            return 0
            ;;
        --flag-min-severity)
            COMPREPLY=( $(compgen -W "1 2 3" -- "$cur") )
            return 0
            ;;
        -o|--output)
            COMPREPLY=( $(compgen -f -- "$cur") )
            return 0
            ;;
        completion)
            COMPREPLY=( $(compgen -W "bash zsh" -- "$cur") )
            return 0
            ;;
    esac
    if [[ ${COMP_WORDS[1]} == about || ${COMP_WORDS[1]} == schema ]]; then
        COMPREPLY=( $(compgen -W "--json --section --help" -- "$cur") )
        return 0
    fi
    if [[ ${COMP_WORDS[1]} == doctor ]]; then
        COMPREPLY=( $(compgen -W "--json --port --help" -- "$cur") )
        return 0
    fi
    if [[ ${COMP_WORDS[1]} == research ]]; then
        COMPREPLY=( $(compgen -W "--project --file --title --language --actor --source-id --version-id --reason --allow-retention --dry-run --context --thresholds --query --limit --passage --help" -- "$cur") )
        return 0
    fi
    if [[ ${COMP_WORDS[1]} == project ]]; then
        COMPREPLY=( $(compgen -W "--help --project --json" -- "$cur") )
        COMPREPLY+=( $(compgen -d -- "$cur") )
        return 0
    fi
    if [[ ${COMP_WORDS[1]} == analysis-review ]]; then
        COMPREPLY=( $(compgen -W "--help --project --manuscript --language --tense-model --tense-scope --json --observation --status --expected-source-sha256 --expected-analysis-sha256 --expected-review-sha256" -- "$cur") )
        return 0
    fi
    if [[ ${COMP_WORDS[1]} == scenes ]]; then
        COMPREPLY=( $(compgen -W "--help --project --language --json --chapter --scene --latest" -- "$cur") )
        COMPREPLY+=( $(compgen -f -- "$cur") )
        return 0
    fi
    if [[ ${COMP_WORDS[1]} == export-site ]]; then
        if [[ $prev == --analysis ]]; then COMPREPLY=( $(compgen -W "chapters language full all" -- "$cur") ); return 0; fi
        COMPREPLY=( $(compgen -W "--help --project --language --json -o --output --include-research --include-source-files --mode --publication-profile --max-chapter --analysis --include-audio" -- "$cur") )
        COMPREPLY+=( $(compgen -f -- "$cur") )
        return 0
    fi
    if [[ ${COMP_WORDS[1]} == profile ]]; then
        COMPREPLY=( $(compgen -W "$opts $style_opts --layer --only-notable --evidence" -- "$cur") )
        COMPREPLY+=( $(compgen -f -- "$cur") )
        return 0
    fi
    COMPREPLY=( $(compgen -W "$opts $style_opts" -- "$cur") )
    COMPREPLY+=( $(compgen -f -- "$cur") )
}
complete -F _lixity_complete lixity
"""

_ZSH_COMPLETION = """#compdef lixity
# zsh completion for lixity – place in a directory of $fpath
#   lixity completion zsh > "${fpath[1]}/_lixity"
_lixity_style_flags=(
  '--z-mild[Notable |z*| threshold]:threshold:'
  '--z-strong[Strong |z*| threshold]:threshold:'
  '--fdr-q[FDR q]:q:'
  '--fdr-method[FDR method]:method:(bh by)'
  '--min-chapters[Minimum chapters for baseline]:count:'
  '--dim-threshold[Dimension score threshold]:threshold:'
  '--flag-min-severity[Minimum severity]:severity:(1 2 3)'
)
_lixity() {
  local -a cmds
  cmds=(
__LIXITY_ZSH_COMMANDS__
  )
  _arguments -C \
    '--version[Print version and exit]' \
    '1: :->command' \
    '*:: :->args'
  case $state in
    command)
      _describe -t commands 'lixity command' cmds
      ;;
    args)
      case $words[1] in
        read-aloud|audio-export-plan)
          _arguments \
            '1:manuscript:_files' \
            '--help[Help]' \
            '--project[Explicit project root]:directory:_files -/' \
            '-o[Audio WAV or MP3 output]:file:_files' \
            '--output[Audio WAV or MP3 output]:file:_files' \
            '--chapter[Canonical chapter number]:chapter:' \
            '--language[Qwen speech language]:language:(zh en ja ko de fr ru pt es it)' \
            '--profile[Saved narrator profile]:profile:' \
            '--instructions[Delivery instructions where supported, otherwise export-only]:text:' \
            '--engine[Speech model variant]:engine:(qwen3 qwen3-design qwen3-base coqui coqui-reference f5-tts ims-toucan openai-compatible mlx-audio)' \
            '--voice[Speech voice]:voice:(Vivian Serena Uncle_Fu Dylan Eric Ryan Aiden Ono_Anna Sohee design reference thorsten)' \
            '--voice-description[VoiceDesign description]:text:' \
            '--reference-id[Saved project reference]:id:' \
            '--speed[Postprocessing tempo factor]:speed:' \
            '--speech-target[Execution target]:target:(local jetson)' \
            '--ssml[Export SSML without synthesis]' \
            '--timeline[Export lossless JSON timeline without synthesis]' \
            '--base-url[Explicit provider URL]:url:' \
            '--model[External model identifier]:model:' \
            '--api-key-env[Credential environment variable name]:name:' \
            '--supports-instructions[Provider supports free-text instructions]' \
            '--plan-only[Inspect the effective speech plan without synthesis]' \
            '--no-direction[Explicitly ignore saved passage direction]' \
            '--preview[Preview the first spoken paragraph]' \
            '--preview-line[Preview paragraph at source line]:line:' \
            '--progress[Report progress to stderr]' \
            '--no-audio-cache[Do not read or retain reusable audio segments]' \
            '--fresh-audio[Recompute completed audio segments]' \
            '--keep-markers[Read editorial markers aloud]'
          ;;
        audio-inspect|audio-verify)
          _arguments \
            '1:audio:_files' \
            '--help[Help]' \
            '--plan[Exported direction timeline]:file:_files' \
            '--transcript[Timestamped transcript]:file:_files' \
            '--language[Explicit analysis language]:language:(en de fr es it pt nl generic)' \
            '--json[JSON output]'
          ;;
        audio-transcribe)
          _arguments \
            '1:audio:_files' \
            '--help[Help]' \
            '-o[Transcription JSON output]:file:_files' \
            '--output[Transcription JSON output]:file:_files' \
            '--base-url[MLX-Audio base URL]:url:' \
            '--model[Transcription model]:model:' \
            '--language[Transcription language]:language:'
          ;;
        audio-status)
          _arguments \
            '--help[Help]' \
            '--project[Explicit project root]:directory:_files -/' \
            '--engine[Compare a model variant]:engine:(qwen3 qwen3-design qwen3-base coqui coqui-reference f5-tts ims-toucan openai-compatible mlx-audio)' \
            '--json[Machine-readable status]'
          ;;
        audio-microphone)
          _arguments \
            '1:action:(status set devices calibrate)' \
            '--help[Help]' \
            '--gain[ALSA capture gain 0-50]:gain:' \
            '--card[ALSA card index or id]:card:' \
            '--control[ALSA mixer control]:control:' \
            '--device[Hardware capture device]:device:' \
            '--json[Machine-readable microphone status]'
          ;;
        audio-calibrate)
          _arguments \
            '--help[Help]' \
            '--gain[ALSA capture gain 0-50]:gain:' \
            '--duration[Calibration burst length in seconds]:duration:' \
            '--countdown[Countdown delay in seconds]:seconds:' \
            '--device[Hardware capture device]:device:' \
            '--json[Machine-readable calibration report]'
          ;;
        audio-reference)
          _arguments \
            '1:action:(create inspect record generate calibration-text)' \
            '--project[Explicit project root]:directory:_files -/' \
            '--audio[Reference WAV]:file:_files' \
            '--transcript-file[Exact UTF-8 transcript]:file:_files' \
            '--transcript[Exact inline transcript]:text:' \
            '--reference-id[Saved reference identity]' \
            '--duration[Record length in seconds]:duration:' \
            '--gain[ALSA capture gain 0-50]:gain:' \
            '--device[Capture device]:device:' \
            '--calibration-text[Record standard calibration text]' \
            '--variant[Calibration text variant]:variant:(phonetic short)' \
            '--language[Language code]:language:(de en)' \
            '--voice-description[Voice description for synthetic generation]:text:' \
            '-o[Save raw recorded WAV]:file:_files' \
            '--output[Save raw recorded WAV]:file:_files'
          ;;
        audio-direction)
          _arguments \
            '1:action:(inspect add save remove)' \
            '--help[Help]' \
            '--project[Explicit project root]:directory:_files -/' \
            '--manuscript[Selected manuscript]:file:_files' \
            '--input[Direction JSON file]:file:_files' \
            '--id[Observed direction ID]:id:' \
            '--replace-id[Original range ID for bounds edits]:id:' \
            '--expected-source[Observed manuscript hash]:sha256:' \
            '--expected-settings[Observed settings hash]:sha256:' \
            '--expected-direction[Observed direction state hash]:sha256:' \
            '--chapter[Chapter number]:number:' \
            '--line[Source line]:number:' \
            '--instruction[Delivery instruction]:text:' \
            '--profile-id[Saved voice profile]:id:' \
            '--pause-before[Pause before in seconds]:seconds:' \
            '--pause-after[Pause after in seconds]:seconds:' \
            '--start[Spoken code-point start offset]:offset:' \
            '--end[Spoken code-point end offset]:offset:'
          ;;
        audio-migrate)
          _arguments \
            '--help[Help]' \
            '--project[Explicit project root]:directory:_files -/' \
            '--to-schema-3[Prepare audio schema upgrade for Coqui]' \
            '--to-schema-4[Prepare audio schema upgrade for external providers]' \
            '--to-schema-5[Prepare audio schema upgrade for phonetics and prosody]' \
            '*--replace[Explicit PROFILE=VOICE replacement]:profile=preset:' \
            '*--instructions[Explicit PROFILE=TEXT delivery]:profile=text:' \
            '--apply[Apply the reviewed candidate]' \
            '--backup[New backup ZIP outside the project]:file:_files' \
            '--expected-snapshot[Reviewed preview snapshot token]:sha256:'
          ;;
        research)
          _arguments \
            '1:action:(__LIXITY_RESEARCH_COMMANDS__)' \
            '--project[Explicit project root]:directory:_files -/' \
            '--file[UTF-8 source]:file:_files' \
            '--manuscript[Path to manuscript file]:file:_files' \
            '--title[Source or project title]:title:' \
            '--language[Language]:language:(en de fr es it pt nl generic)' \
            '--actor[Local actor]:actor:' \
            '--source-id[Source identifier]:id:' \
            '--version-id[Explicit source version identifier]:id:' \
            '--reason[Reason for action]:reason:' \
            '--allow-retention[Confirm local retention permission]' \
            '--dry-run[Preview without writing]' \
            '--context[Source criticism context JSON file]:file:_files' \
            '--thresholds[Analysis thresholds]:thresholds:' \
            '--query[Literal search words]:query:' \
            '--limit[Maximum hits]:limit:' \
            '--passage[Immutable passage ID]:id:'
          ;;
        completion)
          _values 'shell' bash zsh sh
          ;;
        project-backup)
          _arguments \
            '--project[Explicit project root]:directory:_files -/' \
            '--manuscript[Selected project-relative manuscript]:file:_files' \
            '*--settings[Selected root settings file]:file:_files' \
            '*--attachment[Selected project-relative attachment]:file:_files' \
            '--output[New bundle directory]:directory:_files -/' \
            '--help[Help]'
          ;;
        project-restore)
          _arguments \
            '--from[Verified project bundle]:directory:_files -/' \
            '--to[New project directory]:directory:_files -/' \
            '--help[Help]'
          ;;
        project)
          _arguments '1:project directory:_files -/' \\
            '--project[Explicit project root]:directory:_files -/' '--json[JSON inspection]' '--help[Help]'
          ;;
        analysis-review)
          _arguments \
            '--project[Explicit project root]:directory:_files -/' \
            '--manuscript[Selected manuscript]:file:_files' \
            '--language[Analysis language]:language:(en de fr es it pt nl generic auto)' \
            '--tense-model[Installed local syntax model]:model:' \
            '--tense-scope[Grammatical tense scope]:scope:(all narration)' \
            '--json[Versioned observations and state]' \
            '--observation[Reviewed observation identity]:sha256:' \
            '--status[Author assertion]:status:(kept changed later)' \
            '--expected-source-sha256[Reviewed manuscript digest]:sha256:' \
            '--expected-analysis-sha256[Reviewed analysis digest]:sha256:' \
            '--expected-review-sha256[Reviewed decision digest]:sha256:' \
            '--help[Help]'
          ;;
        doctor)
          _arguments '--json[JSON diagnostics]' '--port[Service port]:port:' '--help[Help]'
          ;;
        about|schema)
          _arguments '--json[JSON output]' '--help[Help]' \
            '--section[One metadata section as JSON]:section:(__LIXITY_ABOUT_SECTIONS__)'
          ;;
        scenes)
          _arguments \
            '1:manuscript:_files' \
            '--project[Explicit project root]:directory:_files -/' \
            '--help[Help]' \
            '--language[Language profile]:profile:(auto de en fr es it pt nl generic)' \
            '--json[Scene JSON with selection scope]' \
            '--chapter[Canonical chapter number]:chapter:' \
            '(--latest)--scene[Exact measured or planned scene ID]:scene:' \
            '(--scene)--latest[Last measured scene in document order]'
          ;;
        profile)
          _arguments \
            '1:manuscript:_files' \
            '--project[Explicit project root]:directory:_files -/' \
            '--help[Help]' \
            '--language[Language profile]:profile:(auto de en fr es it pt nl generic)' \
            '--json[JSON output]' \
            '--layer[Paragraph metric]:layer:(__LIXITY_PARAGRAPH_LAYERS__)' \
            '--only-notable[With a layer, select notable paragraphs after comparison]' \
            '--evidence[With a layer, show exact counted passage evidence]' \
            '-o[output file]:file:_files' \
            '--output[output file]:file:_files' \
            "${_lixity_style_flags[@]}"
          ;;
        serve)
          _arguments \
            '1:path:_files' \
            '--host[Bind address]:host:' \
            '--port[Port]:port:' \
            '--language[Language profile]:profile:(auto de en fr es it pt nl generic)' \
            '--title[Dashboard title]:title:' \
            '--open[Open in browser]' \
            '--no-project[Start without preloading a project]' \
            '--research-project[Explicit research project root]:directory:_files -/' \
            "${_lixity_style_flags[@]}"
          ;;
        export-site)
          _arguments \
            '1:manuscript:_files' \
            '--project[Explicit project root]:directory:_files -/' \
            '--language[Language profile]:profile:(auto de en fr es it pt nl generic)' \
            '--mode[Reading format]:mode:(review reader companion)' \
            '--publication-profile[Root-local reading profile]:name:' \
            '--max-chapter[Omit content after this chapter]:chapter:' \
            '*--analysis[Optional reader analysis]:section:(chapters language full all)' \
            '--include-audio[Reader: include saved current chapter audio]' \
            '--include-research[Include authored history and cited excerpts]' \
            '--include-source-files[Also include original source files and full text]' \
            '--json[Print the export manifest]' \
            '--help[Help]' \
            '-o[New website directory]:directory:_files -/' \
            '--output[New website directory]:directory:_files -/'
          ;;
        service)
          _arguments \
            '1:action:(start stop restart status)' \
            '2:project:_files' \
            '--port[Port]:port:' \
            '--host[Loopback host]:host:(127.0.0.1 localhost)' \
            '--no-project[Start an empty workspace]' \
            '--open[Open browser]' \
            '--backend[Runtime backend]:backend:(auto process systemd)' \
            '--json[Machine-readable lifecycle result]' \
            '--language[Language profile]:profile:(auto de en fr es it pt nl generic)' \
            '--title[Project title]:title:' \
            '--research-project[Explicit research root]:directory:_files -/' \
            '--debug[Enable diagnostics]' \
            "${_lixity_style_flags[@]}"
          ;;
        build)
          _arguments \
            '1:file:_files' \
            '--project[Explicit project root]:directory:_files -/' \
            '--language[language profile]:profile:(auto de en fr es it pt nl generic)' \
            '--dry-run[Show planned artifacts only]' \
            "${_lixity_style_flags[@]}"
          ;;
        motifs)
          _arguments \
            '1:file:_files' \
            '--project[Explicit project root]:directory:_files -/' \
            '--motif[NAME=REGEX]' \
            '--phrases[Phrase size]:n:' \
            '--language[language profile]:profile:(auto de en fr es it pt nl generic)' \
            '--json[JSON output]'
          ;;
        characters)
          _arguments \
            '1:file:_files' \
            '--project[Explicit project root]:directory:_files -/' \
            '--name[Figure name or alias]' \
            '--names[Comma-separated names]:names:' \
            '--language[language profile]:profile:(auto de en fr es it pt nl generic)' \
            '--json[JSON output]'
          ;;
        dashboard)
          _arguments \
            '1:file:_files' \
            '--project[Explicit project root]:directory:_files -/' \
            '--language[language profile]:profile:(auto de en fr es it pt nl generic)' \
            '--names[Character names]:names:' \
            '-o[output file]:file:_files' \
            '--output[output file]:file:_files' \
            "${_lixity_style_flags[@]}"
          ;;
        *)
          _arguments \
            '1:file:_files' \
            '--project[Explicit project root]:directory:_files -/' \
            '--language[language profile]:profile:(auto de en fr es it pt nl generic)' \
            '--json[JSON output]' \
            '-o[output file]:file:_files' \
            '--output[output file]:file:_files' \
            "${_lixity_style_flags[@]}"
          ;;
      esac
      ;;
  esac
}
_lixity "$@"
"""


def build_completion_scripts(
    commands: Sequence[tuple[str, str]],
    about_sections: Sequence[str],
) -> tuple[str, str]:
    """Build Bash and Zsh completion scripts from live command metadata."""
    from .research.cli import command_metadata

    research_actions = " ".join(
        name for command in command_metadata()
        for name in (command["name"], *command.get("aliases", []))
    )
    names = " ".join(name for name, _help in commands)
    descriptors = "\n".join(f"    '{name}:{help_text}'" for name, help_text in commands)
    sections = " ".join(about_sections)
    layers = " ".join(LAYER_FEATURES)
    bash = (
        _BASH_COMPLETION.replace("__LIXITY_COMMANDS__", names)
        .replace("__LIXITY_RESEARCH_COMMANDS__", research_actions)
        .replace("__LIXITY_ABOUT_SECTIONS__", sections)
        .replace("__LIXITY_PARAGRAPH_LAYERS__", layers)
    )
    zsh = (
        _ZSH_COMPLETION.replace("__LIXITY_ZSH_COMMANDS__", descriptors)
        .replace("__LIXITY_RESEARCH_COMMANDS__", research_actions)
        .replace("__LIXITY_ABOUT_SECTIONS__", sections)
        .replace("__LIXITY_PARAGRAPH_LAYERS__", layers)
    )
    return bash, zsh
