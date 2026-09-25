#!/usr/bin/env python3
"""Read declarative adapter metadata for Layer 1."""
import json
import os
import sys

ROOT = os.environ.get("MATRIX_ROOT") or os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))
)


class _AdapterMetaUnreadable(Exception):
    """metadata exists but could not be read/parsed (import/open/YAMLError)."""


def load_yaml(path):
    import yaml                     # fuera del try: si falla, propaga
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def binding(target):
    adapter_yaml = os.path.join(ROOT, "adapters", target, "adapter.yaml")
    if not os.path.isfile(adapter_yaml):
        return None
    try:
        config = load_yaml(adapter_yaml)
    except Exception as exc:
        raise _AdapterMetaUnreadable(exc) from exc
    if not isinstance(config, dict):
        return None
    value = config.get("binding")
    if not isinstance(value, dict):
        return None
    file_name = value.get("file")
    begin_marker = value.get("begin_marker")
    end_marker = value.get("end_marker")
    exclude_entries = value.get("exclude_entries")
    doc_path = value.get("doc_path")
    if not all(isinstance(item, str) and item for item in (file_name, begin_marker, end_marker)):
        return None
    result = {
        "file": file_name,
        "begin_marker": begin_marker,
        "end_marker": end_marker,
    }
    # exclude_entries is optional since the no-binding rework (devin adapter no
    # longer declares it). Keep the field when a target still provides it so
    # adapter_binding() in bin/lib/binding.sh keeps parsing it uniformly.
    if isinstance(exclude_entries, list) and all(
        isinstance(item, str) and item for item in exclude_entries
    ):
        result["exclude_entries"] = exclude_entries
    if isinstance(doc_path, str) and doc_path:
        result["doc_path"] = doc_path
    return result


def main():
    if len(sys.argv) != 3 or sys.argv[1] != "binding" or not sys.argv[2].startswith("--target="):
        sys.exit(1)
    target = sys.argv[2].split("=", 1)[1]
    try:
        value = binding(target)
    except _AdapterMetaUnreadable as exc:
        cause = exc.__cause__ or exc
        print(f"[trainman:adapter-meta] error: metadata ilegible para '{target}': "
              f"{type(cause).__name__}: {cause}", file=sys.stderr)
        print(f"[trainman:adapter-meta] sys.executable={sys.executable}", file=sys.stderr)
        print(f"[trainman:adapter-meta] sys.path[0:5]={sys.path[:5]}", file=sys.stderr)
        sys.exit(2)
    if value is None:
        sys.exit(1)
    print(json.dumps(value, ensure_ascii=False))


if __name__ == "__main__":
    main()
