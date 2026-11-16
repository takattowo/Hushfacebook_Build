#!/usr/bin/env python3
"""Download the exact Facebook build Hushfacebook documents, from APKPure.

Usage: fetch_apkpure.py <version> <outdir>

Hushfacebook needs the "(arm64-v8a) (Android 11+)" bundle. Older Android 9
and 8.0 builds hide their code in a compressed secondary-dex archive that the
patcher cannot read, so picking the wrong variant makes every patch fail.

APKPure lists each variant's architecture and minimum Android version. This
script picks the arm64-v8a / Android 11+ XAPK for <version>, downloads it,
and verifies the SHA-1 APKPure publishes for that variant.
"""
import hashlib
import os
import re
import sys
import time
import urllib.request

VERSION_PAGE = "https://apkpure.com/facebook-app/com.facebook.katana/download/"
DOWNLOAD_URL = ("https://d.apkpure.com/b/XAPK/com.facebook.katana"
                "?versionCode={}")

UA = ("Mozilla/5.0 (X11; Linux x86_64; rv:135.0) Gecko/20100101 "
      "Firefox/135.0")


def log(*a):
    print(*a, flush=True)


def fetch_page(version):
    url = VERSION_PAGE + version
    last_err = None
    for attempt in range(1, 4):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=60) as resp:
                return resp.read().decode("utf-8", "replace")
        except Exception as e:
            last_err = e
            log(f"::warning::APKPure page fetch attempt {attempt} failed: {e}")
            time.sleep(5 * attempt)
    sys.exit(f"::error::Could not load APKPure page for {version}: {last_err}")


def pick_variant(html, version):
    # Each variant is one <div class="apk" data-dt-app=...> block containing
    # its download link, architecture, minimum Android version, size, SHA-1.
    blocks = re.split(r'<div class="apk" data-dt-app=', html)[1:]
    found = []
    for block in blocks:
        code = re.search(
            r'https://d\.apkpure\.com/b/XAPK/com\.facebook\.katana'
            r'\?versionCode=(\d+)', block)
        name = re.search(r'<span class="name one-line">([^<]+)</span>', block)
        arch = re.search(
            r'<span class="label">Architecture</span>'
            r'<span class="value">([^<]+)</span>', block)
        android = re.search(
            r'<span class="label">Requires Android</span>'
            r'<span class="value">([^<]+)</span>', block)
        sha1 = re.search(
            r'<span class="label">File SHA1</span>'
            r'<span class="value">([^<]+)</span>', block)
        size = re.search(r'<span class="size">([^<]+)</span>', block)
        if not (code and name and arch and android and sha1):
            continue
        if name.group(1).strip() != version:
            continue
        api = re.search(r'API (\d+)', android.group(1))
        found.append({
            "versionCode": code.group(1),
            "arch": arch.group(1).strip(),
            "android": android.group(1).strip(),
            "api": int(api.group(1)) if api else 0,
            "sha1": sha1.group(1).strip().lower(),
            "size": size.group(1).strip() if size else "?",
        })

    if not found:
        log("::warning::No APKPure variants matched version " + version)

    for v in found:
        if v["arch"] == "arm64-v8a" and v["api"] >= 30:
            return v

    listing = ", ".join(f'{v["arch"]}/{v["android"]}' for v in found) or "none"
    sys.exit(f"::error::APKPure has no arm64-v8a Android 11+ bundle for "
             f"{version} (found: {listing})")


def sha1_file(path):
    digest = hashlib.sha1()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download(version, variant, out):
    url = DOWNLOAD_URL.format(variant["versionCode"])
    log(f"fetching {url}")
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    written = 0
    with urllib.request.urlopen(req, timeout=600) as resp, open(out, "wb") as fh:
        expected = resp.headers.get("Content-Length")
        while True:
            chunk = resp.read(1 << 20)
            if not chunk:
                break
            fh.write(chunk)
            written += len(chunk)
        if expected and written != int(expected):
            sys.exit(f"::error::Truncated download: {written} of {expected} bytes")

    actual = sha1_file(out)
    if actual != variant["sha1"]:
        sys.exit(f"::error::SHA-1 mismatch: expected {variant['sha1']}, "
                 f"got {actual}")
    log(f"downloaded {written} bytes, SHA-1 {actual}")


def main():
    if len(sys.argv) != 3:
        sys.exit("usage: fetch_apkpure.py <version> <outdir>")
    version, outdir = sys.argv[1], sys.argv[2]

    log(f"== Picking {version} (arm64-v8a, Android 11+) from APKPure")
    html = fetch_page(version)
    variant = pick_variant(html, version)
    log(f"selected versionCode {variant['versionCode']} "
        f"({variant['arch']}, {variant['android']}, {variant['size']})")

    os.makedirs(outdir, exist_ok=True)
    out = os.path.join(outdir, "facebook.xapk")
    download(version, variant, out)

    size = os.path.getsize(out)
    if size < 10 * 1024 * 1024:
        sys.exit(f"::error::Downloaded file too small ({size} bytes)")
    log(f"saved {out} ({size} bytes)")


if __name__ == "__main__":
    main()
