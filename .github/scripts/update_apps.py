"""Bring apps up to the newest upstream release.

Each app folder with an update.yml is checked against its image registry (Docker Hub or
GitHub's ghcr.io). When there is a newer x.y.z tag, or the app doesn't run that tag yet, the
image line in docker-compose.yml (tag + digest) and the version, icon link and release notes
in umbrel-app.yml are updated. Prints the changed apps.

update.yml:
  image: owner/name or ghcr.io/owner/name   image to follow
  releases: URL                              where people can read what changed
  changelog: URL (optional)                  raw CHANGELOG.md with "## x.y.z" sections: used as release notes
  replaces: [old/image] (optional)           older image names this app used, swapped on the first update
"""

import json
import pathlib
import re
import sys
import urllib.error
import urllib.request

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[2]
SEMVER = re.compile(r"^v?\d+\.\d+\.\d+$")
INDEX = (
    "application/vnd.oci.image.index.v1+json,application/vnd.docker.distribution.manifest.list.v2+json,"
    "application/vnd.oci.image.manifest.v1+json,application/vnd.docker.distribution.manifest.v2+json"
)


def ver(v):
    return tuple(int(x) for x in re.findall(r"\d+", v)[:3])


def fetch(url, headers=None, method="GET"):
    req = urllib.request.Request(url, headers=headers or {}, method=method)
    return urllib.request.urlopen(req, timeout=30)


def latest_docker_hub(image):
    url = f"https://hub.docker.com/v2/repositories/{image}/tags?page_size=100&ordering=last_updated"
    with fetch(url) as r:
        tags = [t for t in json.load(r)["results"] if SEMVER.match(t["name"]) and t.get("digest")]
    if not tags:
        return None, None
    best = max(tags, key=lambda t: ver(t["name"]))
    return best["name"], best["digest"]


def latest_ghcr(image):
    repo = image.removeprefix("ghcr.io/")
    with fetch(f"https://ghcr.io/token?scope=repository:{repo}:pull") as r:
        auth = {"Authorization": "Bearer " + json.load(r)["token"]}
    with fetch(f"https://ghcr.io/v2/{repo}/tags/list?n=1000", auth) as r:
        tags = [t for t in json.load(r).get("tags") or [] if SEMVER.match(t)]
    if not tags:
        return None, None
    best = max(tags, key=ver)
    with fetch(f"https://ghcr.io/v2/{repo}/manifests/{best}", {**auth, "Accept": INDEX}, "HEAD") as r:
        return best, r.headers["Docker-Content-Digest"]


def latest(image):
    try:
        return latest_ghcr(image) if image.startswith("ghcr.io/") else latest_docker_hub(image)
    except urllib.error.HTTPError as e:
        if e.code in (403, 404):  # not published yet
            return None, None
        raise


def summarize(section, limit=600):
    """A changelog section as one line: intro and bullet points joined as sentences."""
    items, cur = [], ""
    for line in section.splitlines():
        text = line.strip()
        if not text:
            continue
        if text[:2] in ("- ", "* ") or not cur:
            if cur:
                items.append(cur)
            cur = text.lstrip("-* ").strip()
        else:  # a wrapped bullet continues
            cur += " " + text
    if cur:
        items.append(cur)
    out = " ".join(i if i.endswith((".", ":", "!", "?")) else i + "." for i in items)
    if len(out) > limit:
        out = out[: limit - 1].rsplit(" ", 1)[0].rstrip(",;:") + "…"
    return out


def notes_for(cfg, version):
    """This version's section of the app's changelog, as one line; or a link to the releases."""
    if cfg.get("changelog"):
        try:
            with fetch(cfg["changelog"]) as r:
                text = r.read().decode()
            m = re.search(rf"^## v?{re.escape(version)}\b.*?\n(.*?)(?=^## |\Z)", text, re.M | re.S)
            if m:
                return summarize(m.group(1))
        except OSError as e:
            print(f"changelog unavailable ({e}); using the releases link", file=sys.stderr)
    return f"Updated to {version}. See what changed: {cfg.get('releases', 'the upstream project')}"


def main():
    changed = []
    for cfg_path in sorted(ROOT.glob("*/update.yml")):
        app = cfg_path.parent
        cfg = yaml.safe_load(cfg_path.read_text())
        image = cfg["image"]
        tag, digest = latest(image)
        manifest_path, compose_path = app / "umbrel-app.yml", app / "docker-compose.yml"
        manifest, compose = manifest_path.read_text(), compose_path.read_text()
        current = re.search(r'^version:\s*"?([^"\n]+)"?', manifest, re.M).group(1)
        names = [image, *cfg.get("replaces", [])]
        image_re = re.compile(rf"(image:\s*)(?:{'|'.join(map(re.escape, names))}):[^\s]+")
        if not image_re.search(compose):
            sys.exit(f"{app.name}: image {image} not found in docker-compose.yml")
        if not tag:
            print(f"{app.name}: no releases yet", file=sys.stderr)
            continue
        version = tag.lstrip("v")
        running = f"{image}:{tag}@{digest}" in compose
        if ver(tag) < ver(current) or (ver(tag) == ver(current) and running):
            print(f"{app.name}: up to date ({current})", file=sys.stderr)
            continue

        compose = image_re.sub(rf"\g<1>{image}:{tag}@{digest}", compose)
        manifest = re.sub(r"^version:.*$", f'version: "{version}"', manifest, flags=re.M)
        manifest = re.sub(r"^(icon: \S+?icon\.svg)\?v=\S+$", rf"\1?v={version}", manifest, flags=re.M)
        notes = notes_for(cfg, version).replace("\\", "")
        manifest = re.sub(r"^releaseNotes:.*?(?=^\w)", f"releaseNotes: >-\n  {notes}\n", manifest, flags=re.M | re.S)

        compose_path.write_text(compose)
        manifest_path.write_text(manifest)
        changed.append(f"{app.name} {current} -> {version}")
        print(f"{app.name}: {current} -> {version}", file=sys.stderr)
    print("; ".join(changed))


if __name__ == "__main__":
    main()
