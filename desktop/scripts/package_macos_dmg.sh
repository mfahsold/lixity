#!/usr/bin/env bash
# Package an ALREADY SIGNED Lixity.app bundle into a compressed UDZO macOS .dmg
# with an Applications shortcut and installation guide. Optionally sign and
# notarize the .dmg, then mount it read-only to verify its contents.
# Pass a Python executable to smoke-test the runtime in the mounted bundle.
set -euo pipefail

if [ $# -lt 2 ] || [ $# -gt 3 ]; then
    echo "Usage: $0 /path/to/Lixity.app /path/to/output.dmg [python-executable]" >&2
    exit 2
fi

APP_BUNDLE="$1"
OUT_DMG="$2"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
INSTALL_GUIDE="$SCRIPT_DIR/../packaging/macos/install-guide.html"
INSTALL_GUIDE_NAME="Start Here - Hier starten.html"

# On older macOS versions, diskutil can create an image from a disk but
# cannot package a directory with a named volume.
USE_DISKUTIL=0
if IMAGE_HELP=$(diskutil image create from --help 2>/dev/null) && [[ "$IMAGE_HELP" == *--volumeName* ]]; then
    USE_DISKUTIL=1
fi

if [ ! -d "$APP_BUNDLE" ]; then
    echo "[ERR] App bundle not found: $APP_BUNDLE" >&2
    exit 1
fi

echo "[1/4] Verifying signed Lixity.app before DMG packaging..."
codesign --verify --deep --strict "$APP_BUNDLE"

STAGE_DIR="$(mktemp -d "${TMPDIR:-/tmp}/lixity-dmg-stage.XXXXXX")"
VERIFY_MNT="$(mktemp -d "${TMPDIR:-/tmp}/lixity-dmg-verify.XXXXXX")"
MOUNTED=0
eject_once() {
    if [ "$USE_DISKUTIL" -eq 1 ]; then
        diskutil eject "$VERIFY_MNT" >/dev/null
    else
        hdiutil detach "$VERIFY_MNT" >/dev/null
    fi
}

eject_image() {
    local attempt
    for attempt in 1 2 3; do
        if eject_once; then
            return 0
        fi
        # macOS can still be inspecting the signed bundle after verification.
        if [ "$attempt" -lt 3 ]; then
            sleep 2
        fi
    done
    return 1
}

cleanup() {
    if [ "$MOUNTED" -eq 1 ]; then
        eject_once || true
    fi
    rmdir "$VERIFY_MNT" 2>/dev/null || true
    rm -rf "$STAGE_DIR"
}
trap cleanup EXIT

echo "[2/4] Staging signed Lixity.app, Applications shortcut and installation guide..."
ditto "$APP_BUNDLE" "$STAGE_DIR/Lixity.app"
ln -s /Applications "$STAGE_DIR/Applications"
install -m 0644 "$INSTALL_GUIDE" "$STAGE_DIR/$INSTALL_GUIDE_NAME"

mkdir -p "$(dirname "$OUT_DMG")"
rm -f "$OUT_DMG"

echo "[3/4] Creating compressed UDZO DMG at $OUT_DMG..."
if [ "$USE_DISKUTIL" -eq 1 ]; then
    diskutil image create from --format UDZO --volumeName Lixity "$STAGE_DIR" "$OUT_DMG"
else
    hdiutil create -volname Lixity -srcfolder "$STAGE_DIR" -format UDZO \
        -imagekey zlib-level=9 "$OUT_DMG"
fi

if [ -n "${APPLE_SIGNING_IDENTITY:-}" ]; then
    echo "[INFO] Signing DMG with Developer ID identity..."
    SIGN_ARGS=(--force --timestamp --sign "$APPLE_SIGNING_IDENTITY")
    if [ -n "${APPLE_SIGNING_KEYCHAIN:-}" ]; then
        SIGN_ARGS+=(--keychain "$APPLE_SIGNING_KEYCHAIN")
    fi
    codesign "${SIGN_ARGS[@]}" "$OUT_DMG"
    if [ -n "${APPLE_NOTARY_PROFILE:-}" ]; then
        echo "[INFO] Submitting DMG for Apple notarization..."
        NOTARY_ARGS=(--keychain-profile "$APPLE_NOTARY_PROFILE" --wait)
        if [ -n "${APPLE_SIGNING_KEYCHAIN:-}" ]; then
            NOTARY_ARGS+=(--keychain "$APPLE_SIGNING_KEYCHAIN")
        fi
        xcrun notarytool submit "$OUT_DMG" "${NOTARY_ARGS[@]}"
        xcrun stapler staple "$OUT_DMG"
        xcrun stapler validate "$OUT_DMG"
        codesign --verify --strict --verbose=2 "$OUT_DMG"
        spctl --assess --type open --context context:primary-signature --verbose=4 "$OUT_DMG"
    fi
fi

echo "[4/4] Mounting DMG read-only to verify embedded Lixity.app signature..."
if [ "$USE_DISKUTIL" -eq 1 ]; then
    diskutil image attach --nobrowse --readOnly --mountPoint "$VERIFY_MNT" "$OUT_DMG" >/dev/null
else
    hdiutil attach -nobrowse -readonly -mountpoint "$VERIFY_MNT" "$OUT_DMG" >/dev/null
fi
MOUNTED=1
codesign --verify --deep --strict --verbose=2 "$VERIFY_MNT/Lixity.app"
if [ -n "${APPLE_SIGNING_IDENTITY:-}" ] && [ -n "${APPLE_NOTARY_PROFILE:-}" ]; then
    xcrun stapler validate "$VERIFY_MNT/Lixity.app"
fi
cmp "$INSTALL_GUIDE" "$VERIFY_MNT/$INSTALL_GUIDE_NAME"
if [ $# -eq 3 ]; then
    "$3" "$SCRIPT_DIR/smoke_desktop_runtime.py" "$VERIFY_MNT/Lixity.app/Contents/Resources/runtime"
fi
eject_image
MOUNTED=0

echo "[OK] Packaged and verified macOS DMG: $OUT_DMG"
