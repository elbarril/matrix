#!/usr/bin/env python3
"""Read declarative adapter metadata for Layer 1."""
import json
import os
import sys

ROOT = os.environ.get("MATRIX_ROOT") or os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))
)


def load_yaml(path):
    try:
        import yaml
        with open(path, encoding="utf-8") as fh:
            return yaml.safe_load(fh) or {}
    except Exception:
        return {}


def binding(target):
    adapter_yaml = os.path.join(ROOT, "adapters", target, "adapter.yaml")
    if not os.path.isfile(adapter_yaml):
        return None
    config = load_yaml(adapter_yaml)
    if not isinstance(config, dict):
        return None
    value = config.get("binding")
    if not isinstance(value, dict):
        return None
    file_name = value.get("file")
    begin_marker = value.get("begin_marker")
    end_marker = value.get("end_marker")
    gitignore_entries = value.get("gitignore_entries")
    doc_path = value.get("doc_path")
    if not all(isinstance(item, str) and item for item in (file_name, begin_marker, end_marker)):
        return None
    if not isinstance(gitignore_entries, list) or not all(
        isinstance(item, str) and item for item in gitignore_entries
    ):
        return None
    result = {
        "file": file_name,
        "begin_marker": begin_marker,
        "end_marker": end_marker,
        "gitignore_entries": gitignore_entries,
    }
    if isinstance(doc_path, str) and doc_path:
        result["doc_path"] = doc_path
    return result


def main():
    if len(sys.argv) != 3 or sys.argv[1] != "binding" or not sys.argv[2].startswith("--target="):
        sys.exit(1)
    value = binding(sys.argv[2].split("=", 1)[1])
    if value is None:
        sys.exit(1)
    print(json.dumps(value, ensure_ascii=False))


if __name__ == "__main__":
    main()
