#!/usr/bin/env python3
"""Seraph · validate_ship — generic ship manifest validation.

Validates a federated ship under `brain/subsystems/<ship>/` against its own
manifest. The hook does not know each ship; it reads the manifest declared in
the ship's `AGENTS.md` and checks the filesystem reality.

Usage:
  python3 hooks/validate_ship.py '{"ship":"logos"}'
  bin/matrix hooks validate_ship '{"ship":"logos"}'
"""

import fnmatch
import os
import re

from _common import emit, parse_frontmatter, parse_scalar_list, read_input, resolve_root

REQUIRED_MANIFEST_KEYS = {
    "ship", "captain", "crew", "route-when", "writes", "reads", "state", "crew-max"
}
VALID_MODEL_POLICIES = {"cheap", "reasoning", "auto"}
ROOT_AGENT_DEPTH = 0  # Neo


def read_agent_check(path):
    """Check an agent file for required frontmatter and XML sections."""
    if not os.path.isfile(path):
        return None, "missing"
    fm = parse_frontmatter(path)
    errors = []
    if not fm.get("name"):
        errors.append("missing name")
    if not fm.get("description"):
        errors.append("missing description")
    if fm.get("model_policy") not in VALID_MODEL_POLICIES:
        errors.append(f"model_policy must be in {VALID_MODEL_POLICIES}")
    capabilities = fm.get("capabilities", [])
    if not capabilities:
        errors.append("capabilities empty")
    body = open(path, encoding="utf-8").read()
    if "<activation>" not in body:
        errors.append("missing <activation>")
    if "<boundaries>" not in body:
        errors.append("missing <boundaries>")
    return fm, "; ".join(errors) if errors else ""


def find_manifests(root):
    """Yield (ship_name, ship_dir) for every ship with an AGENTS.md frontmatter."""
    subsystems = os.path.join(root, "brain", "subsystems")
    if not os.path.isdir(subsystems):
        return
    for name in sorted(os.listdir(subsystems)):
        ship_dir = os.path.join(subsystems, name)
        if not os.path.isdir(ship_dir):
            continue
        agents_md = os.path.join(ship_dir, "AGENTS.md")
        if not os.path.isfile(agents_md):
            continue
        fm = parse_frontmatter(agents_md)
        if fm.get("ship"):
            yield fm["ship"], ship_dir


def no_core_state_check(root, ship_dir, state_path):
    """Layer-3 static check: state path is not under brain/state/ and no ship
    file mentions brain/state/ except in a line that also says never/nunca/no toca."""
    errors = []
    state_abs = os.path.normpath(os.path.join(root, state_path))
    core_state = os.path.normpath(os.path.join(root, "brain", "state"))
    if state_abs == core_state or state_abs.startswith(core_state + os.sep):
        errors.append("state path falls under brain/state/")

    literal = re.compile(r"brain/state/", re.IGNORECASE)
    allowed = re.compile(r"nunca|never|no toca|not touch|does not touch", re.IGNORECASE)
    for dirpath, _dirnames, filenames in os.walk(ship_dir):
        for f in filenames:
            if not f.endswith(".md"):
                continue
            p = os.path.join(dirpath, f)
            try:
                for i, ln in enumerate(open(p, encoding="utf-8").read().splitlines(), 1):
                    if literal.search(ln) and not allowed.search(ln):
                        errors.append(f"{os.path.relpath(p, root)}:{i} mentions brain/state/")
                        break
            except Exception:
                pass
    return errors


def state_gitignored(root, state_path):
    """Check that .gitignore ignores the state directory or all of its contents.

    Accepts either a directory rule (`dir/`) or a contents rule (`dir/*`) with
    a `.gitkeep` re-inclusion.
    """
    gi = os.path.join(root, ".gitignore")
    if not os.path.isfile(gi):
        return False
    positives = []
    negatives = []
    with open(gi, encoding="utf-8") as fh:
        for ln in fh:
            ln = ln.split("#", 1)[0].strip()
            if not ln:
                continue
            if ln.startswith("!"):
                negatives.append(ln[1:])
            else:
                positives.append(ln)

    # Normalize state path (no trailing slash for matching, then test variants)
    base = state_path.rstrip("/")

    def matches(path, pat):
        return fnmatch.fnmatch(path, pat) or fnmatch.fnmatch(path + "/", pat)

    # Case 1: the directory itself is ignored.
    for pat in positives:
        if matches(base, pat):
            # Re-inclusion of the whole directory cancels it.
            for neg in negatives:
                if matches(base, neg) and not (matches(base + "/.gitkeep", neg) or matches(base + "/*", neg)):
                    return False
            return True

    # Case 2: the contents are ignored (`dir/*` or `dir/**`) and .gitkeep is the
    # only re-included file.
    for pat in positives:
        if matches(base + "/*", pat) or matches(base + "/**", pat):
            return True
    return False


