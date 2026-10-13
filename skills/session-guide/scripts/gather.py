#!/usr/bin/env python3
"""Collect the mechanical facts of a change set into <guide-dir>/facts.json.

usage: gather.py <guide-dir> (--base <rev> | --ticket) [--reviewed <sha>]
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path


def git(*args, cwd=".", env=None):
    return subprocess.run(["git", *args], cwd=cwd, env=env, check=True, capture_output=True, text=True).stdout


def git_succeeds(*args, cwd="."):
    """Whether a git command exits 0: for questions such as "does this commit exist?"."""
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True).returncode == 0


def churn(f):
    """Lines changed in a file (or anything else carrying add and del counts)."""
    return f["add"] + f["del"]


@contextmanager
def snapshot(root, exclude=None):
    """An env for git with a throwaway copy of the index that also holds the untracked files (intent-to-add),
    so a move nobody staged still reads as a rename, and the real index stays as it was."""
    tmp = tempfile.mkdtemp(prefix="session-guide-")
    index = Path(tmp) / "index"
    real = Path(root) / git("rev-parse", "--git-path", "index", cwd=root).strip()
    if real.is_file():
        shutil.copy2(real, index)  # keep its mtime, or git trusts stat data it should re-check (racy git)
    env = {**os.environ, "GIT_INDEX_FILE": str(index)}
    try:
        untracked = [p for p in git("ls-files", "--others", "--exclude-standard", "-z", cwd=root).split("\0")
                     if p and not (exclude and (p + "/").startswith(exclude + "/"))]
        for i in range(0, len(untracked), 500):
            git("add", "--intent-to-add", "--", *untracked[i:i + 500], cwd=root, env=env)
        yield env
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# First guesses only; the agent overrides any of them in guide.json.
GENERATED = re.compile(r"(^|/)(generated|gen|dist|build|target|vendor|node_modules|__snapshots__)/"
                       r"|\.(min\.js|map|snap|lock)$|(^|/)(package-lock\.json|pnpm-lock\.yaml|go\.sum)$")
TEST = re.compile(r"(^|/)(tests?|__tests__|spec|testdata|fixtures?)/|(Test|Tests|IT|Spec)\.\w+$"
                  r"|[._-](test|spec)\.\w+$|(^|/)test_[^/]+$|_test\.\w+$")
SKIM = re.compile(r"\.(md|adoc|rst|txt|ya?ml|json|toml|properties|ini|xml|gradle|cfg|conf)$"
                  r"|(^|/)docs?/|(Dto|DTO|Request|Response)\.\w+$")


def tier(f):
    """read (logic), skim (tests, DTOs, config, docs), skip (generated, deleted, moved unchanged)."""
    p = f["path"]
    if f["status"] == "D" or f.get("binary") or GENERATED.search(p) \
            or (f["status"] in "RC" and f["add"] == f["del"] == 0):
        return "skip"
    if TEST.search(p) or SKIM.search(p):
        return "skim"
    return "read"


LAYERS = [  # first match wins
    ("Tests", TEST),
    ("Docs", re.compile(r"(^|/)docs?/|\.(md|adoc|rst)$")),
    ("Migration", re.compile(r"(^|/)(migrations?|flyway|liquibase|changelog)/|\.sql$")),
    ("UI", re.compile(r"(^|/)(ui|frontend|components|pages|views|templates|static)/|\.(tsx|jsx|vue|svelte|css|scss|html)$")),
    ("API", re.compile(r"(^|/)(api|rest|controllers?|resources?|endpoints?|routes|graphql|web|dto|mappers?)/"
                       r"|(Controller|Resource|Endpoint|Dto|DTO|Mapper)\.\w+$")),
    ("Service", re.compile(r"(^|/)(services?|application|usecases?|scheduler|eventlisteners?|handlers?)/|(Service|Handler)\.\w+$")),
    ("Persistence", re.compile(r"(^|/)(persistence|repository|repositories|dao|db|store|infra|infrastructure)/|(Repository|Dao|Entity)\.\w+$")),
    ("Domain", re.compile(r"(^|/)(domain|model|core|entities)/")),
    ("Config", re.compile(r"\.(ya?ml|toml|properties|ini|gradle|cfg|conf)$|(^|/)(pom\.xml|package\.json|Dockerfile)$")),
]


def layer(path):
    return next((name for name, rx in LAYERS if rx.search(path)), "Other")


# Source roots say nothing about the module: src/main/java/be/x/order and src/test/java/be/x/order are one.
SOURCE_ROOT = re.compile(r"(^|/)(src/)?(main|test|it|integrationTest)/(java|kotlin|scala|groovy|resources)/|(^|/)(src|lib|app|tests?)/")
JOB_LINES = 1500  # read lines: about what one subagent takes in


def read_lines(f):
    return churn(f) if f["tier"] == "read" else 0


def modules(files):
    """path -> module: the first directory below the common prefix, split deeper while it has too many read lines."""
    dirs = {f["path"]: [d for d in SOURCE_ROOT.sub("/", "/" + f["path"]).strip("/").split("/")[:-1] if d] for f in files}
    size = {f["path"]: read_lines(f) for f in files}
    result = {}

    def assign(group, depth, prefix):
        while len({tuple(dirs[p][:depth + 1]) for p in group}) == 1 and all(len(dirs[p]) > depth + 1 for p in group):
            depth += 1  # skip directories every file shares
        buckets = {}
        for p in group:
            buckets.setdefault(dirs[p][depth] if len(dirs[p]) > depth else None, []).append(p)
        for name, members in buckets.items():
            if name is None:
                result.update((p, prefix.rstrip("/") or "(root)") for p in members)
            elif sum(size[p] for p in members) > JOB_LINES and any(len(dirs[p]) > depth + 1 for p in members):
                assign(members, depth + 1, prefix + name + "/")
            else:
                result.update((p, prefix + name) for p in members)

    assign(list(dirs), 0, "")
    return result


def jobs(files):
    """Neighbouring modules with read lines, packed into one subagent's worth each."""
    per = {}
    for f in files:
        per[f["module"]] = per.get(f["module"], 0) + read_lines(f)
    packed = []
    for name in sorted(m for m, n in per.items() if n):
        if packed and packed[-1]["read"] + per[name] <= JOB_LINES:
            packed[-1]["modules"].append(name)
            packed[-1]["read"] += per[name]
        else:
            packed.append({"modules": [name], "read": per[name]})
    return packed


