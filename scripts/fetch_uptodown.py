#!/usr/bin/env python3
"""Download the exact Facebook build Hushfacebook documents, from Uptodown.

Usage: fetch_uptodown.py <version> <outdir>

Uptodown pages have no Cloudflare interstitial; the only gate is a
Turnstile token on the download-url API. This script does not trust the
page's own button flow (it stalls on CI IPs) - it:
  1. reads /android/versions and picks <version>'s "Android + 11" row
     (that file id resolves to the arm64-v8a variant page),
  2. renders + executes Turnstile itself in Chromium,
  3. POSTs the token to /ajax/app/<app>/file/<file>/download-url,
  4. downloads the returned dw.uptodown.com link and verifies size.
"""
import json
import os
import re
import sys
import time
import urllib.request

UT_BASE = "https://facebook.en.uptodown.com/android"
UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/156.0.0.0 Safari/537.36")

STEALTH = r"""
Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
if (!window.chrome) {
  window.chrome = {runtime: {}, loadTimes: () => ({}), csi: () => ({})};
}
Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
const _pq = window.navigator.permissions.query.bind(window.navigator.permissions);
window.navigator.permissions.query = (params) =>
  params.name === 'notifications'
    ? Promise.resolve({state: Notification.permission})
    : _pq(params);
// report a GPU-less Linux desktop GL stack instead of SwiftShader
const _gp = WebGLRenderingContext.prototype.getParameter;
WebGLRenderingContext.prototype.getParameter = function (p) {
  if (p === 37445) return 'Google Inc. (X.org)';
  if (p === 37446) return 'ANGLE (X.org, Mesa, llvmpipe (LLVM 15.0.7, 256 bits), OpenGL 4.5 (Core Profile) Mesa 23.2.1)';
  return _gp.call(this, p);
};
"""


def log(*a):
    print(*a, flush=True)


def pick_file_id(version):
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


def solve_turnstile(page, timeout=120):
    """Render + execute the widget ourselves, return a token or None.

    Turnstile error 600010 ("bot behavior detected") is retryable - reset
    the widget and execute again, up to 6 rounds.
    """
    JS = """() => {
        const el = document.getElementById('download-turnstile-widget');
        if (!el) return 'no-widget-element';
        if (typeof window.turnstile === 'undefined') return 'no-turnstile-api';
        window.__tok = null; window.__terr = null;
        try {
            window.__tid = window.turnstile.render(el, {
                sitekey: el.dataset.sitekey,
                action: 'download',
                callback: (t) => { window.__tok = t; },
                'error-callback': (e) => { window.__terr = String(e); return true; },
                'timeout-callback': () => { window.__terr = 'timeout'; },
            });
            window.turnstile.execute(window.__tid);
            return 'started';
        } catch (e) { return 'throw:' + e; }
    }"""
    setup = page.evaluate(JS)
    if setup == "no-widget-element":
        # widget div is only rendered after the button's flow starts
        page.eval_on_selector("#detail-download-button", "el => el.click()")
        time.sleep(2)
        setup = page.evaluate(JS)
    log(f"turnstile setup: {setup}")
    if setup != "started":
        return None

    round_deadline = time.time() + timeout
    last_click = 0.0
    while time.time() < round_deadline:
        tok = page.evaluate("window.__tok")
        if tok:
            log("turnstile token received")
            return tok
        err = page.evaluate("window.__terr")
        if err:
            log(f"::warning::turnstile error {err}; resetting widget")
            time.sleep(2)
            page.evaluate("""() => {
                window.__tok = null; window.__terr = null;
                window.turnstile.reset(window.__tid);
                window.turnstile.execute(window.__tid);
            }""")
            last_click = 0.0
            # do not burn the whole budget on one error storm
            round_deadline = min(round_deadline, time.time() + 45)
        if time.time() - last_click > 5:
            _try_click_turnstile(page)
            last_click = time.time()
        time.sleep(1)
    log("::warning::turnstile timed out")
    return None


def fetch_download_url(ctx, file_id, token):
    url = f"{UT_BASE}/ajax/app/16791/file/{file_id}/download-url"
    resp = ctx.request.post(
        url,
        headers={
            "Content-Type": "application/json",
            "Origin": "https://facebook.en.uptodown.com",
            "Referer": f"{UT_BASE}/download/{file_id}-x",
        },
        data=json.dumps({"token": token, "onlyXapk": "1"}),
        timeout=60000,
    )
    body = resp.text()
    log(f"download-url POST -> {resp.status}: {body[:200]}")
    if resp.status != 200:
        raise RuntimeError(f"download-url HTTP {resp.status}")
    data = json.loads(body)
    return data["data"]["downloadURL"]


def download(file_id, version, out):
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        launch_kwargs = dict(
            headless=not os.environ.get("DISPLAY"),
            args=["--no-sandbox", "--disable-setuid-sandbox",
                  "--disable-dev-shm-usage"],
        )
        try:
            # real Google Chrome: correct brand/UA hints, not CfT "Chromium"
            browser = p.chromium.launch(channel="chrome", **launch_kwargs)
            log("browser: real Google Chrome")
        except Exception as e:
            log(f"chrome channel unavailable ({e}); falling back to chromium")
            browser = p.chromium.launch(**launch_kwargs)
        ctx = browser.new_context(locale="en-US",
                                  viewport={"width": 1920, "height": 1080})
        page = ctx.new_page()
        page.add_init_script(STEALTH)
        page.on("console", lambda m: log(f"console[{m.type}]: {m.text[:200]}")
                if m.type in ("error", "warning") else None)
        page.on("pageerror", lambda e: log(f"pageerror: {str(e)[:300]}"))

        url = f"{UT_BASE}/download/{file_id}-x"
        log(f"variant page: {url}")
        page.goto(url, wait_until="domcontentloaded", timeout=60000)

        body = page.content()
        if version not in body:
            raise RuntimeError(f"version {version} not shown on variant page")
        if "arm64-v8a" not in body:
            raise RuntimeError("variant page is not arm64-v8a")

        # settle consent/cookie overlays so the widget iframe is clickable
        for sel in ("#truste-consent-button", "button:has-text('Accept')",
                    "#onetrust-accept-btn-handler"):
            try:
                page.locator(sel).first.click(timeout=2000)
                log(f"dismissed overlay: {sel}")
            except Exception:
                pass

        token = solve_turnstile(page)
        if not token:
            browser.close()
            raise RuntimeError("no turnstile token")

        hash_ = fetch_download_url(ctx, file_id, token)
        file_url = "https://dw.uptodown.com/dwn/" + hash_
        log(f"fetching {file_url}")
        resp = ctx.request.get(file_url, headers={"Referer": UT_BASE + "/"},
                               timeout=300000)
        if resp.status != 200:
            raise RuntimeError(f"file fetch HTTP {resp.status}")
        data = resp.body()
        with open(out, "wb") as fh:
            fh.write(data)
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

    out = os.path.join(outdir, "facebook.xapk")
    download(file_id, version, out)

    size = os.path.getsize(out)
    if size < 10 * 1024 * 1024:
        sys.exit(f"::error::Downloaded file too small ({size} bytes)")
    log(f"saved {out} ({size} bytes)")


if __name__ == "__main__":
    main()
