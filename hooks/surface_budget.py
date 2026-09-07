#!/usr/bin/env python3
"""Seraph · surface_budget — size budgets for the shared document surface.

Checks the three docs that are injected on every activation — AGENTS.md,
DEVIN.md, brain/agents/neo.md — against warn/fail byte budgets, and reports
each as `ok` (under warn), `warn` (past warn, under fail), `fail` (past fail),
or `missing`.

Severity is asymmetric on purpose: `ok: false` only when a surface EXCEEDS its
`fail` budget. A `warn` state never flips `ok` — the boot channel surfaces it
in `boot_warn.warns` so the master sees it, but activation never blocks on it.

Usage:
  python3 hooks/surface_budget.py
  bin/matrix hooks surface_budget
"""

import os

from _common import emit, read_input, resolve_root


# Umbrales de la superficie documental compartida (bytes).
# AGENTS.md: 16_384 B es la truncación de inyección; fail queda SIEMPRE por
# debajo (16_200) para que el límite de alerta active antes del corte real.
# DEVIN.md y neo.md: límites informales de lectura medidos (ver
# brain/output/research/growth-risk-report-2026-09.md).
# SUBIR UN UMBRAL ES CADENA COMPLETA: requiere Morpheus + Architect + Smith —
# subir el límite en vez de recortar es el patrón de crecimiento confirmado y
# no se hace en un fix de rutina.
SURFACES = [
    {"name": "AGENTS.md", "path": "AGENTS.md", "warn": 15_500, "fail": 16_200},
    {"name": "DEVIN.md", "path": "DEVIN.md", "warn": 20 * 1024, "fail": 24 * 1024},
    {"name": "brain/agents/neo.md", "path": os.path.join("brain", "agents", "neo.md"), "warn": 18 * 1024, "fail": 22 * 1024},
]


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
                    "warn": spec["warn"],
                    "fail": spec["fail"],
                    "status": "missing",
                }
            )
            continue
        size = os.path.getsize(path)
        if size > spec["fail"]:
            status = "fail"
        elif size > spec["warn"]:
            status = "warn"
        else:
            status = "ok"
        surfaces.append(
            {
                "name": spec["name"],
                "bytes": size,
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
