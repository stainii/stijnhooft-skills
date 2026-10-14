#!/usr/bin/env python3
"""Check a guide, merge its parts, and render <guide-dir>.html and <guide-dir>.mr.md.

usage: build.py <guide-dir> [--part parts/job-<N>.json]
Prints "ok <path>" or one problem per line, and exits 1 when there are problems.
With --part it renders nothing and prints only the problems of that part and its job's files, so a subagent can
check its part before guide.json is complete.
"""
import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gather  # noqa: E402
from guide import REQUIRED, file_view, load, matches, origin, panel_ids, panel_links, refs  # noqa: E402
from source import Source  # noqa: E402
from views import change_map, file_tree, lineage, mr_text, read_lines, size  # noqa: E402

TEMPLATE = Path(__file__).resolve().parent.parent / "template.html"
DATA_SLOT = "/*GUIDE_DATA*/"


def resolve(guide, source, large):
    """Follow every reference into the code: (problems, hunks to show, code to show at the base and now)."""
    problems, hunks, code = [], {}, {"base": {}, "now": {}}
    for r in refs(guide):
        if not r.span:
            problems.append(f"{r.where}: {r.text!r} needs line numbers: path:line or path:from-to")
            continue
        if r.kind == "hunk":
            lines, problem = source.hunk(r.span)
            # a large guide shows hunks only where a decision, a contract or a card is argued
            if lines and not (large and r.in_stop):
                hunks[r.text] = lines
        else:
            at_base = r.kind == "base"
            problem = source.place_problem(r.span, at_base)
            if not problem and r.kind in code:
                code[r.kind][r.text] = r.span.lines_of(source.text(r.span.path, at_base))
        if problem:
            problems.append(f"{r.where}: {problem}")
    return problems, hunks, code


def check(guide, view):
    """Every problem in what the guide claims about the change as a whole."""
    problems = []
    read_order = [r.get("files", []) for r in guide.get("readOrder", [])]
    for path, v in view.items():
        if not v["panel"] and not v["group"]:
            problems.append(f"{path}: changed, but no stop, decision, contract, card or group explains it")
        if v["tier"] == "read" and not any(matches(patterns, path) for patterns in read_order):
            problems.append(f"{path}: read tier, but not in readOrder")
    for d in guide.get("decisions", []):
        if not d.get("hunks"):
            problems.append(f"decision {d.get('id')}{origin(d)}: no hunks")
    rf = guide.get("refactoring")
    if rf is not None:
        succeeded = {path for link in rf.get("links", []) for path in link.get("from", [])}
        for path, v in view.items():
            if v["status"] == "D" and path not in succeeded and path not in rf.get("gone", {}):
                problems.append(f"{path}: deleted with no successor; link it, or say why in refactoring.gone")
    ids = panel_ids(guide)
    for where, target in panel_links(guide):
        if target not in ids:
            problems.append(f"{where}: links to #{target}, which is not a panel")
    return problems


def render(data):
    blob = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    return TEMPLATE.read_text(encoding="utf-8").replace(DATA_SLOT, blob)


def part_problems(problems, part, facts):
    """The problems a subagent can fix: those naming its part, or a file of its job."""
    m = re.fullmatch(r"job-(\d+)\.json", part.name)
    jobs = facts["jobs"]
    modules = set(jobs[int(m.group(1)) - 1]["modules"]) if m and 0 < int(m.group(1)) <= len(jobs) else set()
    paths = {f["path"] for f in facts["files"] if f["module"] in modules}
    tag = f"(parts/{part.name})"
    return [p for p in problems if tag in p or p.split(": ", 1)[0] in paths]


def build(guide_dir, root, saved, env, part=None):
    facts = gather.collect(saved["base"], root, env)
    guide = load(guide_dir)
    missing = [k for k in REQUIRED if k not in guide]
    if missing and not part:
        return [f"guide.json: missing {', '.join(missing)} (see guide.schema.ts)"]
    problems, hunks, code = resolve(guide, Source(root, saved["base"], facts, env), facts["large"])
    view = file_view(guide, facts)
    problems += check(guide, view)
    if part:
        return part_problems(problems, part, facts)
    if problems:
        return problems
    for m in guide.get("split") or []:
        m["read"] = read_lines(view, m.get("files", []))
    sz = size(guide, view)
    mr = mr_text(guide, sz)
    guide_dir.with_suffix(".mr.md").write_text(mr, encoding="utf-8")
    guide_dir.with_suffix(".html").write_text(render({
        **guide, "hunks": hunks, "code": code, "mrText": mr, "large": facts["large"], "size": sz,
        "map": change_map(view, facts["large"]), "tree": file_tree(view, facts["large"]),
        "lineage": lineage(guide, view, facts), "since": saved.get("since")}), encoding="utf-8")
    return []


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("guide_dir")
    ap.add_argument("--part", help="check only this part (parts/job-<N>.json) and its job's files; render nothing")
    args = ap.parse_args(argv)
    guide_dir = Path(args.guide_dir).resolve()
    part = Path(args.part) if args.part else None
    if part and not (guide_dir / "parts" / part.name).is_file():
        sys.exit(f"build.py: no part {guide_dir / 'parts' / part.name}")
    root = Path(gather.git("rev-parse", "--show-toplevel", cwd=guide_dir.parent).strip())
    saved = json.loads((guide_dir / "facts.json").read_text(encoding="utf-8"))
    with gather.snapshot(root, gather.guides_folder(guide_dir, root)) as env:
        problems = build(guide_dir, root, saved, env, part)
    sys.stdout.reconfigure(encoding="utf-8")
    if problems:
        print("\n".join(problems))
        return 1
    print(f"ok {guide_dir / 'parts' / part.name}" if part else f"ok {guide_dir.with_suffix('.html')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
