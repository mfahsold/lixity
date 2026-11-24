#!/usr/bin/env bash
# Prepare an isolated Developer ID keychain for an opt-in GitHub Actions build.
set -euo pipefail
umask 077

required=(APPLE_DEVELOPER_ID_P12_BASE64 APPLE_DEVELOPER_ID_P12_PASSWORD
          APPLE_NOTARY_KEY_P8_BASE64 APPLE_NOTARY_KEY_ID APPLE_NOTARY_ISSUER_ID)
for name in "${required[@]}"; do
    if [ -z "${!name:-}" ]; then
        echo "Missing GitHub secret $name for the macOS notarized build." >&2
        exit 1
    fi
done

: "${RUNNER_TEMP:?Expected GitHub runner temp directory}"
: "${GITHUB_OUTPUT:?Expected GitHub step output file}"
keychain="$RUNNER_TEMP/lixity-developer-id.keychain-db"
if [ -e "$keychain" ]; then
    echo "The temporary Developer ID keychain already exists." >&2
    exit 1
fi
temporary="$(mktemp -d "$RUNNER_TEMP/lixity-signing.XXXXXX")"
ready=0
cleanup() {
    rm -rf "$temporary"
    if [ "$ready" -eq 0 ] && [ -f "$keychain" ]; then
        security delete-keychain "$keychain"
    fi
}
trap cleanup EXIT

printf '%s' "$APPLE_DEVELOPER_ID_P12_BASE64" | base64 -D > "$temporary/developer-id.p12"
printf '%s' "$APPLE_NOTARY_KEY_P8_BASE64" | base64 -D > "$temporary/notary-key.p8"
password="$(openssl rand -hex 32)"
printf '::add-mask::%s\n' "$password"
security create-keychain -p "$password" "$keychain"
security unlock-keychain -p "$password" "$keychain"
security set-keychain-settings -lut 3600 "$keychain"
security import "$temporary/developer-id.p12" -P "$APPLE_DEVELOPER_ID_P12_PASSWORD" \
    -T /usr/bin/codesign -t cert -f pkcs12 -k "$keychain"
security set-key-partition-list -S apple-tool:,apple: -s -k "$password" "$keychain" >/dev/null
identity="$(security find-identity -v -p codesigning "$keychain" | awk '/"Developer ID Application: / {print $2}')"
if ! [[ "$identity" =~ ^[[:xdigit:]]{40}$ ]]; then
    echo "Expected exactly one valid Developer ID Application identity in the certificate." >&2
    exit 1
fi

profile=lixity-release-notary
xcrun notarytool store-credentials "$profile" --keychain "$keychain" \
    --key "$temporary/notary-key.p8" --key-id "$APPLE_NOTARY_KEY_ID" --issuer "$APPLE_NOTARY_ISSUER_ID"
printf 'identity=%s\nkeychain=%s\nprofile=%s\n' "$identity" "$keychain" "$profile" >> "$GITHUB_OUTPUT"
ready=1
