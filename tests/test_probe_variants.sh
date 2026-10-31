#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP/bin"

cat > "$TMP/bin/gh" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
case "$1" in
  api)
    case "$2" in
      repos/SysAdminDoc/Hushfacebook/releases/latest) echo v0.19.0 ;;
      repos/MorpheApp/morphe-desktop/releases/latest) echo v1.20.0 ;;
      *) exit 2 ;;
    esac
    ;;
  release)
    case "$2" in
      download)
        shift 2
        while (($#)); do
          if [[ "$1" == --pattern ]]; then
            pattern="$2"
            shift 2
          else
            shift
          fi
        done
        case "$pattern" in
          *-all.jar) touch morphe-desktop-test-all.jar ;;
          patches-*.mpp) touch patches-test.mpp ;;
          *) exit 2 ;;
        esac
        ;;
      view) exit 1 ;;
      *) exit 2 ;;
    esac
    ;;
  *) exit 2 ;;
esac
EOF
cat > "$TMP/bin/java" <<'EOF'
#!/usr/bin/env bash
echo 'Supported Facebook 584.0.0.51.56'
EOF
chmod +x "$TMP/bin/gh" "$TMP/bin/java"

run_case() {
  local name="$1" expert="$2" amoled="$3" material_you="$4" expected="$5"
  local work="$TMP/$name"
  mkdir -p "$work"
  if ! (
    cd "$work"
    PATH="$TMP/bin:$PATH" \
      GITHUB_OUTPUT="$work/output" \
      EXPERT="$expert" \
      AMOLED="$amoled" \
      MATERIAL_YOU="$material_you" \
      FORCE=false \
      bash "$ROOT/scripts/probe.sh"
  ) > "$work/log" 2>&1; then
    cat "$work/log"
    return 1
  fi
  grep -Fx "release_tag=$expected" "$work/output"
}

run_case default false false false v0.19.0-fb584.0.0.51.56
run_case amoled false true false v0.19.0-fb584.0.0.51.56-amoled
run_case material-you false false true v0.19.0-fb584.0.0.51.56-material-you
run_case expert true false false v0.19.0-fb584.0.0.51.56-expert
