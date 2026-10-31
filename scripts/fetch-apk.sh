#!/usr/bin/env bash
# Download the exact Facebook build Hushfacebook documents from APKMirror:
# (arm64-v8a) (120-640dpi) (Android 11+) bundle -> .apkm (morphe merges splits).
# Uses apkmd (tanishqmanuja/apkmirror-downloader).
set -euo pipefail

VERSION="$1"
mkdir -p apk

echo "== Download apkmd"
APKMD_TAG=$(gh api repos/tanishqmanuja/apkmirror-downloader/releases/latest --jq '.tag_name')
gh release download "$APKMD_TAG" --repo tanishqmanuja/apkmirror-downloader --pattern 'apkmd'
chmod +x apkmd
./apkmd --version || true

echo "== Fetch Facebook $VERSION from APKMirror (arm64-v8a, 120-640dpi, bundle)"
# NOTE: apkmd exits 0 even on failure - the file check below is the real gate.
# minAndroidVersion filter is NOT passed: the tool compares parseFloat of
# "Android 11+" which is NaN and would filter out every variant.
./apkmd download facebook-2 facebook \
  --version "$VERSION" \
  --arch arm64-v8a \
  --dpi 120-640dpi \
  --type bundle \
  --outfile facebook.apkm \
  --outdir apk

ls -la apk/ || true

FILE=$(find apk -maxdepth 1 -type f \( -name '*.apkm' -o -name '*.apk' -o -name '*.xapk' -o -name '*.apks' \) | head -n1 || true)
if [ -z "$FILE" ]; then
  echo "::error::apkmd produced no bundle for $VERSION (Cloudflare block, wrong variant filter, or version missing on APKMirror)"
  exit 1
fi

echo "Downloaded: $FILE"
echo "apk=$FILE" >> "$GITHUB_OUTPUT"
