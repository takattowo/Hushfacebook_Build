#!/usr/bin/env python3
"""Download the exact Facebook variant Hushfacebook documents from APKMirror.

Usage: fetch_apkmirror.py <version> <outdir>

Variant pinned to the build the Hushfacebook README names:
(arm64-v8a) (120-640dpi) (Android 11+) bundle -> .apkm

Uses apktap's APKMirror flow. On Cloudflare 403 apktap falls back to
curl / cloudscraper / curl_cffi and finally headless Chromium; the stock
browser fallback waits for "networkidle" which never happens on a CF
interstitial, so this script replaces the two browser helpers with versions
that wait for the challenge to clear instead, and copies the solved
cf_clearance cookie back to the urllib jar so subsequent requests skip the
whole fallback chain.
"""
import sys
import time

from apktap import api, html
from apktap import http as apktap_http
from apktap.http import BASE, _BROWSER_STEALTH_INIT, _Browser, _FakeResponse, _cj

apktap_http.HEADLESS = True

CF_MARKERS = ("Just a moment", "Enable JavaScript and cookies", "cf-browser-verification")

def _cookie_to_jar(c):
    import http.cookiejar
    _cj.set_cookie(http.cookiejar.Cookie(
        version=0, name=c["name"], value=c["value"],
        port=None, port_specified=False,
        domain=c["domain"], domain_specified=True,
        domain_initial_dot=c["domain"].startswith("."),
        path=c["path"], path_specified=True,
        secure=c.get("secure", False),
        expires=int(c["expires"]) if c.get("expires") and c["expires"] > 0 else None,
        discard=True, comment=None, comment_url=None, rest={}, rfc2109=False,
    ))

def _sync_cookies_to_urllib():
    try:
        for c in _Browser._context.cookies():
            _cookie_to_jar(c)
    except Exception as e:
        print(f"cookie sync failed (non-fatal): {e}", file=sys.stderr)

def _is_challenge(body_text):
    head = body_text[:4000]
    return any(m in head for m in CF_MARKERS)

def _try_click_challenge(page):
    """CF serves an interactive checkbox challenge to datacenter IPs -
    it never clears without a click."""
    frames = []
    for f in page.frames:
        u = f.url or ""
        if "challenges.cloudflare.com" in u or "cdn-cgi/challenge-platform" in u:
            frames.append(f)
    try:
        frames.append(page.main_frame)
    except Exception:
        pass
    for f in frames:
        for sel in ("input[type='checkbox']",
                    "#challenge-stage input[type='checkbox']",
                    "input"):
            try:
                f.locator(sel).first.click(timeout=1200)
                return True
            except Exception:
                continue
        try:  # turnstile checkbox sits near the left edge, mid-height
            f.locator("body").click(timeout=1200, position={"x": 32, "y": 33})
            return True
        except Exception:
            continue
    return False

def _browser_get(url, method="GET", timeout=60):
    try:
        _Browser.ensure()
    except Exception as e:
        print(f"browser launch failed: {e}", file=sys.stderr)
        return None
    page = _Browser._context.new_page()
    page.add_init_script(_BROWSER_STEALTH_INIT)
    try:
        page.goto(url, timeout=45 * 1000, wait_until="domcontentloaded")
        deadline = time.time() + 90
        body = ""
        last_click = 0.0
        while time.time() < deadline:
            try:
                body = page.content()
            except Exception:
                time.sleep(1)
                continue
            if not _is_challenge(body):
                break
            if time.time() - last_click > 5:
                _try_click_challenge(page)
                last_click = time.time()
            time.sleep(2)
        try:
            page.wait_for_load_state("networkidle", timeout=15000)
            body = page.content()
        except Exception:
            pass
        if _is_challenge(body):
            print("browser fetch: challenge never cleared", file=sys.stderr)
            return None
        _sync_cookies_to_urllib()
        print(f"browser fetch ok: {page.url}", file=sys.stderr)
        return _FakeResponse(body.encode("utf-8"),
                             {"Content-Type": "text/html; charset=utf-8"},
                             page.url)
    except Exception as e:
        print(f"browser fetch failed: {e}", file=sys.stderr)
        return None
    finally:
        try:
            page.close()
        except Exception:
            pass

