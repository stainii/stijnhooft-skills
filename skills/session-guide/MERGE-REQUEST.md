# Merge request

Two arguments, both on the current branch's guide in `.claude/session-guides/`. Write or update the
guide first (`ticket` scope) if it is missing or older than the branch head.

## `mr` — the description reviewers read

The guide is for the author; the merge request is what colleagues see. `build.py` already writes it
next to the page, as `<name>.mr.md`, from the guide's data: summary, Ship / Show / Ask and review
size, the reading order, evidence, merge danger, and the open review cards as checkboxes.

Your part is `mr` in `guide.json`: a `summary` of two or three sentences in the repo's own terms,
and one `mermaid` diagram (the lineage for a refactoring, the call-tree diff or a state diagram
otherwise). Run `build.py` and give the user the path.

Creating or editing the merge request on the server (`glab mr create`, `gh pr create`) publishes
it: do that only when the user asks, for this MR.

Done when `build.py` prints `ok` and every claim in the summary is proved somewhere in the guide.

## `reviewed` — mark what the reviewers saw

Append the branch head to `.claude/session-guides/<branch>.reviewed` as
`<ISO date> <full sha> v<n>`. Nothing is pushed; the file is local.

From then on, every guide for this branch is gathered with `--reviewed <last sha>`. `gather.py`
pairs the commits with `git range-diff`, so the *Since last review* panel survives a rebase or
squash: each commit unchanged, changed, added or dropped, and the lines changed since. Add
`findings` to `guide.json`: every finding from that round (review comments, or the guide's review
cards at that version) and where it was answered, or `open: true`.

If the reviewed sha is no longer reachable (the branch was rewritten and pruned), the panel says
so; point the user to the merge request's own version compare.
