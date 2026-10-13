"""The guide as data: loading guide.json with its parts, and walking what it refers to."""
import json
import re

from source import Span

REQUIRED = ["title", "context", "ship", "evidence", "danger", "sessions", "contracts", "review", "flows", "decisions",
            "readOrder", "mr"]
FIXED_PANELS = {"overview", "contracts", "review", "readorder", "split", "since", "mr", "lineage", "transit", "behaviour"}
PANEL_LINK = re.compile(r"\]\(#([\w-]+)\)")


def load(guide_dir):
    """guide.json with every parts/*.json merged into it."""
    guide = json.loads((guide_dir / "guide.json").read_text())
    parts = guide_dir / "parts"
    for part in sorted(parts.glob("*.json")) if parts.is_dir() else []:
        guide = merge(tag(json.loads(part.read_text()), f"parts/{part.name}"), guide)
    return guide


def tag(node, origin_name):
    """Mark every object from a part with where it came from, so a problem names the file to fix."""
    if isinstance(node, dict):
        return {**{k: tag(v, origin_name) for k, v in node.items()}, "_from": origin_name}
    if isinstance(node, list):
        return [tag(v, origin_name) for v in node]
    return node


def origin(item):
    return f" ({item['_from']})" if isinstance(item, dict) and item.get("_from") else ""


def merge(part, guide):
    """Lists add up (guide.json first) and an item with a known id merges into it; objects merge; guide.json wins
    on a plain value."""
    if isinstance(part, dict) and isinstance(guide, dict):
        out = dict(part)
        for k, v in guide.items():
            out[k] = merge(part[k], v) if k in part else v
        return out
    if isinstance(part, list) and isinstance(guide, list):
        out = list(guide)
        index = {x["id"]: i for i, x in enumerate(out) if isinstance(x, dict) and "id" in x}
        for item in part:
            if isinstance(item, dict) and item.get("id") in index:
                i = index[item["id"]]
                out[i] = {**merge(item, out[i]), "_from": out[i].get("_from")}
            else:
                out.append(item)
        return out
    return guide


class Ref:
    """One reference the guide makes into the code.

    kind: hunk (a diff range), place (a line now), base / now (code shown as read at the base, or now).
    panel: the panel that explains the file it names. in_stop: part of a walkthrough stop, which a large guide
    shows without its hunk."""

    def __init__(self, kind, where, text, panel, owner, in_stop=False):
        self.kind, self.text, self.panel, self.in_stop = kind, text, panel, in_stop
        self.where = where + origin(owner)
        self.span = Span.parse(text)


def refs(guide):
    """Every reference into the code: the one walk over the guide's structure."""
    for flow in guide.get("flows", []):
        for st in flow.get("stops", []):
            where = f"stop {st.get('id')}"
            yield Ref("place", where, st.get("at"), st.get("id"), st, in_stop=True)
            if st.get("hunk"):
                yield Ref("hunk", where, st["hunk"], st.get("id"), st, in_stop=True)
    for d in guide.get("decisions", []):
        for h in d.get("hunks", []):
            yield Ref("hunk", f"decision {d.get('id')}", h.get("at"), d.get("id"), d)
    for c in guide.get("contracts", []):
        yield Ref("place", f"contract {c.get('at')}", c.get("at"), "contracts", c)
        if c.get("hunk"):
            yield Ref("hunk", f"contract {c.get('at')}", c["hunk"], "contracts", c)
    for c in guide.get("review", []):
        if c.get("hunk"):
            yield Ref("hunk", f"card {c.get('id')}", c["hunk"], "review", c)
    if guide.get("evidence", {}).get("test"):
        yield Ref("place", "evidence", guide["evidence"]["test"], None, guide["evidence"])
    for i, t in enumerate((guide.get("refactoring") or {}).get("transit", []), 1):
        yield Ref("base", f"transit {i}", t.get("from"), "transit", t)
        yield Ref("now", f"transit {i}", t.get("to"), "transit", t)


def panel_ids(guide):
    ids = set(FIXED_PANELS)
    ids.update(st.get("id") for flow in guide.get("flows", []) for st in flow.get("stops", []))
    ids.update(d.get("id") for d in guide.get("decisions", []))
    return ids


def panel_links(node, where=""):
    """(where, id) for every link to a panel: [label](#id) in text, and every panel / see field."""
    if isinstance(node, dict):
        for k, v in node.items():
            here = f"{where}.{k}" if where else k
            if k == "_from":
                continue
            if k == "panel" and isinstance(v, str):
                yield here, v
            elif k == "see" and isinstance(v, list):
                yield from ((here, x) for x in v)
            else:
                yield from panel_links(v, here)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from panel_links(v, f"{where}[{i}]")
    elif isinstance(node, str):
        yield from ((where, m) for m in PANEL_LINK.findall(node))


def glob(pattern):
    """A path glob as a regex: ** crosses directories, * and ? do not."""
    rx = re.escape(pattern).replace(r"\*\*/", "(?:.*/)?").replace(r"\*\*", ".*").replace(r"\*", "[^/]*")
    return re.compile(rx.replace(r"\?", "[^/]") + "$")


def matches(patterns, path):
    return any(glob(p).match(path) for p in patterns)


def explainers(guide):
    """path -> the panel that explains it: every reference that names the file, the lineage, and overrides."""
    out = {}
    for r in refs(guide):
        if r.panel and r.span:
            out.setdefault(r.span.path, r.panel)
    rf = guide.get("refactoring") or {}
    for link in rf.get("links", []):
        for path in link.get("from", []) + link.get("to", []):
            out.setdefault(path, "lineage")
    for path in rf.get("gone", {}):
        out.setdefault(path, "lineage")
    for path, o in (guide.get("files") or {}).items():
        if o.get("panel"):
            out[path] = o["panel"]
    return out


def file_view(guide, facts):
    """path -> the changed file after the guide's say: tier, layer, panel, group, review."""
    expl, groups, overrides = explainers(guide), guide.get("groups") or [], guide.get("files") or {}
    refactoring = guide.get("refactoring") is not None
    view = {}
    for f in facts["files"]:
        path = f["path"]
        group = next((g for g in groups if matches(g.get("match", []), path)), {})
        o = overrides.get(path, {})
        renamed_in_refactoring = refactoring and f["status"] == "R"
        view[path] = {**f,
                      "tier": o.get("tier") or group.get("tier") or f["tier"],
                      "layer": o.get("layer") or group.get("layer") or f["layer"],
                      "review": bool(o.get("review")),
                      "panel": expl.get(path) or expl.get(f.get("old_path")) or group.get("panel")
                      or ("lineage" if renamed_in_refactoring else None),
                      "group": group.get("name")}
    return view
