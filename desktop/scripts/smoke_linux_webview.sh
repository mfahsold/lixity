#!/usr/bin/env bash
# Exercise an already installed, checksum-verified DEB in an isolated X11 session.
set -euo pipefail

scripts=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)

if [[ ${1:-} == --probe ]]; then
  stage=$2
  export LANG=C.UTF-8 LC_ALL=C.UTF-8 XDG_SESSION_TYPE=x11 GTK_A11Y=1 NO_AT_BRIDGE=0
  export LIBGL_ALWAYS_SOFTWARE=1 WEBKIT_DISABLE_DMABUF_RENDERER=1 WEBKIT_DISABLE_COMPOSITING_MODE=1
  openbox > "$LIXITY_QA_OUTPUT/$stage-window-manager.log" 2>&1 &
  window_manager=$!
  if [[ $stage == control ]]; then
    command=(/usr/bin/python3 "$scripts/smoke_linux_webview.py" control)
  else
    command=(/usr/bin/lixity-desktop)
  fi
  "${command[@]}" > "$LIXITY_QA_OUTPUT/$stage-app.log" 2>&1 &
  application=$!
  trap 'kill "$application" "$window_manager" 2>/dev/null || true' EXIT
  timeout 95 /usr/bin/python3 "$scripts/smoke_linux_webview.py" "$stage" "$LIXITY_QA_OUTPUT" \
    "$scripts/../../samples/first-look.md"
  exit
fi

if [[ ${1:-} == --isolated ]]; then
  ip -o link show > "$LIXITY_QA_OUTPUT/network.txt"
  run_stage() {
    local stage=$1 profile
    profile=$(mktemp -d "$LIXITY_QA_TEMP/profile.XXXXXX") || return
    mkdir -m 700 "$profile/run" || return
    local result=0
    HOME="$profile" XDG_RUNTIME_DIR="$profile/run" XDG_CONFIG_HOME="$profile/config" \
      XDG_CACHE_HOME="$profile/cache" XDG_STATE_HOME="$profile/state" XDG_DATA_HOME="$profile/data" \
      timeout 110 xvfb-run -a -s '-screen 0 1440x950x24 -nolisten tcp' dbus-run-session -- \
      bash "$scripts/smoke_linux_webview.sh" --probe "$stage" \
      > "$LIXITY_QA_OUTPUT/$stage-session.log" 2>&1 || result=$?
    local sidecar="$profile/state/lixity/service/desktop-sidecar.log"
    if [[ -f $sidecar ]]; then cp -- "$sidecar" "$LIXITY_QA_OUTPUT/$stage-sidecar.log"; fi
    cat "$LIXITY_QA_OUTPUT/$stage-session.log"
    return "$result"
  }

  control=0
  lixity=0
  run_stage control || control=$?
  run_stage lixity || lixity=$?
  printf 'Stock WebKitGTK control exit: %s\nLixity offline example exit: %s\n' "$control" "$lixity" \
    | tee "$LIXITY_QA_OUTPUT/result.txt"
  [[ $control == 0 && $lixity == 0 ]]
  exit
fi

if [[ $# -ne 3 || ! -f $1 || $1 != *.deb || ! $2 =~ ^[a-f0-9]{64}$ ]]; then
  echo "Usage: $0 /path/to/lixity-amd64.deb EXPECTED_SHA256 /path/to/new-evidence-directory" >&2
  exit 2
fi
if [[ $(uname -s) != Linux || $(uname -m) != x86_64 || $EUID == 0 ]]; then
  echo 'Run this check as an ordinary user on a disposable Linux x86-64 system.' >&2
  exit 2
fi

package=$(realpath -- "$1")
printf '%s  %s\n' "$2" "$package" | sha256sum --strict -c -
if [[ $(dpkg-deb -f "$package" Package) != lixity || $(dpkg-deb -f "$package" Architecture) != amd64 ]]; then
  echo 'Expected a Lixity amd64 DEB.' >&2
  exit 2
fi
version=$(dpkg-deb -f "$package" Version)
if [[ $(dpkg-query -W -f='${Status} ${Version} ${Architecture}' lixity) != "install ok installed $version amd64" ]]; then
  echo 'Install the verified DEB on the test system before running this check.' >&2
  exit 2
fi

temp=$(mktemp -d)
trap 'rm -rf -- "$temp"' EXIT
dpkg-deb --control "$package" "$temp/control"
# Use the DEB's file inventory to catch stale or modified installed payloads.
(cd / && md5sum --quiet --strict -c "$temp/control/md5sums")
mkdir -- "$3"
output=$(realpath -- "$3")
{
  printf 'Installer: %s\nSHA-256: %s\nArchitecture: %s\n' "$(basename -- "$package")" "$2" "$(uname -m)"
  cat /etc/os-release
  dpkg-query -W lixity libwebkit2gtk-4.1-0
  printf 'Display: Xvfb with software rendering\n'
} > "$output/environment.txt"

# Add only loopback to a private network namespace and run both GUI probes as the caller.
sudo unshare --net -- bash -euc '
  ip link set lo up
  exec runuser -u "$1" -- env LIXITY_QA_OUTPUT="$2" LIXITY_QA_TEMP="$3" bash "$4" --isolated
' qa "$(id -un)" "$output" "$temp" "$scripts/smoke_linux_webview.sh"
