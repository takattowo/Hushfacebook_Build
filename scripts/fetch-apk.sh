#!/usr/bin/env bash
# Download the exact Facebook build Hushfacebook documents from APKMirror:
# (arm64-v8a) (120-640dpi) (Android 11+) bundle -> .apkm (morphe merges splits).
set -euo pipefail

VERSION="$1"
mkdir -p apk

echo "== Install apktap + curl_cffi (Cloudflare bypass)"
pip install --quiet apktap curl_cffi

echo "== Fetch Facebook $VERSION from APKMirror"
python scripts/fetch_apkmirror.py "$VERSION" apk

ls -la apk/ || true

FILE=$(find apk -maxdepth 1 -type f \( -name '*.apkm' -o -name '*.apk' -o -name '*.xapk' -o -name '*.apks' \) | head -n1 || true)
if [ -z "$FILE" ]; then
  echo "::error::No bundle downloaded for $VERSION"
  exit 1
fi

echo "Downloaded: $FILE"
echo "apk=$FILE" >> "$GITHUB_OUTPUT"
