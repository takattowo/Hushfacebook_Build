#!/usr/bin/env bash
# Probe upstream: latest Hushfacebook patch bundle, latest morphe-desktop,
# and the Facebook version the bundle supports. Decide if a build is needed.
set -euo pipefail

HUSH_REPO="SysAdminDoc/Hushfacebook"
MORPHE_REPO="MorpheApp/morphe-desktop"
PACKAGE="com.facebook.katana"

echo "== Latest upstream releases"
HUSH_TAG=$(gh api "repos/$HUSH_REPO/releases/latest" --jq '.tag_name')
MORPHE_TAG=$(gh api "repos/$MORPHE_REPO/releases/latest" --jq '.tag_name')
echo "Hushfacebook:   $HUSH_TAG"
echo "morphe-desktop: $MORPHE_TAG"

echo "== Download patcher and patch bundle"
gh release download "$MORPHE_TAG" --repo "$MORPHE_REPO" --pattern '*-all.jar'
gh release download "$HUSH_TAG" --repo "$HUSH_REPO" --pattern 'patches-*.mpp'

JAR=$(ls morphe-desktop-*-all.jar)
MPP=$(ls patches-*.mpp)
echo "jar: $JAR"
echo "mpp: $MPP"

echo "== Supported Facebook versions (asked of the bundle itself)"
java -jar "$JAR" list-versions \
  --patches "$MPP" \
  --filter-package-names "$PACKAGE" | tee list-versions.txt

# The first version line also carries each ABI's version code. Fetching the
# arm64 build by code avoids scraping APKPure's version page (403 from CI)
# and guarantees the architecture Hushfacebook documents.
SUPPORTED=$(grep -m1 -E 'ARM64_V8A=[0-9]+' list-versions.txt || true)
FB_VERSION=$(printf '%s\n' "$SUPPORTED" | grep -oE '[0-9]+(\.[0-9]+){3,}' | head -n1 || true)
FB_ARM64_CODE=$(printf '%s\n' "$SUPPORTED" | grep -oE 'ARM64_V8A=[0-9]+' | head -n1 | cut -d= -f2 || true)
if [ -z "$FB_VERSION" ] || [ -z "$FB_ARM64_CODE" ]; then
  echo "::error::Could not parse a Facebook version and arm64 version code from list-versions output. See list-versions.txt above."
  exit 1
fi
echo "Recommended Facebook: $FB_VERSION (arm64 versionCode $FB_ARM64_CODE)"

RELEASE_TAG="${HUSH_TAG}-fb${FB_VERSION}"
echo "Release tag: $RELEASE_TAG"

NEED=true
if gh release view "$RELEASE_TAG" >/dev/null 2>&1; then
  NEED=false
  echo "Release $RELEASE_TAG already exists - nothing to build."
fi
if [ "${FORCE:-false}" = "true" ]; then
  NEED=true
  echo "Force build requested."
fi

{
  echo "hush_tag=$HUSH_TAG"
  echo "fb_version=$FB_VERSION"
  echo "fb_arm64_code=$FB_ARM64_CODE"
  echo "release_tag=$RELEASE_TAG"
  echo "need_build=$NEED"
} >> "$GITHUB_OUTPUT"

echo "need_build=$NEED"
