#!/usr/bin/env python3
"""Download the exact Facebook variant Hushfacebook documents from APKMirror.

Usage: fetch_apkmirror.py <version> <outdir>

Variant pinned to the build the Hushfacebook README names:
(arm64-v8a) (120-640dpi) (Android 11+) bundle -> .apkm

Uses apktap's APKMirror flow (browser-UA requests; on Cloudflare 403 it falls
back to curl / cloudscraper / curl_cffi, then headless Chromium).
"""
import sys

from apktap import api, html
from apktap.http import BASE

PACKAGE = "com.facebook.katana"
ARCH = "arm64-v8a"
DPI = "120-640dpi"
ANDROID_11 = "Android 11+"
WANT_TYPE = "bundle"

def log(*a):
    print(*a, flush=True)

def main():
    if len(sys.argv) != 3:
        sys.exit("usage: fetch_apkmirror.py <version> <outdir>")
    version, outdir = sys.argv[1], sys.argv[2]

    log(f"== Looking up {PACKAGE} on APKMirror")
    found = api.search_by_package(PACKAGE)
    if not found:
        sys.exit("::error::APKMirror app_exists API returned nothing for " + PACKAGE)
    name, app_url = found
    app_url = html.urljoin(BASE, app_url)
    log(f"app: {name} {app_url}")

    vurl = None
    for vname, vhref in api.get_versions(app_url):
        log(f"  version: {vname}")
        if vname.strip().startswith(version):
            vurl = html.urljoin(BASE, vhref)
            break
    if not vurl:
        sys.exit(f"::error::Version {version} not found on APKMirror")
    log(f"version page: {vurl}")

    variants = api.get_variants(vurl)
    for v in variants:
        log(f"  variant: type={v['type']} arch={v['arch']} dpi={v['dpi']} android={v['android']}")

    if not variants:
        sys.exit("::error::No variants parsed from the version page (Cloudflare?)")

    def matches(v, check_android):
        if v["type"] != WANT_TYPE or v["arch"] != ARCH or v["dpi"] != DPI:
            return False
        if check_android and v["android"].strip() != ANDROID_11:
            return False
        return True

    selected = next((v for v in variants if matches(v, True)), None)
    if selected is None:
        selected = next((v for v in variants if matches(v, False)), None)
        if selected is not None:
            log(f"::warning::No Android 11+ row matched, taking {selected['android']}")
    if selected is None:
        sys.exit("::error::No (arm64-v8a, 120-640dpi, bundle) variant for this version")

    log(f"SELECTED: {selected}")
    dl = api.get_download_url(html.urljoin(BASE, selected["url"]))
    if not dl:
        sys.exit("::error::Could not resolve the APKMirror download URL (Cloudflare?)")
    log(f"download url: {dl}")

    ext = "apkm" if selected["type"] == "bundle" else "apk"
    out = f"{outdir}/facebook.{ext}"
    digest = api.download_file(dl, out)
    log(f"\nsaved {out} sha256={digest}")

if __name__ == "__main__":
    main()
