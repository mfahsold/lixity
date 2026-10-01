#!/usr/bin/env bash
# lixity-start.sh — Start, stop and status for Lixity on Linux and macOS.
#
# Usage:
#   ./scripts/lixity-start.sh [start|stop|restart|status] [--port PORT] [--host HOST] [--open] [PROJECT]
#
# Environment variables (override defaults):
#   LIXITY_PORT   Port to listen on (default: 8765)
#   LIXITY_HOST   Bind address     (default: 127.0.0.1)
#   LIXITY_DIR    Project path to open (optional)
#
# State lives in ${XDG_RUNTIME_DIR:-~/.local/share/lixity}/:
#   lixity-<PORT>.pid   PID of the managed instance for PORT (fallback: lixity.pid for 8765)
#   lixity-<PORT>.log   stdout+stderr of the instance (rotated to .log.1 on start)
#
# Exit codes: 0 success, 1 failure or "not running" for `status`.

set -euo pipefail

# ── Configuration Defaults ───────────────────────────────────────────────────
PORT="${LIXITY_PORT:-8765}"
HOST="${LIXITY_HOST:-127.0.0.1}"
DIR="${LIXITY_DIR:-}"
OPEN_BROWSER=0

# ── Argument parsing ──────────────────────────────────────────────────────────
case "${1:-}" in
    -h|--help|help)
        sed -n '2,15p' "$0"
        exit 0
        ;;
esac

COMMAND="${1:-start}"
if [ $# -gt 0 ]; then
    shift
fi

while [[ $# -gt 0 ]]; do
    case "$1" in
        --port)    PORT="${2:?--port needs a value}"; shift 2 ;;
        --port=*)  PORT="${1#*=}"; shift ;;
        --host)    HOST="${2:?--host needs a value}"; shift 2 ;;
        --open)    OPEN_BROWSER=1; shift ;;
        -h|--help) sed -n '2,15p' "$0"; exit 0 ;;
        *)         DIR="$1"; shift ;;
    esac
done

# ── Runtime State Paths ───────────────────────────────────────────────────────
resolve_runtime_dir() {
    if [ -n "${XDG_RUNTIME_DIR:-}" ] && [ -d "$XDG_RUNTIME_DIR" ] && [ -w "$XDG_RUNTIME_DIR" ]; then
        echo "$XDG_RUNTIME_DIR"
    elif mkdir -p "${HOME}/.local/share/lixity" 2>/dev/null && [ -w "${HOME}/.local/share/lixity" ]; then
        echo "${HOME}/.local/share/lixity"
    else
        local fallback_dir="/tmp/lixity-${EUID:-${UID:-$(id -u)}}"
        mkdir -p "$fallback_dir" 2>/dev/null || true
        echo "$fallback_dir"
    fi
}

RUNTIME_DIR="$(resolve_runtime_dir)"

resolve_pid_file() {
    local target="${RUNTIME_DIR}/lixity-${PORT}.pid"
    if [ ! -f "$target" ] && [ "$PORT" = "8765" ] && [ -f "${RUNTIME_DIR}/lixity.pid" ]; then
        echo "${RUNTIME_DIR}/lixity.pid"
    else
        echo "$target"
    fi
}

PID_FILE="$(resolve_pid_file)"
LOG_FILE="${RUNTIME_DIR}/lixity-${PORT}.log"

# ── Helpers ───────────────────────────────────────────────────────────────────
die()  { echo "[ERR] $*" >&2; exit 1; }
info() { echo "[OK]  $*"; }

# Resolve the lixity binary: prefer a venv in the current directory.
resolve_lixity() {
    if [ -x ".venv/bin/lixity" ]; then
        echo ".venv/bin/lixity"
    elif command -v lixity &>/dev/null; then
        echo "lixity"
    else
        die "lixity not found. Install with: uv tool install 'git+https://github.com/mfahsold/lixity.git'"
    fi
}

# Read the full command line of a PID, or nothing when it cannot be determined.
read_cmdline() {
    local pid="$1"
    if [ -r "/proc/${pid}/cmdline" ]; then
        tr '\0' ' ' < "/proc/${pid}/cmdline" 2>/dev/null || true
    else
        ps -p "$pid" -o command= 2>/dev/null || true
    fi
}

# True when the recorded PID is alive and still looks like a Lixity server.
# Stale PID files or recycled PIDs from unrelated processes are cleaned up.
recorded_pid_is_live() {
    [ -s "$PID_FILE" ] || return 1
    local pid cmdline
    pid="$(tr -dc '0-9' < "$PID_FILE")"
    [ -n "$pid" ] || { rm -f "$PID_FILE"; return 1; }
    if ! kill -0 "$pid" 2>/dev/null; then
        rm -f "$PID_FILE"
        return 1
    fi
    cmdline="$(read_cmdline "$pid")"
    if [ -n "$cmdline" ]; then
        case "$cmdline" in
            *lixity*) return 0 ;;
            *)
                # Recycled PID pointing at an unrelated process
                rm -f "$PID_FILE"
                return 1
                ;;
        esac
    fi
    return 0
}