def corpus_shape(root, state_path, captain):
    """Validate every non-empty topic against the corpus source/appraisal shape."""
    state_abs = os.path.normpath(os.path.join(root, state_path))
    if not os.path.isdir(state_abs):
        return True, "state directory not yet populated, corpus_shape skipped"

    verified = []
    skipped_empty = []
    nonconformant = []
    errors = []

    for topic in sorted(os.listdir(state_abs)):
        topic_dir = os.path.join(state_abs, topic)
        if not os.path.isdir(topic_dir):
            continue

        sources_dir = os.path.join(topic_dir, "sources")
        appraisals_dir = os.path.join(topic_dir, "appraisals")
        has_sources_dir = os.path.isdir(sources_dir)
        has_appraisals_dir = os.path.isdir(appraisals_dir)

        # `_topic.yaml` declares a not-yet-populated topic, not evidence content.
        # Any other regular file, at any depth, makes a missing corpus structure
        # a real corpus-spec violation rather than an empty-topic skip.
        content_files = []
        for dirpath, _dirnames, filenames in os.walk(topic_dir):
            for filename in filenames:
                path = os.path.join(dirpath, filename)
                if os.path.normpath(path) == os.path.join(topic_dir, "_topic.yaml"):
                    continue
                content_files.append(path)

        if not (has_sources_dir and has_appraisals_dir):
            if not content_files:
                skipped_empty.append(topic)
                continue
            nonconformant.append(topic)
            errors.append(
                f"topic '{topic}' no conforme al corpus-spec: falta sources/ y/o appraisals/"
            )
            continue

        source_files = sorted(f for f in os.listdir(sources_dir) if f.endswith(".md"))
        # A topic with its shape but no sources is an unpopulated topic. It has
        # no evidence to pair or grade, so it is deliberately not "verified".
        if not source_files:
            skipped_empty.append(topic)
            continue

        # First pass: collect all ingestors before inspecting any appraisal.
        # This avoids order-dependent false negatives.
        ingestors = set()
        for filename in source_files:
            fm = parse_frontmatter(os.path.join(sources_dir, filename))
            if fm.get("ingested_by"):
                ingestors.add(fm["ingested_by"])

        # Second pass: enforce one appraisal per source and independent authorship.
        for filename in source_files:
            app = os.path.join(appraisals_dir, filename)
            if not os.path.isfile(app):
                errors.append(f"{topic}/appraisals/{filename} missing for {topic}/sources/{filename}")
                continue
            afm = parse_frontmatter(app)
            appraised_by = afm.get("appraised_by", "")
            if appraised_by == captain or appraised_by in ingestors:
                errors.append(
                    f"{topic}/appraisals/{filename} appraised_by '{appraised_by}' (captain or ingestor)"
                )
        verified.append(topic)

    detail = (
        f"verified topics: {', '.join(verified) if verified else '(none)'}; "
        f"skipped empty topics: {', '.join(skipped_empty) if skipped_empty else '(none)'}; "
        f"nonconformant topics: {', '.join(nonconformant) if nonconformant else '(none)'}"
    )
    if errors:
        return False, detail + "; " + "; ".join(errors)
    return True, detail


def compute_required_nesting(ship, captain, crew):
    """Compute expected max-nesting values for ship agents.

    For now the manifest only supports a flat captain+crew tree.
    Captain is at depth 1 from Neo; crew are depth 2.  A captain that can
    spawn depth-2 children needs max-nesting: 2.  Leaves need no field.
    """
    # global depth from Neo
    depths = {captain: 1}
    for member in crew:
        depths[member] = 2

    # children map (flat)
    children = {captain: list(crew)}

    def deepest_descendant(node):
        d = 0
        for c in children.get(node, []):
            d = max(d, 1 + deepest_descendant(c))
        return d

    expected = {}
    for node in depths:
        sub = deepest_descendant(node)
        if sub > 0:
            # max-nesting value = depth of deepest descendant from root
            expected[node] = depths[node] + sub
    return expected


