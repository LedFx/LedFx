"""Relabel the bundled UI for a backend patch without rebuilding its features."""

import argparse
import hashlib
import json
import re
from pathlib import Path


def bump_frontend(root: Path, old_version: str, new_version: str) -> str:
    manifest_path = root / "asset-manifest.json"
    manifest_text = manifest_path.read_text()
    manifest = json.loads(manifest_text)
    bundle = root / manifest["files"]["main.js"].lstrip("/")
    old_name = bundle.name
    text = bundle.read_text()
    old_label = f'rE:"{old_version}"'
    new_label = f'rE:"{new_version}"'
    if text.count(old_label) != 1:
        raise ValueError(
            "Expected exactly one frontend version export; inspect the bundle"
        )
    text = text.replace(old_label, new_label)
    # Hash the executable body, excluding the license comment that names the file.
    body = text.split("\n", 1)[1]
    digest = hashlib.sha256(body.encode()).hexdigest()[:8]
    new_name = f"main.{digest}.js"
    new_bundle = bundle.with_name(new_name)
    license_path = bundle.with_name(old_name + ".LICENSE.txt")
    new_license = bundle.with_name(new_name + ".LICENSE.txt")
    if new_bundle.exists() or new_license.exists():
        raise ValueError("Destination assets already exist")
    if not license_path.is_file():
        raise ValueError("Missing bundle license file")

    index_path = root / "index.html"
    index_text = index_path.read_text()
    worker_path = root / "service-worker.js"
    worker_text = worker_path.read_text()
    for name, contents in (
        ("index", index_text),
        ("manifest", manifest_text),
        ("service worker", worker_text),
    ):
        if old_name not in contents:
            raise ValueError(f"Missing bundle reference in {name}")
    index_text = index_text.replace(old_name, new_name)
    worker_text = worker_text.replace(old_name, new_name)
    # Workbox caches index.html by revision; change it with the script reference.
    index_revision = hashlib.md5(index_text.encode(), usedforsecurity=False).hexdigest()
    worker_text, count = re.subn(
        r"('revision':')[^']+(',\s*'url':'/index\.html')",
        lambda match: match[1] + index_revision + match[2],
        worker_text,
    )
    if count != 1:
        raise ValueError("Expected exactly one index.html precache revision")

    new_bundle.write_text(text.replace(old_name, new_name))
    license_path.rename(new_license)
    bundle.unlink()
    index_path.write_text(index_text)
    manifest_path.write_text(manifest_text.replace(old_name, new_name))
    worker_path.write_text(worker_text)
    return new_name


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("old_version")
    parser.add_argument("new_version")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1] / "ledfx_frontend"
    print(bump_frontend(root, args.old_version, args.new_version))


if __name__ == "__main__":
    main()
