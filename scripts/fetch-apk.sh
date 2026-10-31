#!/usr/bin/env bash
# Download the exact Facebook version the patch bundle supports, from APKPure.
set -euo pipefail

VERSION="$1"
PACKAGE="com.facebook.katana"

echo "== Download apkeep"
APKEEP_TAG=$(gh api repos/EFForg/apkeep/releases/latest --jq '.tag_name')
gh release download "$APKEEP_TAG" --repo EFForg/apkeep --pattern 'apkeep-x86_64-unknown-linux-gnu'
chmod +x apkeep-x86_64-unknown-linux-gnu
APKEEP=./apkeep-x86_64-unknown-linux-gnu

mkdir -p apk

echo "== Versions APKPure has (debug info)"
"$APKEEP" -l -a "$PACKAGE" -d apk-pure | tee apkeep-versions.txt || echo "::warning::version listing failed, continuing"

echo "== Download $PACKAGE version $VERSION"
# acknowledge_dangers: APKPure is a third-party mirror (see USAGE-apkpure.md)
"$APKEEP" -a "$PACKAGE@$VERSION" -d apk-pure -o 'acknowledge_dangers=true' apk/
ls -la apk/

APK=$(find apk -maxdepth 1 -type f \( -name '*.apk' -o -name '*.xapk' -o -name '*.apkm' -o -name '*.apks' \) | head -n1 || true)
if [ -z "$APK" ]; then
  echo "::error::apkeep produced no APK/XAPK for $VERSION. Check apkeep-versions.txt above."
  exit 1
fi

echo "Downloaded: $APK"
echo "apk=$APK" >> "$GITHUB_OUTPUT"
