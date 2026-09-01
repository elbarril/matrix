#!/usr/bin/env python3
r"""Advisory phase-close checks that can only emit PASS or WARN.

For eval lessons, an explicit reasoned N/A matches ``^N/A\s*[-:]\s*\S+``
(case-insensitive). Otherwise the lesson text, or a cited lesson number, must
match brain/data/lessons.md or brain/data/lessons/<project>.md.
"""

import json
import os
import re
import sys

from _common import read_input, resolve_root
from validate_phase_close import VALID_PHASES


PATH_RE = re.compile(r"(?:brain/output/[^\s\"'`]+|/tmp/[^\s\"'`]+)")
NA_RE = re.compile(r"^N/A\s*[-:]\s*\S+", re.IGNORECASE)
LESSON_NUMBER_RE = re.compile(r"(?:lecci[oó]n|lesson)\s*#?\s*(\d+)", re.IGNORECASE)


def emit_warn(errors):
    result = {
        "hook": "precheck_phase_close",
        "ok": not errors,
        "verdict": "PASS" if not errors else "WARN",
        "errors": errors,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


def plan_step_text(root, plan, step):
    path = plan if os.path.isabs(plan) else os.path.join(root, plan)
    with open(path, encoding="utf-8") as handle:
        lines = handle.readlines()
    step_re = re.compile(rf"(?<![0-9.]){re.escape(str(step))}(?![0-9])")
    start = next((index for index, line in enumerate(lines) if step_re.search(line)), None)
    if start is None:
        raise ValueError(f"paso '{step}' no encontrado en {plan}")
    heading = re.match(r"^(#+)\s+", lines[start])
    end = len(lines)
    for index in range(start + 1, len(lines)):
        next_heading = re.match(r"^(#+)\s+", lines[index])
        next_step = re.match(r"^\s*\d+\.\d+\.\s+", lines[index])
        if (heading and next_heading and len(next_heading.group(1)) <= len(heading.group(1))) or (
            not heading and (next_heading or next_step)
        ):
            end = index
            break
    return "".join(lines[start:end]).strip()


def lesson_sources(root):
    paths = [os.path.join(root, "brain", "data", "lessons.md")]
    scoped = os.path.join(root, "brain", "data", "lessons")
    if os.path.isdir(scoped):
        paths.extend(
            os.path.join(scoped, name)
            for name in sorted(os.listdir(scoped))
            if name.endswith(".md")
        )
    chunks = []
    for path in paths:
        if os.path.isfile(path):
            with open(path, encoding="utf-8") as handle:
                chunks.append(handle.read())
    return "\n".join(chunks)


def run_checks(data):
    root = resolve_root()
    phase = str(data.get("phase") or "").strip().lower()
    errors = []
    plan = str(data.get("plan") or "").strip()
    step = str(data.get("step") or "").strip()

    if not plan or not step:
        errors.append("plan/step no provisto")
    else:
        try:
            compared = plan_step_text(root, plan, step)
            owner = re.search(r"(?i)\*{0,2}Dueño\*{0,2}\s*:\s*([^\n]+)", compared)
            labels = sorted({token.lower() for token in re.findall(r"\b(?:spec|develop|test|eval)\b", compared, re.IGNORECASE) if token.lower() in VALID_PHASES})
            if phase not in labels:
                errors.append(
                    f"fase '{phase}' no aparece literalmente en paso {step}; "
                    f"Dueño={owner.group(1).strip() if owner else 'no encontrado'}; texto comparado={compared}"
                )
        except Exception as exc:
            errors.append(f"no se pudo comparar plan/step: {exc}")

    for field in ("evidence", "lesson"):
        value = str(data.get(field) or "")
        for raw_path in PATH_RE.findall(value):
            referenced = raw_path.rstrip(".,;:)]}")
            disk_path = referenced if os.path.isabs(referenced) else os.path.join(root, referenced)
            if not os.path.isfile(disk_path):
                errors.append(f"{field} referencia un archivo inexistente: {referenced}")

    if phase == "eval":
        lesson = str(data.get("lesson") or "").strip()
        if not NA_RE.match(lesson):
            sources = lesson_sources(root)
            number_match = LESSON_NUMBER_RE.search(lesson)
            number_found = bool(
                number_match
                and re.search(rf"(?m)^\s*{re.escape(number_match.group(1))}\.", sources)
            )
            text_found = bool(lesson and lesson.casefold() in sources.casefold())
            if not number_found and not text_found:
                errors.append(
                    "lesson de eval no matchea lessons.md/lessons/<project>.md ni es N/A razonado"
                )
    return errors


def main():
    try:
        data = read_input()
        if not isinstance(data, dict):
            raise ValueError("el payload debe ser un objeto JSON")
        return emit_warn(run_checks(data))
    except BaseException as exc:
        return emit_warn([f"fallo interno del precheck: {type(exc).__name__}: {exc}"])


if __name__ == "__main__":
    sys.exit(main())
