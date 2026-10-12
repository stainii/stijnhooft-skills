# Merge request

Two arguments, both on the current branch's guide in `.claude/session-guides/`. Write or update the
guide first (`ticket` scope) if it is missing or older than the branch head.

## `mr` — the description reviewers read

The guide is for the author; the merge request is what colleagues see. Condense the guide into
Markdown at `.claude/session-guides/<branch>.mr.md`, in the shape of the `/pr` skill where one is
installed, otherwise:

1. **Summary** — two or three sentences in the repo's own terms, then one diagram (Mermaid: the
   lineage for a refactoring, the call-tree diff or a state diagram otherwise), then the
   Ship / Show / Ask call and the review size in one line.
2. **Read in this order** — the guide's list, file names only, tiers in italics.
3. **Evidence** — before and after, and the tests that pin it.
4. **Merge danger** — door and blast radius.
5. **Review focus** — the open review cards as task-list checkboxes, one line each.

Put the same text in the guide's *MR description* panel, and give the user the path. Creating or
editing the merge request on the server (`glab mr create`, `gh pr create`) publishes it: do that only
when the user asks, for this MR.

Done when every open review card is a checkbox and every claim links back to something the guide
proves.

## `reviewed` — mark what the reviewers saw

Append the branch head to `.claude/session-guides/<branch>.reviewed` as
`<ISO date> <full sha> v<n>`. Nothing is pushed; the file is local.

From then on, every guide for this branch gets a **Since last review** panel built from
`git range-diff <merge-base>..<last reviewed sha> <merge-base>..HEAD`:

- one row per commit: *unchanged* (`=`), *changed* (`!`, with its diff of diffs), *new* (`>`),
  *dropped* (`<`) — range-diff pairs commits by content, so this survives a rebase or squash;
- the review size of only what changed since then;
- every finding from that round — review comments, or the guide's review cards at that version —
  and where it was answered, or that it is still open.

If the reviewed sha is no longer reachable (the branch was rewritten and pruned), say so and fall
back to the merge request's own version compare.
