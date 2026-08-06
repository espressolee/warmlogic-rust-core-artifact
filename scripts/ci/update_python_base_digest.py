#!/usr/bin/env python3
"""Update pinned Docker Hub digest for a tagged Python base image."""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


ACCEPT_HEADER = (
    "application/vnd.oci.image.index.v1+json, "
    "application/vnd.docker.distribution.manifest.list.v2+json"
)


def fail(msg: str) -> None:
    print(f"[DIGEST-REFRESH] ERROR: {msg}")
    sys.exit(1)


def parse_image(image: str) -> tuple[str, str]:
    if ":" not in image:
        fail(f"image must include explicit tag, got: {image!r}")
    name, tag = image.rsplit(":", 1)
    if "/" not in name:
        repo = f"library/{name}"
    else:
        repo = name
    return repo, tag


def fetch_token(repo: str) -> str:
    query = urllib.parse.urlencode(
        {
            "service": "registry.docker.io",
            "scope": f"repository:{repo}:pull",
        }
    )
    url = f"https://auth.docker.io/token?{query}"
    with urllib.request.urlopen(url, timeout=20) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    token = payload.get("token")
    if not token:
        fail("failed to acquire registry token")
    return str(token)


def fetch_digest(repo: str, tag: str, token: str) -> str:
    url = f"https://registry-1.docker.io/v2/{repo}/manifests/{tag}"
    req = urllib.request.Request(url, method="HEAD")
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Accept", ACCEPT_HEADER)
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            digest = resp.headers.get("docker-content-digest")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        fail(f"registry request failed: HTTP {exc.code} {body}")
    if not digest or not digest.startswith("sha256:"):
        fail(f"invalid digest header: {digest!r}")
    return digest.removeprefix("sha256:")


def find_current_digests(dockerfile_text: str, image: str) -> list[str]:
    pattern = re.compile(
        rf"^FROM\s+{re.escape(image)}@sha256:([0-9a-f]{{64}})\s+AS\s+\S+\s*$",
        re.MULTILINE,
    )
    return pattern.findall(dockerfile_text)


def update_dockerfile_text(dockerfile_text: str, image: str, new_digest: str) -> tuple[str, int]:
    pattern = re.compile(
        rf"(FROM\s+{re.escape(image)}@sha256:)[0-9a-f]{{64}}(\s+AS\s+\S+\s*$)",
        re.MULTILINE,
    )
    updated, count = pattern.subn(rf"\g<1>{new_digest}\g<2>", dockerfile_text)
    return updated, count


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dockerfile", type=Path, default=Path("Dockerfile"))
    parser.add_argument("--image", default="python:3.12-slim")
    parser.add_argument(
        "--mode",
        choices=("check", "apply"),
        default="apply",
        help="check: fail if stale, apply: rewrite Dockerfile when stale",
    )
    args = parser.parse_args()

    if not args.dockerfile.exists():
        fail(f"missing dockerfile: {args.dockerfile}")
    dockerfile_text = args.dockerfile.read_text(encoding="utf-8")

    existing = find_current_digests(dockerfile_text, args.image)
    if not existing:
        fail(f"no pinned FROM lines found for image {args.image}")
    if len(set(existing)) != 1:
        fail(f"inconsistent pinned digests for {args.image}: {sorted(set(existing))}")
    current_digest = existing[0]

    repo, tag = parse_image(args.image)
    token = fetch_token(repo)
    latest_digest = fetch_digest(repo, tag, token)

    print(
        f"[DIGEST-REFRESH] image={args.image} current=sha256:{current_digest} "
        f"latest=sha256:{latest_digest}"
    )

    if current_digest == latest_digest:
        print("[DIGEST-REFRESH] OK: Dockerfile already up to date")
        return

    if args.mode == "check":
        fail("Dockerfile digest is stale; run with --mode apply")

    updated, changed = update_dockerfile_text(dockerfile_text, args.image, latest_digest)
    if changed == 0:
        fail("failed to update Dockerfile digest references")
    args.dockerfile.write_text(updated, encoding="utf-8")
    print(f"[DIGEST-REFRESH] UPDATED: replaced {changed} FROM line(s)")


if __name__ == "__main__":
    main()
