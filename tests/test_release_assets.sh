#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP/bin"

cat > "$TMP/bin/gh" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
if [[ "$1" == release && "$2" == view ]]; then
  exit 1
fi
if [[ "$1" == release && "$2" == create ]]; then
  printf '%s\n' "$@" > "$GH_ARGS_CAPTURE"
  exit 0
fi
exit 2
EOF
chmod +x "$TMP/bin/gh"

PATH="$TMP/bin:$PATH" \
  GH_ARGS_CAPTURE="$TMP/gh-args" \
  RELEASE_TAG=v0.19.0-fb584.0.0.51.56 \
  EXPERT=false \
  FORCE=false \
  bash "$ROOT/scripts/release.sh" 584.0.0.51.56 v0.19.0 \
    default.apk amoled.apk material-you.apk

grep -Fxq default.apk "$TMP/gh-args"
grep -Fxq amoled.apk "$TMP/gh-args"
grep -Fxq material-you.apk "$TMP/gh-args"
grep -Fq 'APK variants: Default (all three expert patches disabled), default + AMOLED black theme, and default + Material You theme' "$TMP/gh-args"