def declared_targets(root):
    adapters_dir = os.path.join(root, "adapters")
    out = []
    for name in sorted(os.listdir(adapters_dir)):
        if os.path.isfile(os.path.join(adapters_dir, name, "adapter.yaml")):
            out.append(name)
    return out


def _load_yaml(path):
    try:
        import yaml
        with open(path, encoding="utf-8") as fh:
            return yaml.safe_load(fh) or {}
    except Exception:
        return {}


def _artifact_dirs_for_target(root, target):
    adapter_yaml = os.path.join(root, "adapters", target, "adapter.yaml")
    if not os.path.isfile(adapter_yaml):
        return None, None
    cfg = _load_yaml(adapter_yaml)
    if not isinstance(cfg, dict):
        return None, None
    artifacts = cfg.get("artifacts", {})
    if not isinstance(artifacts, dict):
        return None, None
    generated = artifacts.get("generated_agents_dir")
    installed = artifacts.get("installed_agents_dir")
    if not generated or not installed:
        return None, None

    def resolve(raw):
        raw = raw.replace("{target}", target)
        raw = os.path.expanduser(raw)
        if os.path.isabs(raw):
            return raw
        return os.path.join(root, raw)

    return resolve(generated), resolve(installed)


def max_nesting_check(root, ship, captain, crew, expected, target=None):
    """Check generated and installed artifacts for the right max-nesting field."""
    agent_stems = {captain: f"{ship}-{captain}"}
    for member in crew:
        agent_stems[member] = f"{ship}-{member}"

    def _check_one_target(target_name):
        generated_dir, installed_dir = _artifact_dirs_for_target(root, target_name)
        if generated_dir is None or installed_dir is None:
            return (
                False,
                f"target '{target_name}' has no adapters/{target_name}/adapter.yaml (or it declares no `artifacts` block) — cannot resolve artifact paths; not implemented yet for '{target_name}'",
            )

        candidates = [generated_dir, installed_dir]
        found_any = False
        errors = []
        notes = []

        for member, stem in agent_stems.items():
            exp = expected.get(member)
            artifacts = []
            for base in candidates:
                path = os.path.join(base, stem, "AGENT.md")
                if os.path.isfile(path):
                    with open(path, encoding="utf-8") as fh:
                        artifacts.append((path, fh.read()))
                    found_any = True

            for path, body in artifacts:
                has_field = re.search(r"^max-nesting:\s*(\d+)", body, re.MULTILINE)
                if exp:
                    if not has_field:
                        errors.append(f"{path} missing max-nesting:{exp}")
                    elif int(has_field.group(1)) != exp:
                        errors.append(f"{path} has max-nesting {has_field.group(1)}, expected {exp}")
                    else:
                        notes.append(f"{path} max-nesting:{exp} ok")
                else:
                    if has_field:
                        errors.append(f"{path} should not have max-nesting (leaf agent)")
                    else:
                        notes.append(f"{path} has no max-nesting (ok for leaf)")

            if len(artifacts) > 1:
                path_a, body_a = artifacts[0]
                path_b, body_b = artifacts[1]
                if body_a != body_b:
                    errors.append(f"artifacts diverge: {path_a} != {path_b}")

        if not found_any:
            return (
                True,
                f"target '{target_name}': neither {generated_dir} nor {installed_dir} contain '<ship>-<agent>/AGENT.md' yet (pre-build state); re-run after build+install",
            )
        if errors:
            return False, "; ".join(errors) + "; re-run bin/matrix install --target=devin"
        return True, "; ".join(notes) if notes else "max-nesting fields correct"

    if target:
        return _check_one_target(target)

    targets = declared_targets(root)
    results = [_check_one_target(t) for t in targets]
    ok = all(r[0] for r in results)
    detail = "; ".join(r[1] for r in results)
    return ok, detail


