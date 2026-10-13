"""What the page and the merge request show, derived from the file view: sizes, the change map, the file tree,
the lineage, and the MR text."""
import re
from collections import Counter

from gather import churn
from guide import matches

LAYER_ORDER = ["UI", "API", "Service", "Domain", "Persistence", "Migration", "Config", "Other", "Tests", "Docs"]
SEVERITY = {"high": 0, "med": 1, "low": 2, "ok": 3}


def size(guide, view):
    """Lines per tier, after the guide's overrides, against the budget."""
    out = {"read": 0, "skim": 0, "skip": 0, "budget": guide.get("budget", 400)}
    for v in view.values():
        out[v["tier"]] += churn(v)
    return out


def read_lines(view, patterns):
    return sum(churn(v) for path, v in view.items() if v["tier"] == "read" and matches(patterns, path))


def most_common(values):
    values = [v for v in values if v]
    return Counter(values).most_common(1)[0][0] if values else None


def change_map(view, large):
    """Layers of chips: one per file, one per group, and in large mode one per directory."""
    bins = {}
    for path, v in view.items():
        if v["group"]:
            key = ("group", v["group"])
        elif large and not v["review"]:
            key = ("dir", path.rsplit("/", 1)[0] + "/" if "/" in path else "./")
        else:
            key = ("file", path)
        bins.setdefault(key, []).append(v)
    layers = {}
    for (kind, name), files in bins.items():
        statuses = {v["status"] for v in files}
        chip = {"label": name.rsplit("/", 1)[-1] if kind == "file" else name, "files": len(files),
                "add": sum(v["add"] for v in files), "del": sum(v["del"] for v in files),
                "panel": most_common(v["panel"] for v in files), "review": any(v["review"] for v in files),
                "status": statuses.pop() if len(statuses) == 1 else "M"}
        if kind == "file":
            chip["path"] = name
        layers.setdefault(most_common(v["layer"] for v in files), []).append(chip)
    order = {name: i for i, name in enumerate(LAYER_ORDER)}
    return [{"layer": name, "chips": sorted(chips, key=lambda c: -churn(c))}
            for name, chips in sorted(layers.items(), key=lambda kv: order.get(kv[0], len(order)))]


def file_tree(view, large):
    """Every changed file as a tree, marked + added, - deleted; one line per directory in large mode."""
    dirs = {}
    for path, v in sorted(view.items()):
        d, _, name = path.rpartition("/")
        dirs.setdefault(d or ".", []).append((name, v))
    out = []
    for d, files in dirs.items():
        if large:
            statuses = {v["status"] for _, v in files}
            mark = "+" if statuses == {"A"} else "-" if statuses == {"D"} else " "
            add, dele = sum(v["add"] for _, v in files), sum(v["del"] for _, v in files)
            out.append(f"{mark} {d}/  {len(files)} files  +{add} -{dele}")
            continue
        out.append(f"  {d}/")
        for name, v in files:
            mark = {"A": "+", "D": "-"}.get(v["status"], " ")
            was = f"  (was {v['old_path']})" if v.get("old_path") else ""
            out.append(f"{mark}   {name}{was}")
    return "\n".join(out)


def lineage(guide, view, facts):
    """One map per job: old files left, new right, git's renames plus the links the session states."""
    rf = guide.get("refactoring")
    if not rf:
        return []
    gone = rf.get("gone", {})
    links = [{"from": [v["old_path"]], "to": [path], "kind": "renamed", "sim": v["sim"], "by": "git"}
             for path, v in view.items() if v["status"] == "R"]
    links += [{"from": l["from"], "to": l["to"], "kind": l["kind"], "by": "agent",
               **({"note": l["note"]} if l.get("note") else {})} for l in rf.get("links", [])]
    module = {v["path"]: v["module"] for v in view.values()}
    module.update({v["old_path"]: v["module"] for v in view.values() if v.get("old_path")})
    job_of = {m: i for i, job in enumerate(facts["jobs"]) for m in job["modules"]}
    maps = {}

    def node(path, new=False):
        """A file on the map; a new file links to the panel that explains it."""
        d, _, name = path.rpartition("/")
        n = {"id": path, "name": name, "dir": d}
        v = view.get(path, {}) if new else {}
        if v.get("panel"):
            n["panel"] = v["panel"]
        if v.get("review"):
            n["review"] = True
        if path in gone:
            n["note"] = gone[path]
        return n

    def map_of(path):
        return maps.setdefault(job_of.get(module.get(path), -1), {"old": {}, "new": {}, "links": []})

    for path, v in view.items():
        if v["status"] in ("D", "R"):
            old = v.get("old_path") or path
            map_of(old)["old"][old] = node(old)
        if v["status"] in ("A", "R"):
            map_of(path)["new"][path] = node(path, new=True)
    for link in links:
        m = map_of((link["to"] or link["from"])[0])
        m["links"].append(link)
        for path in link["from"]:
            m["old"].setdefault(path, node(path))
        for path in link["to"]:
            m["new"].setdefault(path, node(path, new=True))
    titles = {i: ", ".join(job["modules"]) for i, job in enumerate(facts["jobs"])}
    return [{"title": titles.get(k, "other"), "old": list(m["old"].values()), "new": list(m["new"].values()),
             "links": m["links"]} for k, m in sorted(maps.items())]


def plain(text):
    """Text for Markdown: panel links become their label; the page's other markup is Markdown already."""
    return re.sub(r"\[([^\]]*)\]\(#[\w-]+\)", r"\1", text or "")


def mr_text(guide, sz):
    """The merge request description: what colleagues see, condensed from the guide."""
    call, ev, danger = guide["ship"], guide.get("evidence", {}), guide["danger"]
    out = [f"# {guide['title']}", "", plain(guide["mr"]["summary"]), ""]
    if guide["mr"].get("mermaid"):
        out += ["```mermaid", guide["mr"]["mermaid"], "```", ""]
    out += [f"**{call['call'].capitalize()}**: {plain(call['why'])} · Review size: {sz['read']} lines to read, "
            f"{sz['skim']} to skim, {sz['skip']} to skip (budget {sz['budget']}).", "", "## Read in this order", ""]
    out += [f"{i}. {', '.join(f'`{f}`' for f in r['files'])} *{r['tier']}*: {plain(r['why'])}"
            for i, r in enumerate(guide.get("readOrder", []), 1)]
    if guide.get("split"):
        out += ["", "## Split plan", ""]
        for i, m in enumerate(guide["split"], 1):
            alone = f" Merges with: {plain(m['alone'])}." if m.get("alone") else ""
            out.append(f"{i}. **{m['title']}** ({m['kind']}, {m['call'].capitalize()}, ~{m['read']} lines to read): "
                       f"{'; '.join(plain(x) for x in m.get('items', []))}.{alone}")
    out += ["", "## Evidence", ""]
    for label in ("before", "after"):
        if ev.get(label):
            out += [f"{label.capitalize()}:", "", "```", ev[label], "```", ""]
    if ev.get("test"):
        out += [f"Pinned by `{ev['test']}`.", ""]
    out += [f"Not covered: {plain(ev.get('notCovered'))}", "", "## Merge danger", "",
            f"**{danger['door']} door**: {plain(danger['why'])} Blast radius: {plain(danger['blast'])}", "",
            "## Review focus", ""]
    cards = sorted((c for c in guide.get("review", []) if c.get("sev") != "ok"), key=lambda c: SEVERITY.get(c["sev"], 9))
    out += [f"- [ ] {c['claim']}" for c in cards] or ["Nothing open."]
    return "\n".join(out) + "\n"
