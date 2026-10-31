#!/usr/bin/env bash
# Patch the Facebook APK with the Hushfacebook bundle using morphe-desktop CLI.
# No --force: if the APK version does not match the bundle, the patcher aborts.
set -euo pipefail

FB_VERSION="$1"
HUSH_TAG="$2"
APK="$3"
EXPERT="${EXPERT:-false}"
AMOLED="${AMOLED:-false}"
MATERIAL_YOU="${MATERIAL_YOU:-false}"

: "${KEYSTORE_BASE64:?Missing KEYSTORE_BASE64 Actions secret}"
: "${KEYSTORE_PASSWORD:?Missing KEYSTORE_PASSWORD Actions secret}"
KEYSTORE_FILE=$(mktemp "${RUNNER_TEMP:-${TMPDIR:-/tmp}}/hushfacebook-keystore.XXXXXX")
trap 'rm -f "$KEYSTORE_FILE"' EXIT
printf '%s' "$KEYSTORE_BASE64" | base64 --decode > "$KEYSTORE_FILE"

JAR=$(ls morphe-desktop-*-all.jar)
MPP=$(ls patches-*.mpp)

SUFFIX=""
if [ "$EXPERT" = "true" ]; then
  SUFFIX="-expert"
else
  if [ "$AMOLED" = "true" ]; then
    SUFFIX="${SUFFIX}-amoled"
  fi
  if [ "$MATERIAL_YOU" = "true" ]; then
    SUFFIX="${SUFFIX}-material-you"
  fi
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

if [ "$EXPERT" = "true" ] || [ "$AMOLED" = "true" ]; then
  ARGS+=(-e "AMOLED black theme")
fi
if [ "$EXPERT" = "true" ] || [ "$MATERIAL_YOU" = "true" ]; then
  ARGS+=(-e "Material You theme")
fi
if [ "$EXPERT" = "true" ]; then
  ARGS+=(-e "Disable Play Store updates")
fi

echo "== Patching $APK -> $OUT (expert=$EXPERT, amoled=$AMOLED, material_you=$MATERIAL_YOU)"
java -jar "$JAR" "${ARGS[@]}" "$APK"

if [ ! -f "$OUT" ]; then
  echo "::error::Patch reported success but $OUT is missing"
  exit 1
fi

ls -la "$OUT"
echo "out=$OUT" >> "$GITHUB_OUTPUT"
