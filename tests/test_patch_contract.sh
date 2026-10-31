#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

mkdir -p "$TMP/bin" "$TMP/work"
cp "$ROOT/scripts/patch.sh" "$TMP/work/patch.sh"
touch "$TMP/work/morphe-desktop-test-all.jar" "$TMP/work/patches-test.mpp"
printf 'test-keystore' > "$TMP/expected-keystore"

cat > "$TMP/bin/java" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
args=("$@")
keystore=""
password=""
entry_password=""
alias=""
out=""
for ((i = 0; i < ${#args[@]}; i++)); do
  case "${args[$i]}" in
    --keystore) keystore="${args[$((i + 1))]}" ;;
    --keystore-password) password="${args[$((i + 1))]}" ;;
    --keystore-entry-password) entry_password="${args[$((i + 1))]}" ;;
    --keystore-entry-alias) alias="${args[$((i + 1))]}" ;;
    -o) out="${args[$((i + 1))]}" ;;
  esac
done
[[ -f "$keystore" ]]
cmp -s "$keystore" "$EXPECTED_KEYSTORE"
[[ "$password" == "$EXPECTED_PASSWORD" ]]
[[ "$entry_password" == "$EXPECTED_PASSWORD" ]]
[[ "$alias" == hush ]]
printf '%s' "$keystore" > "$KEYSTORE_PATH_CAPTURE"
: > "$out"
EOF
chmod +x "$TMP/bin/java"

(
  cd "$TMP/work"
  PATH="$TMP/bin:$PATH" \
    KEYSTORE_BASE64="$(printf 'test-keystore' | base64 | tr -d '\n')" \
    KEYSTORE_PASSWORD='test-password' \
    EXPECTED_PASSWORD='test-password' \
    EXPECTED_KEYSTORE="$TMP/expected-keystore" \
    KEYSTORE_PATH_CAPTURE="$TMP/keystore-path" \
    GITHUB_OUTPUT="$TMP/github-output" \
    RUNNER_TEMP="$TMP" \
    bash ./patch.sh 584.0.0.51.56 v0.19.0 "$TMP/facebook.xapk"
)

expected="Hushfacebook-584.0.0.51.56-v0.19.0.apk"
grep -Fx "out=$expected" "$TMP/github-output"
[[ -f "$TMP/work/$expected" ]]
[[ ! -e "$(cat "$TMP/keystore-path")" ]]
