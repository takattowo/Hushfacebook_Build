#!/usr/bin/env bash
# Download the exact Facebook build Hushfacebook documents, from Uptodown:
# (arm64-v8a) (Android + 11) xapk -> morphe merges the splits.
set -euo pipefail

VERSION="$1"
mkdir -p apk

echo "== Install browser tooling"
pip install --quiet playwright
# real Google Chrome preferred (channel=chrome); chromium as fallback
python -m playwright install --with-deps chrome || \
  python -m playwright install --with-deps chromium
sudo apt-get install -y -qq xvfb >/dev/null 2>&1 || true

# Turnstile clearance from CI IPs is flaky - retry with backoff.
ok=false
for attempt in 1 2 3 4; do
  echo "-- fetch attempt $attempt"
  if xvfb-run -a python scripts/fetch_uptodown.py "$VERSION" apk; then
    ok=true
    break
  fi
  echo "attempt $attempt failed; sleeping $((attempt * 30))s"
  sleep $((attempt * 30))
done
if [ "$ok" != "true" ]; then
  echo "::error::Uptodown fetch failed after 4 attempts"
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
