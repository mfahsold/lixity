#!/usr/bin/env bash
# Run the same display and accessibility probe against both applications.
set -euo pipefail

if [[ ${1:-} == probe ]]; then
  stage=$2
  shift 2
  export LANG=C.UTF-8 LC_ALL=C.UTF-8 XDG_SESSION_TYPE=x11 GTK_A11Y=1 NO_AT_BRIDGE=0
  export LIBGL_ALWAYS_SOFTWARE=1 WEBKIT_DISABLE_DMABUF_RENDERER=1 WEBKIT_DISABLE_COMPOSITING_MODE=1
  openbox > "$QA_OUTPUT/$stage-window-manager.log" 2>&1 &
  window_manager=$!
  if [[ $stage == control ]]; then
    command=(/usr/bin/python3 "$QA_SCRIPTS/control.py")
  else
    command=(/usr/bin/lixity-desktop)
  fi
  "${command[@]}" > "$QA_OUTPUT/$stage-app.log" 2>&1 &
  application=$!
  trap 'kill "$application" "$window_manager" 2>/dev/null || true' EXIT

  result=0
  timeout 65 /usr/bin/python3 "$QA_SCRIPTS/observe.py" "$QA_OUTPUT/$stage-tree.json" "$@" \
    > "$QA_OUTPUT/$stage-observer.log" 2>&1 || result=$?
  cat "$QA_OUTPUT/$stage-observer.log"
  # The accessibility tree can populate before the first painted frame.
  if [[ $result == 0 ]]; then sleep 3; fi
  xwd -root -silent -out "$QA_OUTPUT/$stage.xwd" || true
  xdotool search --onlyvisible --name . getwindowname %@ > "$QA_OUTPUT/$stage-windows.txt" 2>&1 || true
  exit "$result"
fi

run_stage() {
  local stage=$1
  shift
  local profile
  profile=$(mktemp -d)
  mkdir -m 700 "$profile/run"
  HOME="$profile" XDG_RUNTIME_DIR="$profile/run" XDG_CONFIG_HOME="$profile/config" \
    XDG_CACHE_HOME="$profile/cache" XDG_STATE_HOME="$profile/state" XDG_DATA_HOME="$profile/data" \
    timeout 90 xvfb-run -a -s '-screen 0 1440x950x24 -nolisten tcp' dbus-run-session -- \
      bash "$QA_SCRIPTS/launch.sh" probe "$stage" "$@" > "$QA_OUTPUT/$stage-session.log" 2>&1
  local result=$?
  if [[ -f "$profile/state/lixity/service/desktop-sidecar.log" ]]; then
    cp "$profile/state/lixity/service/desktop-sidecar.log" "$QA_OUTPUT/$stage-sidecar.log"
  fi
  cat "$QA_OUTPUT/$stage-session.log"
  return "$result"
}

control=0
lixity=0
run_stage control 'Stock WebKitGTK rendered this document' 'Visible WebKitGTK control' || control=$?
run_stage lixity 'Welcome to Lixity' 'Open a project folder' 'Try the example offline' || lixity=$?
printf 'Stock WebKitGTK control exit: %s\nLixity Welcome exit: %s\n' "$control" "$lixity" | tee "$QA_OUTPUT/result.txt"
[[ $control == 0 && $lixity == 0 ]]
