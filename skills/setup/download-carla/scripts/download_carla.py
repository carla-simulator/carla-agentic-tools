#!/usr/bin/env python3
"""Download CARLA — an official release, a nightly, a source checkout, or a Docker image.

Commands:
    list                          published versions and what each one offers
    resolve [--version 0.9.16]    print the real download URL(s) + sizes, download nothing
    release [--version latest] [--with-maps] [--dest DIR] [--keep-archive]
                                  official package: download, verify, extract
    nightly [--dest DIR]          the rolling Dev build (no version tag)
    git [--ref ue4-dev] [--dest DIR]
                                  shallow source checkout (then build-carla-ue4)
    docker [--version 0.9.16]     docker pull carlasim/carla:<version>

Every command ends by printing a WHAT/WHERE block: the kind of CARLA obtained, its
path, and the exact environment variables the other skills read — so nothing
downstream has to guess what was installed.

Why URLs are resolved from the GitHub API rather than constructed: the filename
scheme is NOT stable across the CARLA line. 0.9.16 publishes
`Linux/CARLA_0.9.16.tar.gz`, while 0.10.0 publishes
`Linux/Carla-0.10.0-Linux-Shipping.tar.gz` — a constructed URL 404s on one of
them. The release body is the authority; the CDN pattern is only a fallback.

Add --dry-run to any downloading command to see exactly what would run.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import urllib.request
import zipfile
from pathlib import Path

API = "https://api.github.com/repos/carla-simulator/carla/releases"
CDN = "https://carla-releases.b-cdn.net"
NIGHTLY = f"{CDN}/Linux/Dev/CARLA_Latest.tar.gz"
PLATFORM = "Windows" if sys.platform.startswith("win") else "Linux"


def _get_json(url: str):
    req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json",
                                               "User-Agent": "carla-agentic-tools"})
    with urllib.request.urlopen(req, timeout=30) as fh:
        return json.load(fh)


def releases() -> list[dict]:
    return _get_json(f"{API}?per_page=20")


def _links(body: str) -> list[tuple[str, str]]:
    """[(label, url)] from a release body's markdown links."""
    return re.findall(r"\[([^\]]+)\]\((https?://[^)\s]+)\)", body or "")


def head(url: str) -> tuple[str, int]:
    """Follow redirects; return (final_url, size_bytes). size 0 when unknown.

    curl first: the tiny.carla.org shortener answers HEAD with a 308, which
    urllib's HEAD redirect handling does not follow (verified — it raises
    HTTPError 308). The fallback is a 1-byte ranged GET, which follows the
    redirect and reports the true length in Content-Range without pulling the
    multi-GB body.
    """
    if shutil.which("curl"):
        r = subprocess.run(["curl", "-sIL", "--max-time", "30", url],
                           capture_output=True, text=True)
        final, size = url, 0
        for line in r.stdout.splitlines():
            low = line.lower()
            if low.startswith("location:"):
                final = line.split(":", 1)[1].strip()
            elif low.startswith("content-length:"):
                try:
                    size = int(line.split(":", 1)[1].strip())
                except ValueError:
                    pass
        if size:
            return final, size
    req = urllib.request.Request(url, headers={"User-Agent": "carla-agentic-tools",
                                               "Range": "bytes=0-0"})
    try:
        with urllib.request.urlopen(req, timeout=30) as fh:
            cr = fh.headers.get("Content-Range", "")
            total = int(cr.rsplit("/", 1)[1]) if "/" in cr else int(fh.headers.get("Content-Length") or 0)
            return fh.geturl(), total
    except Exception:
        return url, 0


def pick_release(version: str) -> dict:
    rels = releases()
    if version in ("latest", "", None):
        # Skip prereleases: "latest" should mean the newest stable line.
        stable = [r for r in rels if not r["prerelease"]]
        return (stable or rels)[0]
    for r in rels:
        if r["tag_name"] == version:
            return r
    raise SystemExit(f"no release tagged {version!r}; run `list` to see what exists")


def asset_urls(rel: dict) -> dict[str, str]:
    """{'package': url, 'maps': url} for THIS platform, from the release body."""
    want_ext = ".zip" if PLATFORM == "Windows" else ".tar.gz"
    out: dict[str, str] = {}
    for label, url in _links(rel["body"]):
        low = label.lower()
        if not low.endswith(want_ext.lower()):
            continue
        if "additionalmaps" in low.replace(" ", ""):
            out.setdefault("maps", url)
        elif low.startswith("carla"):
            out.setdefault("package", url)
    if "package" not in out:
        # Fallback to the historical pattern; correct for the 0.9.x line only.
        out["package"] = f"{CDN}/{PLATFORM}/CARLA_{rel['tag_name']}{want_ext}"
    return out


def human(n: int) -> str:
    return f"{n / 1e9:.1f} GB" if n else "size unknown"


def free_bytes(path: Path) -> int:
    p = path
    while not p.exists():
        p = p.parent
    return shutil.disk_usage(p).free


