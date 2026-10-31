#!/usr/bin/env bash
# Download the exact Facebook build Hushfacebook documents from APKMirror:
# (arm64-v8a) (120-640dpi) (Android 11+) bundle -> .apkm (morphe merges splits).
set -euo pipefail

VERSION="$1"
mkdir -p apk

echo "== Install apktap (GitHub - not on PyPI) + CF bypass chain"
pip install --quiet curl_cffi cloudscraper playwright
pip install --quiet "git+https://github.com/Llucs/ApkTap.git"
# Full Chromium (apktap would only grab chromium-headless-shell, which
# Cloudflare challenges forever); xvfb gives it a real display so it runs headed.
python -m playwright install --with-deps chromium
sudo apt-get install -y -qq xvfb >/dev/null 2>&1 || true

echo "== Fetch Facebook $VERSION from APKMirror"
# Cloudflare challenge clearance from datacenter IPs is flaky - retry with backoff.
ok=false
for attempt in 1 2 3 4 5 6; do
  echo "-- fetch attempt $attempt"
  if xvfb-run -a python scripts/fetch_apkmirror.py "$VERSION" apk; then
    ok=true
    break
  fi
  sleep_for=$(( attempt * 30 ))
  [ "$sleep_for" -gt 120 ] && sleep_for=120
  echo "attempt $attempt failed; sleeping ${sleep_for}s"
  sleep "$sleep_for"
done
if [ "$ok" != "true" ]; then
  echo "::error::APKMirror fetch failed after 6 attempts"
  exit 1
fi

ls -la apk/ || true

FILE=$(find apk -maxdepth 1 -type f \( -name '*.apkm' -o -name '*.apk' -o -name '*.xapk' -o -name '*.apks' \) | head -n1 || true)
if [ -z "$FILE" ]; then
  echo "::error::No bundle downloaded for $VERSION"
  exit 1
fi

echo "Downloaded: $FILE"
echo "apk=$FILE" >> "$GITHUB_OUTPUT"
