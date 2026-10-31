# Hushfacebook Build

Automated builder for **prebuilt patched Facebook APKs** using [Hushfacebook](https://github.com/SysAdminDoc/Hushfacebook) patches and [morphe-desktop](https://github.com/MorpheApp/morphe-desktop). Everything runs in GitHub Actions - nothing is built locally.

> [!WARNING]
> This repo is **private on purpose**. It contains the signing keystore. Do not make it public - anyone with the keystore can sign APKs your phone accepts as updates to your patched Facebook.

## How it works

A scheduled GitHub Action runs daily (plus a manual button):

1. Reads the latest [Hushfacebook release](https://github.com/SysAdminDoc/Hushfacebook/releases) and downloads its `.mpp` patch bundle.
2. Asks morphe-desktop `list-versions` which Facebook version the bundle supports.
3. Downloads exactly that Facebook build from [Uptodown](https://uptodown.com) (version history -> "Android + 11" arm64-v8a xapk; the download button is Turnstile-gated, so the fetch runs a real Chrome under xvfb to solve it).
4. Patches it with morphe-desktop (default Hushfacebook patch selection = every patch except the three expert ones), signs it with this repo's keystore.
5. Publishes a GitHub Release named `<hush-tag>-fb<facebook-version>` with the APK attached.

If a release for the current combination already exists, the run stops after step 2 - so most days cost almost nothing.

## Get an APK

Releases tab -> pick the newest release -> download the `.apk`.

Expert variant (adds `AMOLED black theme`, `Material You theme`, `Disable Play Store updates`): Actions -> *Build patched Facebook* -> *Run workflow* -> tick **expert**.

## Manual trigger

Actions -> *Build patched Facebook* -> *Run workflow*:

| Input | Effect |
|---|---|
| `force` | Rebuild and replace the release even if it already exists |
| `expert` | Also enable the three non-default patches (separate `-expert` release tag) |

## When a build fails

- **Patch failure** = new Facebook version broke a Hushfacebook fingerprint, or vice versa. Nothing is released; the last good release stays. GitHub emails you on workflow failure.
- **Fetch failure** = Uptodown did not have that Facebook version yet, or its Turnstile gate refused the CI IP. Retries itself the next day.

## Keystore

- `keystore.p12`, alias `hush`, password `HushBuild2026` (also in `scripts/patch.sh`).
- Android installs updates only over the same signature. **Back this file up somewhere private.** Lose it and every installed build can only be replaced by uninstalling (data loss) or a fresh key.
- If you fork: generate your own keystore, or users of your builds are chained to this one.

## Files

```
.github/workflows/build.yml   triggers + step wiring
scripts/probe.sh              upstream probe, version decision
scripts/fetch-apk.sh          installs browser tooling, runs the Uptodown fetch (with retries)
scripts/fetch_uptodown.py     picks the exact version/variant, solves Turnstile, downloads
scripts/patch.sh              morphe-desktop patch + sign
scripts/release.sh            publish GitHub release
keystore.p12                  signing key (KEEP PRIVATE)
```

## Credits

- [Hushfacebook](https://github.com/SysAdminDoc/Hushfacebook) - the patches (GPL-3.0)
- [Morphe](https://github.com/MorpheApp) - patcher and desktop CLI (GPL-3.0)
- This repo only automates building; it adds no patches of its own.