def download(url: str, dest: Path, dry: bool) -> Path:
    """Resumable download with curl (falls back to urllib). Skips a complete file."""
    final, size = head(url)
    out = dest / Path(final).name
    print(f"  url  : {final}")
    print(f"  size : {human(size)}")
    print(f"  into : {out}")
    if out.exists() and size and out.stat().st_size == size:
        print("  already downloaded and complete — skipping")
        return out
    # Extraction needs roughly as much again as the archive, so demand ~2.2x.
    need = int(size * 2.2) if size else 0
    have = free_bytes(dest)
    if need and have < need:
        raise SystemExit(f"  not enough disk: need ~{human(need)} (archive + extraction), "
                         f"have {human(have)} at {dest}")
    if shutil.which("curl"):
        cmd = ["curl", "-fL", "--retry", "3", "--retry-delay", "5", "-C", "-", "-o", str(out), final]
    else:
        cmd = [sys.executable, "-c",
               f"import urllib.request;urllib.request.urlretrieve({final!r}, {str(out)!r})"]
    print("  " + " ".join(cmd))
    if dry:
        print("  (dry run — nothing downloaded)")
        return out
    dest.mkdir(parents=True, exist_ok=True)
    rc = subprocess.run(cmd).returncode
    if rc != 0:
        raise SystemExit(f"download failed (exit {rc}); re-run to resume")
    if size and out.stat().st_size != size:
        raise SystemExit(f"size mismatch: got {out.stat().st_size}, expected {size}")
    return out


def extract(archive: Path, dest: Path, dry: bool) -> Path:
    """Extract into dest/<stem>/ and return the directory that holds CarlaUE4.sh."""
    target = dest / archive.name.replace(".tar.gz", "").replace(".zip", "")
    print(f"  extract: {archive.name} -> {target}")
    if dry:
        print("  (dry run — nothing extracted)")
        return target
    target.mkdir(parents=True, exist_ok=True)
    if archive.name.endswith(".zip"):
        with zipfile.ZipFile(archive) as z:
            z.extractall(target)
    else:
        # A CARLA tarball has no single top-level dir, hence the dedicated target.
        with tarfile.open(archive) as tf:
            # filter="data" refuses absolute paths, symlink escapes and device
            # nodes. Python 3.14 makes it the default; setting it explicitly keeps
            # 3.10-3.13 safe and silences the deprecation warning.
            if sys.version_info >= (3, 12):
                tf.extractall(target, filter="data")
            else:
                tf.extractall(target)
    return target


def find_launcher(root: Path) -> Path | None:
    for cand in (root / "CarlaUE4.sh", root / "LinuxNoEditor" / "CarlaUE4.sh",
                 root / "CarlaUnreal.sh"):
        if cand.exists():
            return cand
    hits = sorted(root.glob("**/CarlaUE4.sh")) + sorted(root.glob("**/CarlaUnreal.sh"))
    return hits[0] if hits else None


def report(kind: str, path: Path, version: str = "", extra: list[str] = ()) -> None:
    """The WHAT/WHERE contract the rest of the skills consume."""
    print()
    print("=== obtained ===")
    print(f"  kind    : {kind}")
    print(f"  version : {version or 'unknown'}")
    print(f"  path    : {path}")
    for line in extra:
        print(f"  {line}")
    print()
    print("  export these for the other skills:")
    if kind in ("release", "nightly"):
        print(f"    export CARLA_TARGET={path}")
        print("    # run it:            run-carla-server")
        print("    # install the client: install-python-api   (uses the wheel inside it)")
    elif kind == "checkout":
        print(f"    export CARLA_UE4_ROOT={path}")
        print("    export UE4_ROOT=/path/to/UnrealEngine_4.26")
        print("    # build it: build-carla-ue4")
    elif kind == "docker":
        print(f"    # image: {path} — run it with --net=host and the nvidia runtime")
        print("    # then: install-python-api --source pypi --version <the image tag>")


def cmd_list(_a) -> int:
    for r in releases()[:8]:
        urls = asset_urls(r)
        tag = r["tag_name"] + (" (prerelease)" if r["prerelease"] else "")
        bits = [k for k in ("package", "maps") if k in urls]
        print(f"{tag:24} {r['published_at'][:10]}  offers: {', '.join(bits) or 'nothing for ' + PLATFORM}")
    print(f"\nplatform detected: {PLATFORM}   (nightly: {NIGHTLY})")
    return 0


def cmd_resolve(a) -> int:
    rel = pick_release(a.version)
    print(f"release {rel['tag_name']} ({rel['published_at'][:10]}) on {PLATFORM}:")
    for kind, url in asset_urls(rel).items():
        final, size = head(url)
        print(f"  {kind:8} {human(size):>12}  {final}")
    return 0