def _browser_resolve_redirect(url, timeout=60):
    # urllib first: we already hold the cf_clearance cookie, and the browser
    # cannot follow download.php (it ends in an attachment, not a navigation).
    try:
        resp = apktap_http._open(url, timeout=timeout)
        resp.read()
        final = resp.geturl()
        if final:
            return final
    except Exception as e:
        print(f"urllib redirect failed ({e}), trying browser", file=sys.stderr)
    try:
        _Browser.ensure()
    except Exception as e:
        print(f"browser launch failed: {e}", file=sys.stderr)
        return None
    page = _Browser._context.new_page()
    page.add_init_script(_BROWSER_STEALTH_INIT)
    try:
        page.goto(url, timeout=timeout * 1000, wait_until="domcontentloaded")
        deadline = time.time() + 90
        last_click = 0.0
        while time.time() < deadline:
            try:
                cur = page.url
                body = page.content()
            except Exception:
                time.sleep(1)
                continue
            if not _is_challenge(body):
                # settle redirects after the challenge clears
                try:
                    page.wait_for_load_state("networkidle", timeout=15000)
                except Exception:
                    pass
                _sync_cookies_to_urllib()
                return page.url
            if time.time() - last_click > 5:
                _try_click_challenge(page)
                last_click = time.time()
            time.sleep(2)
        return None
    except Exception as e:
        print(f"browser redirect failed: {e}", file=sys.stderr)
        return None
    finally:
        try:
            page.close()
        except Exception:
            pass

apktap_http._browser_get = _browser_get
apktap_http._browser_resolve_redirect = _browser_resolve_redirect


# apktap launches playwright's chromium-headless-shell, which Cloudflare
# identifies and serves an endless challenge to. Replace ensure() with one
# that runs the FULL Chromium - headed when a display exists (xvfb-run in
# CI), new headless otherwise.
def _ensure(cls):
    if cls._browser is not None:
        return
    import os
    from playwright.sync_api import sync_playwright
    cls._pw = sync_playwright().start()
    cls._browser = cls._pw.chromium.launch(
        headless=not os.environ.get("DISPLAY"),
        args=[
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-dev-shm-usage",
            "--disable-gpu",
            "--disable-blink-features=AutomationControlled",
        ],
    )
    cls._context = cls._browser.new_context(
        user_agent=apktap_http.HEADERS["User-Agent"],
        locale="en-US",
        viewport={"width": 1920, "height": 1080},
    )


_Browser.ensure = classmethod(_ensure)

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

    ext = "apkm" if selected["type"] == "bundle" else "apk"
    out = f"{outdir}/facebook.{ext}"

    # dl.* URLs are single-use and the connection sometimes dies mid-body;
    # regenerate a fresh URL per attempt and verify the completed size.
    import hashlib
    import os
    import urllib.request
    from apktap import http as H

    digest = None
    for attempt in range(1, 6):
        dl = api.get_download_url(html.urljoin(BASE, selected["url"]))
        if not dl:
            log(f"attempt {attempt}: could not resolve download url, retrying")
            time.sleep(5)
            continue
        try:
            req = urllib.request.Request(dl)
            for k, v in H.HEADERS.items():
                if k.lower() == "accept-encoding":
                    continue  # we want the raw binary, not gzip
                req.add_header(k, v)
            with H._opener.open(req, timeout=300) as r:
                total = r.headers.get("Content-Length")
                tmp = out + ".part"
                read = 0
                with open(tmp, "wb") as fh:
                    while True:
                        chunk = r.read(1 << 20)
                        if not chunk:
                            break
                        fh.write(chunk)
                        read += len(chunk)
                if total and read != int(total):
                    raise IOError(f"truncated: got {read} of {total} bytes")
                os.replace(tmp, out)
            with open(out, "rb") as fh:
                digest = hashlib.sha256(fh.read()).hexdigest()
            log(f"downloaded {read} bytes (Content-Length {total})")
            break
        except Exception as e:
            log(f"attempt {attempt} failed: {e}")
            time.sleep(10)
    if digest is None:
        sys.exit(f"::error::Could not download the APKMirror file for {version} after 5 attempts")
    log(f"\nsaved {out} sha256={digest}")

if __name__ == "__main__":
    main()
