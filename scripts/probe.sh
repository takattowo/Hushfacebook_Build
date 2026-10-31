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

FB_VERSION=$(grep -oE '[0-9]+(\.[0-9]+){3,}' list-versions.txt | head -n1 || true)
if [ -z "$FB_VERSION" ]; then
  echo "::error::Could not parse a Facebook version from list-versions output. See list-versions.txt above."
  exit 1
fi
echo "Recommended Facebook: $FB_VERSION"

SUFFIX=""
if [ "${EXPERT:-false}" = "true" ]; then
  SUFFIX="-expert"
else
  if [ "${AMOLED:-false}" = "true" ]; then
    SUFFIX="${SUFFIX}-amoled"
  fi
  if [ "${MATERIAL_YOU:-false}" = "true" ]; then
    SUFFIX="${SUFFIX}-material-you"
  fi
fi
RELEASE_TAG="${HUSH_TAG}-fb${FB_VERSION}${SUFFIX}"
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
  echo "release_tag=$RELEASE_TAG"
  echo "need_build=$NEED"
} >> "$GITHUB_OUTPUT"

echo "need_build=$NEED"
