#!/usr/bin/env python3
"""Download the exact Facebook build Hushfacebook documents, from APKPure.

Usage: fetch_apkpure.py <version> <arm64_version_code> <outdir>

APKPure's version page sits behind bot protection that rejects GitHub Actions,
but its download host accepts a version code directly. The Hushfacebook bundle
reports the arm64-v8a APK version code it patches, so download that code and
verify the result: same package and version, minSdk >= 30 (Android 11+), and an
arm64-v8a base APK. The Android 9/8 builds hide their code in a compressed
secondary-dex archive the patcher cannot read, so the wrong SDK breaks patching.
"""
import json
import os
import shutil
import sys
import tempfile
import urllib.request
import zipfile

PACKAGE = "com.facebook.katana"
DOWNLOAD_URL = "https://d.apkpure.com/b/XAPK/{package}?versionCode={code}"
UA = ("Mozilla/5.0 (X11; Linux x86_64; rv:135.0) Gecko/20100101 "
      "Firefox/135.0")


def log(*a):
    print(*a, flush=True)


def fail(message):
    sys.exit("::error::" + message)


def download(url, out):
    part = out + ".part"
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=600) as resp, \
                open(part, "wb") as fh:
            expected = resp.headers.get("Content-Length")
            written = 0
            while True:
                chunk = resp.read(1 << 20)
                if not chunk:
                    break
                fh.write(chunk)
                written += len(chunk)
            if expected and written != int(expected):
                fail(f"Truncated download: {written} of {expected} bytes")
        os.replace(part, out)
    except BaseException:
        if os.path.exists(part):
            os.remove(part)
        raise
    return written


def parse_int(value, label):
    try:
        return int(value)
    except (TypeError, ValueError):
        fail(f"XAPK manifest has an invalid {label}: {value!r}")


def verify(path, version, code):
    try:
        with zipfile.ZipFile(path) as xapk:
            bad = xapk.testzip()
            if bad:
                fail(f"Corrupt XAPK entry: {bad}")
            if "manifest.json" not in xapk.namelist():
                fail("XAPK has no manifest.json")
            manifest = json.loads(xapk.read("manifest.json"))

            if manifest.get("package_name") != PACKAGE:
                fail(f"Wrong package: {manifest.get('package_name')!r}")
            if manifest.get("version_name") != version:
                fail(f"Wrong version: {manifest.get('version_name')!r}, "
                     f"wanted {version!r}")
            if str(manifest.get("version_code")) != str(code):
                fail(f"Wrong version code: {manifest.get('version_code')!r}, "
                     f"wanted {code!r}")
            min_sdk = parse_int(manifest.get("min_sdk_version"), "min_sdk_version")
            if min_sdk < 30:
                fail(f"Android {min_sdk} build, need Android 11+ (API 30)")

            base = next((s.get("file") for s in manifest.get("split_apks", [])
                         if s.get("id") == "base"), None)
            if not base:
                fail("XAPK manifest has no base APK")

            with tempfile.TemporaryDirectory() as tmp:
                base_path = os.path.join(tmp, "base.apk")
                with xapk.open(base) as src, open(base_path, "wb") as dst:
                    shutil.copyfileobj(src, dst, 1 << 20)
                with zipfile.ZipFile(base_path) as apk:
                    abis = {name.split("/")[1] for name in apk.namelist()
                            if name.startswith("lib/") and name.count("/") >= 2}
    except zipfile.BadZipFile as e:
        fail(f"Downloaded file is not a valid XAPK: {e}")
    except (ValueError, KeyError) as e:
        fail(f"Could not read XAPK manifest: {e}")

    if "arm64-v8a" not in abis:
        fail(f"Base APK is not arm64-v8a (found: {sorted(abis) or 'none'})")
    log(f"verified {PACKAGE} {version} ({code}), minSdk {min_sdk}, "
        f"arm64-v8a")


def main():
    if len(sys.argv) != 4:
        sys.exit("usage: fetch_apkpure.py <version> <arm64_version_code> "
                 "<outdir>")
    version, code, outdir = sys.argv[1], sys.argv[2], sys.argv[3]
    if not code.isdigit():
        sys.exit(f"::error::arm64 version code is not numeric: {code!r}")

    os.makedirs(outdir, exist_ok=True)
    out = os.path.join(outdir, "facebook.xapk")
    url = DOWNLOAD_URL.format(package=PACKAGE, code=code)

    log(f"== Fetching Facebook {version} (arm64-v8a, versionCode {code})")
    log(f"fetching {url}")
    written = download(url, out)
    try:
        verify(out, version, code)
    except BaseException:
        os.remove(out)
        raise

    size = os.path.getsize(out)
    if size < 10 * 1024 * 1024:
        fail(f"Downloaded file too small ({size} bytes)")
    log(f"saved {out} ({written} bytes)")


if __name__ == "__main__":
    main()
