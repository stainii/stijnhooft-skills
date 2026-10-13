"""A throwaway git repo per test, and the two scripts run as the agent runs them."""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[2] / "skills" / "session-guide" / "scripts"


class GitSandbox:
    def __init__(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.email", "t@example.com")
        self.git("config", "user.name", "t")
        self.git("config", "commit.gpgsign", "false")

    def close(self):
        self._tmp.cleanup()

    def git(self, *args):
        return subprocess.run(["git", *args], cwd=self.root, check=True,
                              capture_output=True, text=True).stdout.strip()

    def write(self, path, text):
        p = self.root / path
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)

    def move(self, old, new):
        (self.root / new).parent.mkdir(parents=True, exist_ok=True)
        self.git("mv", old, new)

    def delete(self, path):
        (self.root / path).unlink()

    def commit(self, msg="c"):
        self.git("add", "-A")
        self.git("commit", "-q", "-m", msg)
        return self.git("rev-parse", "HEAD")

    def run(self, script, *args):
        return subprocess.run([sys.executable, str(SCRIPTS / script), *args], cwd=self.root,
                              capture_output=True, text=True)

    def gather(self, *args, guide="guides/g"):
        r = self.run("gather.py", str(self.root / guide), *args)
        assert r.returncode == 0, r.stderr
        return json.loads((self.root / guide / "facts.json").read_text())

    def write_guide(self, data, guide="guides/g"):
        self.write(f"{guide}/guide.json", json.dumps(data))

    def write_part(self, name, data, guide="guides/g"):
        self.write(f"{guide}/parts/{name}.json", json.dumps(data))

    def build(self, guide="guides/g"):
        return self.run("build.py", str(self.root / guide))


def lines(n, prefix="line"):
    return "".join(f"{prefix} {i}\n" for i in range(1, n + 1))


def by_path(facts):
    return {f["path"]: f for f in facts["files"]}
