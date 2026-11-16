#!/usr/bin/env python3
"""Download the exact Facebook build Hushfacebook documents, from Uptodown.

Usage: fetch_uptodown.py <version> <outdir>

Uptodown's website gates downloads behind Cloudflare Turnstile, which fails
reliably from CI IPs. Its mobile API does not: this script authenticates like
the Uptodown Android client (HMAC-signed anonymous session) and asks the API
for the file's CDN URL.

  1. reads /android/versions and picks <version>'s "Android + 11" row
     (that file id resolves to the arm64-v8a variant page),
  2. authenticates against www.uptodown.app/eapi,
  3. resolves /apps/<app>/file/<file>/downloadUrl,
  4. downloads the returned dw.uptodown.com link and verifies its SHA-256.
"""
import hashlib
import hmac
import json
import os
import re
import secrets
import sys
import time
import urllib.parse
import urllib.request

UT_BASE = "https://facebook.en.uptodown.com/android"
APP_ID = "16791"  # com.facebook.katana
API_BASE = "https://www.uptodown.app/eapi"

# plain page fetches (urllib) from CI IPs only ever worked with this Firefox
# UA - a desktop Chrome UA gets HTTP 404 on /versions
UA_FETCH = ("Mozilla/5.0 (X11; Linux x86_64; rv:135.0) Gecko/20100101 "
            "Firefox/135.0")

# Reverse-engineered from the Uptodown Android client: the API requires the
# client's Dalvik UA and identifier, and an HMAC-signed anonymous session.
API_UA = "Dalvik/2.1.0 (Linux; U; Android 16; Pixel 8 Pro Build/BP4A.260205.001)"
API_CLIENT = "739"
API_HMAC_KEY = b"MDGMXUMdvHJBG/vjdFgmqX6LUdy7ecfwvYNd0gyfOCs="


def log(*a):
    print(*a, flush=True)


def pick_file_id(version):
    html = None
    last_err = None
    for attempt in range(1, 4):
        try:
            req = urllib.request.Request(UT_BASE + "/versions",
                                         headers={"User-Agent": UA_FETCH,
                                                  "Referer": "https://en.uptodown.com/"})
            resp = urllib.request.urlopen(req, timeout=30)
            html = resp.read().decode("utf-8", "replace")
            break
        except Exception as e:
            last_err = e
            log(f"::warning::/versions fetch attempt {attempt} failed: {e}")
            time.sleep(5 * attempt)
    if html is None:
        sys.exit(f"::error::Could not load Uptodown version history: {last_err}")
    rows = re.findall(
        r'data-version-id="(\d+)"[^>]*>\s*'
        r'<span class="type[^"]*"[^>]*>[^<]*</span>\s*'
        r'<span class="version">([^<]+)</span>\s*'
        r'<span class="sdkVersion">([^<]+)</span>',
        html)
    if not rows:
        return None, None
    for fid, ver, sdk in rows:
        if ver == version and "+ 11" in sdk:
            return fid, sdk
    for fid, ver, sdk in rows:
        if ver == version:
            log(f"::warning::no Android + 11 row for {version}, taking {sdk}")
            return fid, sdk
    return None, None


def api_headers(token=None, form=False):
    headers = {
        "User-Agent": API_UA,
        "Identificador": "Uptodown_Android",
        "Identificador-Version": API_CLIENT,
    }
    if token:
        headers["Authorization"] = "Bearer " + token
    if form:
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    return headers


def api_auth():
    identifier = secrets.token_hex(8)
    unixtime = str(int(time.time()))
    signature = hmac.new(API_HMAC_KEY, unixtime.encode(),
                         hashlib.sha256).hexdigest()
    body = urllib.parse.urlencode({
        "identifier": identifier,
        "id_plataforma": "13",
        "lang": "en",
        "unixtime": unixtime,
        "hmac": signature,
    }).encode()
    req = urllib.request.Request(
        f"{API_BASE}/auth/token?identifier={identifier}",
        data=body, headers=api_headers(form=True))
    with urllib.request.urlopen(req, timeout=30) as resp:
        token = json.load(resp).get("token")
    if not token:
        raise RuntimeError("Uptodown auth returned no token")
    return token


def fetch_download_url(token, file_id):
    req = urllib.request.Request(
        f"{API_BASE}/apps/{APP_ID}/file/{file_id}/downloadUrl",
        headers=api_headers(token))
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.load(resp)
    if data.get("success") != 1:
        raise RuntimeError(f"downloadUrl failed: {data}")
    return data["data"]["downloadURL"], data["data"].get("sha256")


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download(file_id, out):
    token = api_auth()
    url, expected_sha = fetch_download_url(token, file_id)
    log(f"fetching {url[:80]}...")
    req = urllib.request.Request(url, headers={"User-Agent": API_UA})
    with urllib.request.urlopen(req, timeout=300) as resp, open(out, "wb") as fh:
        while True:
            chunk = resp.read(1 << 20)
            if not chunk:
                break
            fh.write(chunk)
    actual_sha = sha256_file(out)
    if expected_sha and actual_sha != expected_sha:
        sys.exit(f"::error::SHA-256 mismatch: expected {expected_sha}, got {actual_sha}")


def main():
    if len(sys.argv) != 3:
        sys.exit("usage: fetch_uptodown.py <version> <outdir>")
    version, outdir = sys.argv[1], sys.argv[2]

    log(f"== Picking {version} (Android + 11) from Uptodown version history")
    file_id, sdk = pick_file_id(version)
    if not file_id:
        sys.exit(f"::error::Version {version} not found on Uptodown")
    log(f"selected file {file_id} ({sdk})")

    os.makedirs(outdir, exist_ok=True)
    out = os.path.join(outdir, "facebook.xapk")
    download(file_id, out)

    size = os.path.getsize(out)
    if size < 10 * 1024 * 1024:
        sys.exit(f"::error::Downloaded file too small ({size} bytes)")
    log(f"saved {out} ({size} bytes)")


if __name__ == "__main__":
    main()