def validate_ship(root, ship_dir, target=None):
    """Run all checks for one ship directory and return a report dict."""
    agents_md = os.path.join(ship_dir, "AGENTS.md")
    manifest = parse_frontmatter(agents_md)
    ship = manifest.get("ship", os.path.basename(ship_dir))
    checks = []
    errors = []

    def check(label, ok, detail="", heuristic=False):
        item = {"ship": ship, "check": label, "ok": bool(ok), "detail": detail if detail else ""}
        if heuristic:
            item["heuristic"] = True
        checks.append(item)
        if not ok:
            errors.append(label + (f": {detail}" if detail else ""))

    # 1. manifest parses and has required keys
    missing_keys = REQUIRED_MANIFEST_KEYS - set(manifest.keys())
    check("manifest_parses", not missing_keys,
          f"missing keys: {', '.join(sorted(missing_keys))}" if missing_keys else "")

    captain = manifest.get("captain", "")
    crew = manifest.get("crew", [])
    if isinstance(crew, str):
        crew = parse_scalar_list(crew)
    state_path = manifest.get("state", "")

    # 2. captain present
    captain_path = os.path.join(ship_dir, "agents", f"{captain}.md")
    if captain:
        fm, err = read_agent_check(captain_path)
        ok = not err and bool(fm)
        if ok and fm.get("name") != captain:
            ok = False
            err = f"frontmatter name '{fm.get('name')}' != captain '{captain}'"
        check("captain_present", ok, err)
    else:
        check("captain_present", False, "no captain in manifest")

    # 3. crew present
    crew_errors = []
    for member in crew:
        p = os.path.join(ship_dir, "agents", f"{member}.md")
        fm, err = read_agent_check(p)
        ok = not err and bool(fm)
        if ok and fm.get("name") != member:
            ok = False
            err = f"frontmatter name '{fm.get('name')}' != '{member}'"
        if not ok:
            crew_errors.append(f"{member}: {err}")
    check("crew_present", not crew_errors, "; ".join(crew_errors))

    # 4. roster discipline
    try:
        crew_max = int(manifest.get("crew-max", 0))
    except ValueError:
        crew_max = 0
    roster_ok = len(crew) + 1 <= crew_max
    roster_detail = f"{len(crew) + 1} members <= crew-max {crew_max}" if roster_ok else f"{len(crew) + 1} members > crew-max {crew_max}"
    check("roster_discipline", roster_ok, roster_detail)

    # 5. no_core_state
    if state_path:
        ns_errors = no_core_state_check(root, ship_dir, state_path)
        check("no_core_state", not ns_errors, "; ".join(ns_errors), heuristic=True)
    else:
        check("no_core_state", False, "manifest has no state path")

    # 6. state_gitignored
    if state_path:
        sg_ok = state_gitignored(root, state_path)
        sg_detail = f"{state_path} is gitignored" if sg_ok else f"{state_path} is not matched by a positive .gitignore rule"
        check("state_gitignored", sg_ok, sg_detail)
    else:
        check("state_gitignored", False, "manifest has no state path")

    # 7. corpus_shape
    if state_path and captain:
        ok, detail = corpus_shape(root, state_path, captain)
        check("corpus_shape", ok, detail)
    else:
        check("corpus_shape", False, "cannot check corpus without state path and captain")

    # 8. max_nesting
    if captain and crew:
        expected = compute_required_nesting(ship, captain, crew)
        ok, detail = max_nesting_check(root, ship, captain, crew, expected, target=target)
        check("max_nesting", ok, detail)
    else:
        check("max_nesting", False, "cannot compute max-nesting without captain and crew")

    return {
        "ship": ship,
        "ok": not errors,
        "checks": checks,
        "errors": errors,
    }


def validate(data):
    root = resolve_root()
    requested = data.get("ship", "")
    target = data.get("target") or None
    reports = []
    any_errors = []

    for ship_name, ship_dir in find_manifests(root):
        if requested and requested != "*" and ship_name != requested:
            continue
        r = validate_ship(root, ship_dir, target=target)
        reports.append(r)
        if not r["ok"]:
            any_errors.extend([f"{ship_name}: {e}" for e in r["errors"]])

    if requested and requested != "*" and not reports:
        return {
            "hook": "validate_ship",
            "ok": False,
            "ship": requested,
            "errors": [f"ship '{requested}' not found"],
            "checks": [],
        }

    return {
        "hook": "validate_ship",
        "ok": not any_errors,
        "ship": requested,
        "ships": [r["ship"] for r in reports],
        "checks": [check for report in reports for check in report["checks"]],
        "errors": any_errors,
    }


def main():
    data = read_input()
    result = validate(data)
    emit(result)


if __name__ == "__main__":
    main()
