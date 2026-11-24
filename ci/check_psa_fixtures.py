"""Check that the IaC-excluded PSA fixtures stay out of deployment inputs."""

from pathlib import Path
import sys

from ruamel.yaml import YAML


def main(fixture_paths):
    root = Path.cwd()
    yaml = YAML(typ="safe")
    fixtures = {Path(path).resolve(strict=True) for path in fixture_paths}
    identities = set()
    for fixture in fixtures:
        document = yaml.load(fixture.read_text(encoding="utf-8-sig"))
        identities.add((document["kind"], document["metadata"]["name"]))

    visited = set()

    def check_object(value, source):
        if isinstance(value, dict):
            metadata = value.get("metadata")
            if isinstance(metadata, dict) and (value.get("kind"), metadata.get("name")) in identities:
                raise ValueError(f"PSA fixture copied into deployable manifest: {source.relative_to(root)}")
            for child in value.values():
                check_object(child, source)
        elif isinstance(value, list):
            for child in value:
                check_object(child, source)

    def inspect(path):
        path = path.resolve()
        if path in fixtures:
            raise ValueError(f"PSA fixture referenced by deployment: {path.relative_to(root)}")
        if not path.is_relative_to(root):
            raise ValueError("Deployment references a path outside the repository")
        if path.is_dir():
            entrypoints = [path / name for name in ("kustomization.yaml", "kustomization.yml", "Kustomization")
                           if (path / name).is_file()]
            if len(entrypoints) != 1:
                raise ValueError(f"Expected one Kustomize entrypoint in {path.relative_to(root)}")
            inspect(entrypoints[0])
            return
        if path in visited:
            return
        visited.add(path)
        for document in yaml.load_all(path.read_text(encoding="utf-8-sig")):
            check_object(document, path)
            if not isinstance(document, dict) or document.get("kind") not in ("Kustomization", "Component"):
                continue
            for key in ("resources", "bases", "components", "generators", "transformers",
                        "patchesStrategicMerge", "patches", "patchesJson6902"):
                for entry in document.get(key, []):
                    reference = entry if isinstance(entry, str) else entry.get("path")
                    if reference and "\n" not in reference:
                        inspect(path.parent / reference)

    for entrypoint in ("k8s", "ci/k8s-dast/bootstrap.yaml", "ci/k8s-dast/target.yaml"):
        inspect(root / entrypoint)
    print("PSA negative fixtures are absent from SecureStay deployment inputs")


if __name__ == "__main__":
    try:
        main(sys.argv[1:])
    except (OSError, ValueError) as error:
        raise SystemExit(str(error)) from None
