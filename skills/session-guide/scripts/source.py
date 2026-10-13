"""The code a guide points at, as git sees it: spans, diffs, and file text at the base and now."""
import re
import subprocess
from dataclasses import dataclass

from gather import git


@dataclass(frozen=True)
class Span:
    """A place in a file: "path:line" or "path:from-to"."""
    path: str
    start: int
    end: int

    PATTERN = re.compile(r"^(.+):(\d+)(?:-(\d+))?$")

    @classmethod
    def parse(cls, text):
        """The span the text names, or None when it is not one."""
        m = cls.PATTERN.match(text or "")
        if not m:
            return None
        start = int(m.group(2))
        return cls(m.group(1), start, int(m.group(3) or start))

    def lines_of(self, text):
        return text[self.start - 1:self.end]


HUNK_HEADER = re.compile(r"@@ -(\d+)(?:,\d+)? \+(\d+)")


def diff_lines(diff, deleted):
    """(mark, text, position) per line of a one-file diff: position is the new line number, or the old one for a
    deleted file. A removed line sits at the position of the line that follows it."""
    old = new = 0
    started = False
    for line in diff.splitlines():
        if line.startswith("@@"):
            m = HUNK_HEADER.match(line)
            old, new, started = int(m.group(1)), int(m.group(2)), True
            continue
        if not started or line.startswith("\\"):
            continue
        mark, text = line[:1], line[1:]
        if mark == "+":
            yield "+", text, new
            new += 1
        elif mark == "-":
            yield "-", text, old if deleted else new
            old += 1
        else:
            yield " ", text, old if deleted else new
            old += 1
            new += 1


class Source:
    """The change set: what changed (facts), the diff per file, and the file text at the base and now."""

    def __init__(self, root, base, facts, env):
        self.root, self.base, self.env = root, base, env
        self.changed = {f["path"]: f for f in facts["files"]}
        self._diffs = {}

    def diff(self, path):
        if path not in self._diffs:
            f = self.changed[path]
            paths = [f["old_path"], path] if f.get("old_path") else [path]
            out = git("diff", "-M", "-U100000", "--no-color", self.base, "--", *paths, cwd=self.root, env=self.env)
            self._diffs[path] = list(diff_lines(out, deleted=f["status"] == "D"))
        return self._diffs[path]

    def text(self, path, at_base=False):
        """The file's lines now (or at the base); None when it doesn't exist there."""
        if not at_base and (self.root / path).is_file():
            return (self.root / path).read_text(errors="replace").splitlines()
        try:
            return git("show", f"{self.base}:{path}", cwd=self.root).splitlines()
        except subprocess.CalledProcessError:
            return None

    def place_problem(self, span, at_base=False):
        """Why the span does not point inside an existing file, or None when it does."""
        text = self.text(span.path, at_base)
        where = " at the base" if at_base else ""
        if text is None:
            return f"{span.path} does not exist{where}"
        if span.start < 1 or span.end > len(text):
            return f"{span.path} has {len(text)} lines{where}, not {span.end}"
        return None

    def hunk(self, span):
        """(lines, problem): the diff lines whose position falls inside the span."""
        if span.path not in self.changed:
            return None, f"{span.path} is not changed in this scope"
        picked = [[mark, text] for mark, text, pos in self.diff(span.path) if span.start <= pos <= span.end]
        if not any(mark != " " for mark, _ in picked):
            return None, f"{span.path}:{span.start}-{span.end} holds no changed lines"
        return picked, None