def changed_files(base, cwd, env):
    """Every file that differs between <base> and the working tree, as the snapshot index sees it."""
    counts = dict(_numstat(base, cwd, env))
    files = []
    for st, old, path in _name_status(base, cwd, env):
        add, dele = counts.get(path) or (0, 0)
        f = {"path": path, "status": st[0], "add": add, "del": dele}
        if old:
            f["old_path"], f["sim"] = old, int(st[1:])
        if path in counts and counts[path] is None:
            f["binary"] = True
        files.append(f)
    return files


def _numstat(base, cwd, env):
    """(path, (added, deleted)); a rename comes as "a\td\t" followed by old and new path."""
    out = git("diff", "--numstat", "-z", "-M", "-C", base, cwd=cwd, env=env).split("\0")
    i = 0
    while i < len(out) - 1:
        add, dele, path = out[i].split("\t")
        i += 1
        if not path:
            path, i = out[i + 1], i + 2
        yield path, None if add == "-" else (int(add), int(dele))


def _name_status(base, cwd, env):
    """(status, old path or None, path); R and C carry a similarity and two paths."""
    out = git("diff", "--name-status", "-z", "-M", "-C", base, cwd=cwd, env=env).split("\0")
    i = 0
    while i < len(out) - 1:
        st = out[i]
        if st[0] in "RC":
            yield st, out[i + 1], out[i + 2]
            i += 3
        else:
            yield st, None, out[i + 1]
            i += 2


RANGE_DIFF = re.compile(r"^\s*(?:\d+|-):\s+(\w+|-+) ([=!<>]) \s*(?:\d+|-):\s+(\w+|-+) (.*)$")
RANGE_STATUS = {"=": "same", "!": "changed", "<": "dropped", ">": "added"}


