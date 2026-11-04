"""Basic checks that the store will load in Umbrel."""
import pathlib
import sys

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[2]
REQUIRED = ["manifestVersion", "id", "name", "tagline", "category", "version", "port",
            "description", "website", "support", "gallery"]

errors = []
store = yaml.safe_load((ROOT / "umbrel-app-store.yml").read_text())
for key in ("id", "name"):
    if not store.get(key):
        errors.append(f"umbrel-app-store.yml: missing {key}")

ports = {}
for manifest_path in sorted(ROOT.glob("*/umbrel-app.yml")):
    app = manifest_path.parent
    m = yaml.safe_load(manifest_path.read_text())
    for key in REQUIRED:
        if key not in m:
            errors.append(f"{app.name}: missing {key}")
    if m.get("id") != app.name:
        errors.append(f"{app.name}: id must match the folder name")
    if not str(m.get("id", "")).startswith(store["id"] + "-"):
        errors.append(f"{app.name}: id must start with '{store['id']}-'")
    if m.get("port") in ports:
        errors.append(f"{app.name}: port {m['port']} already used by {ports[m['port']]}")
    ports[m.get("port")] = app.name
    compose = yaml.safe_load((app / "docker-compose.yml").read_text())
    for name, svc in compose.get("services", {}).items():
        image = svc.get("image")
        if image and "@sha256:" not in image:
            errors.append(f"{app.name}: service {name} image should be pinned with @sha256")

if errors:
    print("\n".join(errors))
    sys.exit(1)
print(f"OK: {len(ports)} app(s)")
