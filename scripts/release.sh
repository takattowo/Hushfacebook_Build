#!/usr/bin/env bash
# Publish the patched APK as a GitHub release on this repo.
set -euo pipefail

FB_VERSION="$1"
HUSH_TAG="$2"
APK="$3"

TAG="$RELEASE_TAG"
EXPERT="${EXPERT:-false}"
FORCE="${FORCE:-false}"

if [ "$FORCE" = "true" ] && gh release view "$TAG" >/dev/null 2>&1; then
  echo "== Force: deleting existing release $TAG"
  gh release delete "$TAG" --yes --cleanup-tag
fi

if gh release view "$TAG" >/dev/null 2>&1; then
  echo "Release $TAG already exists, skipping."
  exit 0
fi

PATCH_NOTE="- Patches: Hushfacebook default selection (all patches except the three expert ones)"
if [ "$EXPERT" = "true" ]; then
  PATCH_NOTE="- Patches: all, expert trio included (AMOLED black theme, Material You theme, Disable Play Store updates)"
fi

NOTES=$(cat <<EOF
Prebuilt patched Facebook, built by GitHub Actions.

- **Facebook:** \`$FB_VERSION\`
- **Patch bundle:** [Hushfacebook $HUSH_TAG](https://github.com/SysAdminDoc/Hushfacebook/releases/tag/$HUSH_TAG)
- **Patcher:** [morphe-desktop](https://github.com/MorpheApp/morphe-desktop/releases)
$PATCH_NOTE

## Install

1. Download the APK below.
2. Uninstall your current Facebook if it is signed differently (this build uses this repo's own signing key, so it will not install over a Morphe Manager-patched copy or Meta's original unless you imported that key).
3. Install the APK and open it.

## Updates

New releases appear here automatically when Hushfacebook or the supported Facebook version changes. Android only allows updates signed with the same key.

Patch settings live inside the app: long-press the Facebook logo (Hushfacebook settings).
EOF
)

echo "== Creating release $TAG"
gh release create "$TAG" "$APK" \
  --title "Facebook $FB_VERSION + Hushfacebook $HUSH_TAG" \
  --notes "$NOTES"

echo "== Release created"
