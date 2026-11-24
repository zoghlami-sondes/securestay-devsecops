"""Bind one scanned OCI archive to the image digest used by the test deployment."""

import hashlib
import json
import os
from pathlib import Path
import re
import sys


def sha256_file(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def read_blob(root, digest):
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", digest):
        raise ValueError("Invalid OCI descriptor")
    path = root / "blobs" / "sha256" / digest.removeprefix("sha256:")
    if "sha256:" + sha256_file(path) != digest:
        raise ValueError("OCI blob digest mismatch")
    return json.loads(path.read_bytes())


def metadata(root, archive, expected_checksum, report, revision, build_url):
    if sha256_file(archive) != expected_checksum:
        raise ValueError("OCI archive changed during image scanning")
    descriptors = json.loads((root / "index.json").read_bytes())["manifests"]
    if len(descriptors) != 1:
        raise ValueError("Expected a single-platform OCI image")
    manifest_digest = descriptors[0]["digest"]
    manifest = read_blob(root, manifest_digest)
    config_digest = manifest["config"]["digest"]
    config = read_blob(root, config_digest)
    if (config["os"], config["architecture"]) != ("linux", "amd64"):
        raise ValueError("Image platform does not match desktop-control-plane")
    return {
        "archive": "securestay.oci.tar",
        "archive_sha256": expected_checksum,
        "image": f"docker.io/library/securestay@{manifest_digest}",
        "manifest_digest": manifest_digest,
        "config_digest": config_digest,
        "platform": "linux/amd64",
        "trivy_report_sha256": sha256_file(report),
        "revision": revision,
        "build_url": build_url,
    }


if __name__ == "__main__":
    _, layout, archive, checksum, report, revision, output = sys.argv
    result = metadata(Path(layout), Path(archive), checksum, Path(report),
                      revision, os.environ["BUILD_URL"])
    Path(output).write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