recorded_pid() {
    tr -dc '0-9' < "$PID_FILE" 2>/dev/null || true
}

# True once the port accepts a TCP connection.
port_accepts_connections() {
    (exec 3<>"/dev/tcp/${HOST}/${PORT}") 2>/dev/null && exec 3<&- && exec 3>&-
}

port_in_use() {
    if command -v ss &>/dev/null; then
        ss -tln 2>/dev/null | grep -qE "[:.]${PORT}[[:space:]]"
    elif command -v lsof &>/dev/null; then
        lsof -i "TCP:${PORT}" -sTCP:LISTEN &>/dev/null
    else
        return 1  # Cannot check; let lixity report the error.
    fi
}

clean_pid_file() {
    rm -f "$PID_FILE"
    if [ "$PORT" = "8765" ]; then
        rm -f "${RUNTIME_DIR}/lixity.pid"
    fi
}

# ── Commands ──────────────────────────────────────────────────────────────────
cmd_start() {
    if recorded_pid_is_live; then
        local live_pid
        live_pid="$(recorded_pid)"
        if port_accepts_connections; then
            info "Lixity is already running (PID ${live_pid}) → http://${HOST}:${PORT}/"
            exit 0
        fi
        clean_pid_file
    fi
    clean_pid_file

    if port_in_use; then
        die "Port ${PORT} is already in use by another process.
     Choose a different port:  LIXITY_PORT=<PORT> $0 start
     Find what is using it:    lsof -i :${PORT}"
    fi

    mkdir -p "$RUNTIME_DIR"
    LIXITY_BIN="$(resolve_lixity)"

    SERVE_ARGS=(serve --host "$HOST" --port "$PORT")
    if [ -n "$DIR" ]; then SERVE_ARGS+=("$DIR"); fi
    if [ "$OPEN_BROWSER" -eq 1 ]; then SERVE_ARGS+=(--open); fi

    # Rotate rather than append: a readiness grep below must never match a line
    # left behind by a previous run and report success for a process that died.
    [ -f "$LOG_FILE" ] && mv -f "$LOG_FILE" "${LOG_FILE}.1"

    nohup "$LIXITY_BIN" "${SERVE_ARGS[@]}" > "$LOG_FILE" 2>&1 &
    PID=$!
    echo "$PID" > "$PID_FILE"
    if [ "$PORT" = "8765" ]; then
        # Maintain compatibility for tools reading legacy lixity.pid
        cp -f "$PID_FILE" "${RUNTIME_DIR}/lixity.pid" 2>/dev/null || true
    fi

    # Wait up to 15 s for the port to accept connections.
    for _ in $(seq 1 60); do
        if port_accepts_connections; then
            info "Lixity started (PID ${PID}) → http://${HOST}:${PORT}/"
            info "Log: ${LOG_FILE}"
            exit 0
        fi
        if ! kill -0 "$PID" 2>/dev/null; then
            clean_pid_file
            echo "[ERR] Lixity exited during startup:" >&2
            sed 's/^/      /' "$LOG_FILE" >&2 2>/dev/null || true
            exit 1
        fi
        sleep 0.25
    done

    # Alive but not listening yet. Say so honestly instead of claiming success.
    echo "[ERR] Lixity is running (PID ${PID}) but ${HOST}:${PORT} is not accepting" >&2
    echo "       connections after 15 s. Check: ${LOG_FILE}" >&2
    exit 1
}

cmd_stop() {
    if ! recorded_pid_is_live || ! port_accepts_connections; then
        clean_pid_file
        info "Lixity is not running."
        exit 0
    fi
    PID="$(recorded_pid)"
    kill "$PID" 2>/dev/null || true
    for _ in $(seq 1 20); do
        kill -0 "$PID" 2>/dev/null || break
        sleep 0.25
    done
    if kill -0 "$PID" 2>/dev/null; then
        info "PID ${PID} ignored SIGTERM; sending SIGKILL."
        kill -9 "$PID" 2>/dev/null || true
        sleep 0.5
    fi
    clean_pid_file
    info "Lixity stopped (PID ${PID})."
}

cmd_restart() {
    cmd_stop
    cmd_start
}

cmd_status() {
    if recorded_pid_is_live && port_accepts_connections; then
        local pid
        pid="$(recorded_pid)"
        info "Lixity is running (PID ${pid}) → http://${HOST}:${PORT}/"
        exit 0
    else
        clean_pid_file
        echo "[--]  Lixity is not running."
        exit 1
    fi
}

# ── Dispatch ──────────────────────────────────────────────────────────────────
case "$COMMAND" in
    start)   cmd_start   ;;
    stop)    cmd_stop    ;;
    restart) cmd_restart ;;
    status)  cmd_status  ;;
    *)       die "Unknown command: ${COMMAND}. Usage: $0 [start|stop|restart|status]" ;;
esac
