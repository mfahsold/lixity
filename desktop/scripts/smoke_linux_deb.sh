#!/usr/bin/env bash
# Resolve the installed Rust host's dependencies in a fresh Ubuntu container.
set -euo pipefail

if [[ $# -ne 1 || ! -f $1 || $1 != *.deb ]]; then
  echo "Usage: $0 /path/to/lixity-amd64.deb" >&2
  exit 2
fi

package_dir=$(cd -- "$(dirname -- "$1")" && pwd -P)
package_name=$(basename -- "$1")
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)

docker run --rm --platform linux/amd64 \
  --mount "type=bind,source=$package_dir,target=/installers,readonly" \
  --mount "type=bind,source=$script_dir/smoke_desktop_runtime.py,target=/smoke_desktop_runtime.py,readonly" \
  ubuntu:22.04 bash -euc '
    export DEBIAN_FRONTEND=noninteractive
    apt-get -o Acquire::Retries=3 update -qq
    apt-get -o Acquire::Retries=3 install -y -qq --no-install-recommends "$1"
    dpkg-query -W -f="\${Package} \${Version} (\${Architecture})\n" lixity
    /lib64/ld-linux-x86-64.so.2 --list /usr/bin/lixity-desktop
    runtime=/usr/lib/Lixity/runtime
    "$runtime/python/bin/python3.12" -I -B /smoke_desktop_runtime.py "$runtime"
  ' bash "/installers/$package_name"