def cmd_release(a) -> int:
    rel = pick_release(a.version)
    urls = asset_urls(rel)
    dest = Path(a.dest).expanduser().resolve()
    print(f"CARLA {rel['tag_name']} for {PLATFORM}")
    archive = download(urls["package"], dest, a.dry_run)
    root = extract(archive, dest, a.dry_run)
    launcher = None if a.dry_run else find_launcher(root)
    extra = []
    if launcher:
        root = launcher.parent
        extra.append(f"launcher: {launcher}")
    elif not a.dry_run:
        extra.append("WARNING: no CarlaUE4.sh found — extraction may be incomplete")

    if a.with_maps:
        if "maps" not in urls:
            print("  note: this release publishes no AdditionalMaps for this platform")
        else:
            print("AdditionalMaps:")
            maps = download(urls["maps"], dest, a.dry_run)
            # AdditionalMaps is NOT extracted: it is imported by the release's own
            # ImportAssets script, which unpacks it into the cooked content tree.
            imp = root / "Import"
            print(f"  place it in {imp} and run {root}/ImportAssets.sh")
            if not a.dry_run:
                imp.mkdir(parents=True, exist_ok=True)
                shutil.move(str(maps), str(imp / maps.name))
                extra.append(f"maps staged in {imp} — run ./ImportAssets.sh to import")

    if not a.dry_run and not a.keep_archive and archive.exists():
        print(f"  removing archive {archive.name} (--keep-archive to keep it)")
        archive.unlink()
    report("release", root, rel["tag_name"], extra)
    return 0


def cmd_nightly(a) -> int:
    dest = Path(a.dest).expanduser().resolve()
    print("CARLA nightly (Dev/CARLA_Latest)")
    archive = download(NIGHTLY, dest, a.dry_run)
    root = extract(archive, dest, a.dry_run)
    launcher = None if a.dry_run else find_launcher(root)
    if launcher:
        root = launcher.parent
    report("nightly", root, "dev", ["note: rolling build, contents change without a tag"])
    return 0


def cmd_git(a) -> int:
    dest = Path(a.dest).expanduser().resolve() / f"carla-{a.ref}"
    cmd = ["git", "clone", "--depth", "1", "--branch", a.ref,
           "https://github.com/carla-simulator/carla.git", str(dest)]
    print("  " + " ".join(cmd))
    if a.dry_run:
        print("  (dry run — nothing cloned)")
    elif dest.exists():
        print(f"  {dest} already exists — leaving it alone")
    else:
        if subprocess.run(cmd).returncode != 0:
            raise SystemExit("clone failed")
    report("checkout", dest, a.ref,
           ["content is NOT included: build-carla-ue4 step 05 fetches it (~31 GB)",
            "a checkout must be BUILT before it can run (build-carla-ue4)"])
    return 0


def cmd_docker(a) -> int:
    image = f"carlasim/carla:{a.version}"
    cmd = ["docker", "pull", image]
    print("  " + " ".join(cmd))
    if a.dry_run:
        print("  (dry run — nothing pulled)")
    elif not shutil.which("docker"):
        raise SystemExit("docker not found on PATH")
    elif subprocess.run(cmd).returncode != 0:
        raise SystemExit("docker pull failed")
    report("docker", image, a.version,
           ["the image ships the server only; the client comes from install-python-api"])
    return 0


def main() -> None:
    p = argparse.ArgumentParser(description="Download CARLA.")
    sub = p.add_subparsers(dest="cmd", required=True)
    default_dest = os.environ.get("CARLA_DOWNLOAD_DIR") or str(Path.home() / "carla-downloads")

    sub.add_parser("list", help="published versions and what they offer").set_defaults(func=cmd_list)

    pr = sub.add_parser("resolve", help="print real URLs + sizes, download nothing")
    pr.add_argument("--version", default="latest")
    pr.set_defaults(func=cmd_resolve)

    pk = sub.add_parser("release", help="download + extract an official package")
    pk.add_argument("--version", default="latest")
    pk.add_argument("--with-maps", action="store_true", help="also fetch AdditionalMaps")
    pk.add_argument("--dest", default=default_dest)
    pk.add_argument("--keep-archive", action="store_true")
    pk.add_argument("--dry-run", action="store_true")
    pk.set_defaults(func=cmd_release)

    pn = sub.add_parser("nightly", help="download + extract the rolling Dev build")
    pn.add_argument("--dest", default=default_dest)
    pn.add_argument("--dry-run", action="store_true")
    pn.set_defaults(func=cmd_nightly)

    pg = sub.add_parser("git", help="shallow source checkout")
    pg.add_argument("--ref", default="ue4-dev")
    pg.add_argument("--dest", default=default_dest)
    pg.add_argument("--dry-run", action="store_true")
    pg.set_defaults(func=cmd_git)

    pd = sub.add_parser("docker", help="docker pull carlasim/carla")
    pd.add_argument("--version", default="0.9.16")
    pd.add_argument("--dry-run", action="store_true")
    pd.set_defaults(func=cmd_docker)

    args = p.parse_args()
    raise SystemExit(args.func(args))


if __name__ == "__main__":
    main()