def since(base, reviewed, root):
    """One row per commit between the reviewed version and HEAD, paired by content, so it survives a rebase."""
    if not git_succeeds("cat-file", "-e", reviewed + "^{commit}", cwd=root):
        return {"reviewed": reviewed, "unreachable": True, "rows": []}
    rows = []
    for line in git("range-diff", "--no-color", "-s", f"{base}..{reviewed}", f"{base}..HEAD", cwd=root).splitlines():
        m = RANGE_DIFF.match(line)
        if m:
            old, st, new, subject = m.groups()
            rows.append({"st": RANGE_STATUS[st], "sha": (new if st != "<" else old)[:12], "subject": subject})
    stat = [l.split("\t") for l in git("diff", "--numstat", reviewed, cwd=root).splitlines()]
    return {"reviewed": reviewed, "rows": rows, "lines": sum(int(a) + int(d) for a, d, _ in stat if a != "-")}


def default_branch(root):
    try:
        return git("symbolic-ref", "--short", "refs/remotes/origin/HEAD", cwd=root).strip()
    except subprocess.CalledProcessError:
        pass
    for name in ("main", "master", "develop"):
        if git_succeeds("rev-parse", "--verify", "-q", name, cwd=root):
            return name
    sys.exit("gather.py: no default branch found (origin/HEAD, main, master, develop); pass --base")


def guides_folder(guide_dir, root):
    """The folder holding every guide and its output, relative to the repo: never part of the change."""
    try:
        return Path(guide_dir).resolve().parent.relative_to(Path(root).resolve()).as_posix()
    except ValueError:
        return None


LARGE_FILES, LARGE_LINES = 50, 3000


def collect(base, root, env):
    """The facts a guide is built on; build.py calls this too, so the checks see the code as it is now."""
    files = changed_files(base, root, env)
    totals = {"files": len(files), "add": 0, "del": 0, "read": 0, "skim": 0, "skip": 0}
    for f in files:
        f["tier"], f["layer"] = tier(f), layer(f["path"])
    module = modules(files)
    for f in files:
        f["module"] = module[f["path"]]
        totals["add"] += f["add"]
        totals["del"] += f["del"]
        totals[f["tier"]] += churn(f)
    large = len(files) > LARGE_FILES or churn(totals) > LARGE_LINES
    return {"base": base, "files": files, "totals": totals, "large": large, "jobs": jobs(files)}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("guide_dir")
    scope = ap.add_mutually_exclusive_group(required=True)
    scope.add_argument("--base", help="session scope: the commit the session started from")
    scope.add_argument("--ticket", action="store_true", help="the branch since its merge-base with the default branch")
    ap.add_argument("--reviewed", help="the sha last marked reviewed: adds the since-last-review rows")
    args = ap.parse_args(argv)
    out = Path(args.guide_dir)
    root = Path(git("rev-parse", "--show-toplevel").strip())
    if args.ticket:
        args.base = git("merge-base", default_branch(root), "HEAD", cwd=root).strip()
    with snapshot(root, guides_folder(out, root)) as env:
        facts = collect(args.base, root, env)
    if args.reviewed:
        facts["since"] = since(args.base, args.reviewed, root)
    out.mkdir(parents=True, exist_ok=True)
    (out / "facts.json").write_text(json.dumps(facts, indent=1))
    print(summary(facts, out / "facts.json"))


def summary(facts, path):
    """What the agent needs to plan, in a few lines; the full list stays in facts.json."""
    t, files = facts["totals"], facts["files"]
    count = lambda st: sum(f["status"] == st for f in files)
    lines = [f"{path}",
             f"{t['files']} files, +{t['add']} -{t['del']} · read {t['read']} · skim {t['skim']} · skip {t['skip']}"
             + (" · LARGE" if facts["large"] else ""),
             f"added {count('A')} · deleted {count('D')} · renamed {count('R')} · copied {count('C')}",
             "jobs (one subagent each in large mode): " + " | ".join(
                 f"{i}: {j['read']} read lines in {', '.join(j['modules'])}" for i, j in enumerate(facts["jobs"], 1))]
    if not facts["large"]:
        lines += [f"read: {f['path']}" for f in files if f["tier"] == "read"]
    if "since" in facts:
        rows = facts["since"]["rows"]
        lines.append("since reviewed: " + ("unreachable" if facts["since"].get("unreachable") else ", ".join(
            f"{sum(r['st'] == st for r in rows)} {st}" for st in ("same", "changed", "added", "dropped"))))
    return "\n".join(lines)


if __name__ == "__main__":
    sys.exit(main())
