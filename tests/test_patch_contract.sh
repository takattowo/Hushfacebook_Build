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
printf '%s\n' "${args[@]}" > "$JAVA_ARGS_CAPTURE"
[[ -f "$keystore" ]]
cmp -s "$keystore" "$EXPECTED_KEYSTORE"
[[ "$password" == "$EXPECTED_PASSWORD" ]]
[[ "$entry_password" == "$EXPECTED_PASSWORD" ]]
[[ "$alias" == hush ]]
printf '%s' "$keystore" > "$KEYSTORE_PATH_CAPTURE"
: > "$out"
EOF
chmod +x "$TMP/bin/java"

run_case() {
  local name="$1" expert="$2" amoled="$3" material_you="$4" expected="$5"
  (
    cd "$TMP/work"
    PATH="$TMP/bin:$PATH" \
      KEYSTORE_BASE64="$(printf 'test-keystore' | base64 | tr -d '\n')" \
      KEYSTORE_PASSWORD='test-password' \
      EXPECTED_PASSWORD='test-password' \
      EXPECTED_KEYSTORE="$TMP/expected-keystore" \
      KEYSTORE_PATH_CAPTURE="$TMP/$name-keystore-path" \
      JAVA_ARGS_CAPTURE="$TMP/$name-java-args" \
      GITHUB_OUTPUT="$TMP/$name-output" \
      RUNNER_TEMP="$TMP" \
      EXPERT="$expert" \
      AMOLED="$amoled" \
      MATERIAL_YOU="$material_you" \
      bash ./patch.sh 584.0.0.51.56 v0.19.0 "$TMP/facebook.xapk"
  )
  grep -Fx "out=$expected" "$TMP/$name-output"
  [[ -f "$TMP/work/$expected" ]]
  [[ ! -e "$(cat "$TMP/$name-keystore-path")" ]]
}

run_case default false false false Hushfacebook-584.0.0.51.56-v0.19.0.apk
! grep -Fxq 'AMOLED black theme' "$TMP/default-java-args"
! grep -Fxq 'Material You theme' "$TMP/default-java-args"
! grep -Fxq 'Disable Play Store updates' "$TMP/default-java-args"

run_case amoled false true false Hushfacebook-584.0.0.51.56-v0.19.0-amoled.apk
grep -Fxq 'AMOLED black theme' "$TMP/amoled-java-args"
! grep -Fxq 'Material You theme' "$TMP/amoled-java-args"
! grep -Fxq 'Disable Play Store updates' "$TMP/amoled-java-args"

run_case material-you false false true Hushfacebook-584.0.0.51.56-v0.19.0-material-you.apk
! grep -Fxq 'AMOLED black theme' "$TMP/material-you-java-args"
grep -Fxq 'Material You theme' "$TMP/material-you-java-args"
! grep -Fxq 'Disable Play Store updates' "$TMP/material-you-java-args"

run_case expert true false false Hushfacebook-584.0.0.51.56-v0.19.0-expert.apk
grep -Fxq 'AMOLED black theme' "$TMP/expert-java-args"
grep -Fxq 'Material You theme' "$TMP/expert-java-args"
grep -Fxq 'Disable Play Store updates' "$TMP/expert-java-args"
