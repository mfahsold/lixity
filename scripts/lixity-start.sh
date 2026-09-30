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
#   lixity.pid   PID of the managed instance
#   lixity.log   stdout+stderr of the current instance (rotated to .log.1)
#
# Exit codes: 0 success, 1 failure or "not running" for `status`.

set -euo pipefail

# ── Configuration ─────────────────────────────────────────────────────────────
PORT="${LIXITY_PORT:-8765}"
HOST="${LIXITY_HOST:-127.0.0.1}"
DIR="${LIXITY_DIR:-}"
OPEN_BROWSER=0

RUNTIME_DIR="${XDG_RUNTIME_DIR:-${HOME}/.local/share/lixity}"
PID_FILE="${RUNTIME_DIR}/lixity.pid"
LOG_FILE="${RUNTIME_DIR}/lixity.log"

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
#
# The command-line check guards against PID reuse (a recorded PID recycled by an
# unrelated process would otherwise make status/stop target the wrong process).
# When the command line cannot be read we fall back to plain liveness rather than
# reporting a false "not running".
recorded_pid_is_live() {
    [ -s "$PID_FILE" ] || return 1
    local pid cmdline
    pid="$(tr -dc '0-9' < "$PID_FILE")"
    [ -n "$pid" ] || return 1
    kill -0 "$pid" 2>/dev/null || return 1
    cmdline="$(read_cmdline "$pid")"
    [ -n "$cmdline" ] || return 0
    case "$cmdline" in
        *lixity*) return 0 ;;
        *)         return 1 ;;
    esac
}

recorded_pid() {
    tr -dc '0-9' < "$PID_FILE" 2>/dev/null || true
}

# True once the port accepts a TCP connection.
#
# Deliberately not a log grep: the server prints its banner with print(), and
# stdout redirected to a file is block-buffered, so for a long-running process
# the banner can sit in the buffer indefinitely. A log-based readiness check
# therefore never succeeds. Connecting to the port is both direct and
# buffering-independent.
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

# ── Commands ──────────────────────────────────────────────────────────────────
cmd_start() {
    if recorded_pid_is_live; then
        info "Lixity is already running (PID $(recorded_pid)) → http://${HOST}:${PORT}/"
        exit 0
    fi
    rm -f "$PID_FILE"

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

    # Wait up to 15 s for the port to accept connections.
    for _ in $(seq 1 60); do
        if port_accepts_connections; then
            info "Lixity started (PID ${PID}) → http://${HOST}:${PORT}/"
            info "Log: ${LOG_FILE}"
            exit 0
        fi
        if ! kill -0 "$PID" 2>/dev/null; then
            rm -f "$PID_FILE"
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
    if ! recorded_pid_is_live; then
        rm -f "$PID_FILE"
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
    rm -f "$PID_FILE"
    info "Lixity stopped (PID ${PID})."
}

cmd_restart() {
    cmd_stop
    cmd_start
}

cmd_status() {
    if recorded_pid_is_live; then
        info "Lixity is running (PID $(recorded_pid)) → http://${HOST}:${PORT}/"
    else
        echo "[--]  Lixity is not running."
        exit 1
    fi
}

# ── Argument parsing ──────────────────────────────────────────────────────────
COMMAND="${1:-start}"
shift || true

while [[ $# -gt 0 ]]; do
    case "$1" in
        --port)    PORT="${2:?--port needs a value}"; shift 2 ;;
        --port=*)  PORT="${1#*=}"; shift ;;
        --host)    HOST="${2:?--host needs a value}"; shift 2 ;;
        --open)    OPEN_BROWSER=1; shift ;;
        -h|--help) sed -n '2,14p' "$0"; exit 0 ;;
        *)         DIR="$1"; shift ;;
    esac
done

case "$COMMAND" in
    start)   cmd_start   ;;
    stop)    cmd_stop    ;;
    restart) cmd_restart ;;
    status)  cmd_status  ;;
    *)       die "Unknown command: ${COMMAND}. Usage: $0 [start|stop|restart|status]" ;;
esac
