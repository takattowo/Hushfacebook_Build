#!/usr/bin/env bash
# Patch the Facebook APK with the Hushfacebook bundle using morphe-desktop CLI.
# No --force: if the APK version does not match the bundle, the patcher aborts.
set -euo pipefail

FB_VERSION="$1"
HUSH_TAG="$2"
APK="$3"
AMOLED="${AMOLED:-false}"
MATERIAL_YOU="${MATERIAL_YOU:-false}"

if [ "$AMOLED" = "true" ] && [ "$MATERIAL_YOU" = "true" ]; then
  echo "::error::AMOLED and Material You variants cannot be enabled together"
  exit 1
fi

: "${KEYSTORE_BASE64:?Missing KEYSTORE_BASE64 Actions secret}"
: "${KEYSTORE_PASSWORD:?Missing KEYSTORE_PASSWORD Actions secret}"
KEYSTORE_FILE=$(mktemp "${RUNNER_TEMP:-${TMPDIR:-/tmp}}/hushfacebook-keystore.XXXXXX")
trap 'rm -f "$KEYSTORE_FILE"' EXIT
printf '%s' "$KEYSTORE_BASE64" | base64 --decode > "$KEYSTORE_FILE"

JAR=$(ls morphe-desktop-*-all.jar)
MPP=$(ls patches-*.mpp)

SUFFIX=""
if [ "$AMOLED" = "true" ]; then
  SUFFIX="-amoled"
elif [ "$MATERIAL_YOU" = "true" ]; then
  SUFFIX="-material-you"
fi
OUT="Hushfacebook-${FB_VERSION}-${HUSH_TAG}${SUFFIX}.apk"

ARGS=(
  patch
  -p "$MPP"
  -o "$OUT"
  --keystore "$KEYSTORE_FILE"
  --keystore-password "$KEYSTORE_PASSWORD"
  --keystore-entry-alias hush
  --keystore-entry-password "$KEYSTORE_PASSWORD"
)

if [ "$AMOLED" = "true" ]; then
  ARGS+=(-e "AMOLED black theme")
elif [ "$MATERIAL_YOU" = "true" ]; then
  ARGS+=(-e "Material You theme")
fi

echo "== Patching $APK -> $OUT (amoled=$AMOLED, material_you=$MATERIAL_YOU)"
java -jar "$JAR" "${ARGS[@]}" "$APK"

if [ ! -f "$OUT" ]; then
  echo "::error::Patch reported success but $OUT is missing"
  exit 1
fi

ls -la "$OUT"
echo "out=$OUT" >> "$GITHUB_OUTPUT"
