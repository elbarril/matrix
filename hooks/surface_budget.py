#!/usr/bin/env python3
"""Seraph · surface_budget — size budgets for the shared document surface.

Checks the three docs that are injected on every activation — AGENTS.md,
DEVIN.md, brain/agents/neo.md — against warn/fail budgets, and reports each as
`ok` (under warn), `warn` (past warn, under fail), `fail` (past fail), or
`missing`.

The two cut mechanisms are asymmetric on purpose: AGENTS.md is *injected* and
truncated at 16.384 B, so it keeps byte budgets (warn 15.500 / fail 16.200,
fail always below the real cut). DEVIN.md and brain/agents/neo.md are *read*
with the `read` tool, which stops at 20.000 chars, so they use char budgets
(warn 19.500 / fail 20.000). Each surface reports `bytes` (diagnostic) and
`chars`, plus its comparison `unit`.

Threshold history, documented so it does not silently return: the old byte
fails (22/24 KiB) sat ABOVE the real 20.000-char read cutoff, which is why the
detector could pass a file that still truncated. The correction lowers the
fail to the real unit (20.000 chars) and makes the warn a uniform 500-char
buffer on both read surfaces.

Severity is asymmetric on purpose: `ok: false` only when a surface EXCEEDS its
`fail` budget. A `warn` state never flips `ok` — the boot channel surfaces it
in `boot_warn.warns` so the master sees it, but activation never blocks on it.

Usage:
  python3 hooks/surface_budget.py
  bin/matrix hooks surface_budget
"""

import os

from _common import emit, read_input, resolve_root


# Umbrales de la superficie documental compartida.
# AGENTS.md se INYECTA y se trunca a 16.384 B: sigue en bytes, con fail (16.200)
# siempre por debajo del corte real. DEVIN.md y neo.md se LEEN con read, que
# corta a 20.000 chars: van en chars, fail 20.000, warn con buffer uniforme de
# 500 chars. El fail viejo en bytes (22/24 KiB) quedaba por encima del corte y
# dejaba el detector inerte; esta tabla baja el fail a la unidad real de corte.
SURFACES = [
    {"name": "AGENTS.md", "path": "AGENTS.md", "warn": 15_500, "fail": 16_200, "unit": "bytes"},
    {"name": "DEVIN.md", "path": "DEVIN.md", "warn": 19_500, "fail": 20_000, "unit": "chars"},
    {"name": "brain/agents/neo.md", "path": os.path.join("brain", "agents", "neo.md"), "warn": 19_500, "fail": 20_000, "unit": "chars"},
]


def _char_count(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return len(fh.read())
    except OSError:
        return None


def validate(_data):
    root = resolve_root()
    surfaces = []
    for spec in SURFACES:
        path = os.path.join(root, spec["path"])
        if not os.path.isfile(path):
            surfaces.append(
                {
                    "name": spec["name"],
                    "bytes": None,
                    "chars": None,
                    "unit": spec["unit"],
                    "warn": spec["warn"],
                    "fail": spec["fail"],
                    "status": "missing",
                }
            )
            continue
        size = os.path.getsize(path)
        chars = _char_count(path) or 0
        # Compare in the surface's own unit so the fail always sits below the
        # real cut (bytes for AGENTS.md, chars for the two read surfaces).
        measure = size if spec["unit"] == "bytes" else chars
        if measure > spec["fail"]:
            status = "fail"
        elif measure > spec["warn"]:
            status = "warn"
        else:
            status = "ok"
        surfaces.append(
            {
                "name": spec["name"],
                "bytes": size,
                "chars": chars,
                "unit": spec["unit"],
                "warn": spec["warn"],
                "fail": spec["fail"],
                "status": status,
            }
        )
    return {
        "hook": "surface_budget",
        "ok": all(s["status"] != "fail" for s in surfaces),
        "surfaces": surfaces,
    }


def main():
    emit(validate(read_input()))


if __name__ == "__main__":
    main()
