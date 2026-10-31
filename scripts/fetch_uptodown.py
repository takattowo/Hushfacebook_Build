#!/usr/bin/env python3
"""Download the exact Facebook build Hushfacebook documents, from Uptodown.

Usage: fetch_uptodown.py <version> <outdir>

Uptodown pages carry no Cloudflare interstitial; only the final Download
button is Turnstile-gated. This script:
  1. reads /android/versions and picks the row matching <version> with
     "Android + 11" (that row's file id resolves to the arm64-v8a variant),
  2. opens its variant page in Chromium (headed under xvfb in CI),
  3. clicks Download, clicks the Turnstile checkbox if CF shows one,
  4. saves the file the browser downloads (or fetches the download-url
     API response directly as a fallback).
"""
import os
import re
import sys
import time

UT_BASE = "https://facebook.en.uptodown.com/android"
UA = ("Mozilla/5.0 (X11; Linux x86_64; rv:135.0) Gecko/20100101 "
      "Firefox/135.0")


def log(*a):
    print(*a, flush=True)


def pick_file_id(version):
    import urllib.request
    req = urllib.request.Request(UT_BASE + "/versions", headers={"User-Agent": UA})
    html = urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "replace")
    rows = re.findall(
        r'data-version-id="(\d+)"[^>]*>\s*'
        r'<span class="type[^"]*"[^>]*>[^<]*</span>\s*'
        r'<span class="version">([^<]+)</span>\s*'
        r'<span class="sdkVersion">([^<]+)</span>',
        html)
    if not rows:
        return None, None
    for fid, ver, sdk in rows:
        log(f"  row: {ver} {sdk} (file {fid})")
    for fid, ver, sdk in rows:
        if ver == version and "+ 11" in sdk:
            return fid, sdk
    for fid, ver, sdk in rows:
        if ver == version:
            log(f"::warning::no Android + 11 row for {version}, taking {sdk}")
            return fid, sdk
    return None, None


def _try_click_turnstile(page):
    frames = [f for f in page.frames
              if "challenges.cloudflare.com" in (f.url or "")
              or "cdn-cgi/challenge-platform" in (f.url or "")]
    for f in frames:
        for sel in ("input[type='checkbox']", "input"):
            try:
                f.locator(sel).first.click(timeout=1200)
                return True
            except Exception:
                continue
        try:
            f.locator("body").click(timeout=1200, position={"x": 32, "y": 33})
            return True
        except Exception:
            continue
    return False


def download(file_id, version, out):
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=not os.environ.get("DISPLAY"),
            args=["--no-sandbox", "--disable-setuid-sandbox",
                  "--disable-dev-shm-usage", "--disable-gpu",
                  "--disable-blink-features=AutomationControlled"],
        )
        ctx = browser.new_context(user_agent=UA, locale="en-US",
                                  viewport={"width": 1920, "height": 1080})
        page = ctx.new_page()
        holder = {}
        api_urls = []

        page.on("download", lambda d: holder.setdefault("dl", d))

        def on_response(resp):
            if "turnstile" in resp.url or "download-url" in resp.url:
                log(f"resp {resp.status} {resp.url[:160]}")
            if resp.url.endswith("/download-url"):
                try:
                    data = resp.json()["data"]["downloadURL"]
                    api_urls.append(data)
                except Exception as e:
                    log(f"download-url parse failed: {e}")
        page.on("response", on_response)

        def on_failed(req):
            if "turnstile" in req.url or "cloudflare" in req.url:
                log(f"requestfailed: {req.url[:160]} ({req.failure})")
        page.on("requestfailed", on_failed)

        url = f"{UT_BASE}/download/{file_id}-x"
        log(f"variant page: {url}")
        page.goto(url, wait_until="domcontentloaded", timeout=60000)

        body = page.content()
        if version not in body:
            raise RuntimeError(f"version {version} not shown on variant page")
        if "arm64-v8a" not in body:
            raise RuntimeError("variant page is not arm64-v8a")

        try:
            # force: ad/consent overlays occasionally cover the button
            page.eval_on_selector("#detail-download-button", "el => el.click()")
        except Exception:
            page.click("#detail-download-button", force=True)
        log("clicked Download; waiting for Turnstile / file...")
        log("turnstile api: " + page.evaluate(
            "typeof window.turnstile === 'undefined' ? 'MISSING' : 'loaded'"))

        deadline = time.time() + 180
        last_click = 0.0
        while time.time() < deadline and "dl" not in holder:
            if time.time() - last_click > 5:
                if _try_click_turnstile(page):
                    log("turnstile clicked")
                last_click = time.time()
            if api_urls:
                break
            time.sleep(1)

        if "dl" in holder:
            holder["dl"].save_as(out)
        elif api_urls:
            file_url = "https://dw.uptodown.com/dwn/" + api_urls[-1]
            log(f"api download-url: {file_url}")
            resp = ctx.request.get(file_url, timeout=300000)
            if resp.status != 200:
                raise RuntimeError(f"download-url fetch HTTP {resp.status}")
            with open(out, "wb") as fh:
                fh.write(resp.body())
        else:
            try:
                diag = page.evaluate("""() => ({
                    turnstile: typeof window.turnstile,
                    widget: (document.getElementById('download-turnstile-widget')||{}).outerHTML,
                    toasts: [...document.querySelectorAll('.toast, .notification, .text-box')]
                        .map(e => e.innerText.trim()).filter(Boolean).slice(0,5),
                    url: location.href,
                })""")
                log(f"diagnostics: {diag}")
            except Exception as e:
                log(f"diagnostics failed: {e}")
            raise RuntimeError("no download started within 180s")
        browser.close()


def main():
    if len(sys.argv) != 3:
        sys.exit("usage: fetch_uptodown.py <version> <outdir>")
    version, outdir = sys.argv[1], sys.argv[2]

    log(f"== Picking {version} (Android + 11) from Uptodown version history")
    file_id, sdk = pick_file_id(version)
    if not file_id:
        sys.exit(f"::error::Version {version} not found on Uptodown")
    log(f"selected file {file_id} ({sdk})")

    ext = "xapk"
    out = os.path.join(outdir, f"facebook.{ext}")
    download(file_id, version, out)

    size = os.path.getsize(out)
    if size < 10 * 1024 * 1024:
        sys.exit(f"::error::Downloaded file too small ({size} bytes)")
    log(f"saved {out} ({size} bytes)")


if __name__ == "__main__":
    main()
