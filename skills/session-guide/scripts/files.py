#!/usr/bin/env python3
"""List changed files from <guide-dir>/facts.json, one per line: tier, status, +added -deleted, path.

usage: files.py <guide-dir> [--job N] [--tier read|skim|skip]
"""
import argparse
import json
import sys
from pathlib import Path


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("guide_dir")
    ap.add_argument("--job", type=int, help="only the files of this job (numbered as gather.py prints them)")
    ap.add_argument("--tier", choices=["read", "skim", "skip"])
    args = ap.parse_args(argv)
    facts = json.loads((Path(args.guide_dir) / "facts.json").read_text(encoding="utf-8"))
    modules = set(facts["jobs"][args.job - 1]["modules"]) if args.job else None
    sys.stdout.reconfigure(encoding="utf-8")
    for f in facts["files"]:
        if (modules is None or f["module"] in modules) and (not args.tier or f["tier"] == args.tier):
            print(f"{f['tier']} {f['status']} +{f['add']} -{f['del']} {f['path']}")


if __name__ == "__main__":
    sys.exit(main())
