# Refactoring

Files were deleted, created, renamed, split or merged. Add `refactoring` to `guide.json`; the page
gets the Lineage, Changed in transit and Behaviour panels. Give `where` a `before` and an `after`.

Record the lineage **during** the work, in `ticket` scope. Git sees a rename only when a file
survives mostly intact, and `build.py` draws those links itself, with their similarity. Every merge,
split or rewrite under a new name is known only to the session.

- **links**: each link git cannot see: old files → new files and what happened (kept, moved,
  renamed, merged, split, rewritten). An old file with no successor and a new one with no
  predecessor stand out on the map on their own.
- **gone**: each deletion with no successor, and why it is intentionally gone. `build.py` reports
  a deletion that has neither a link nor a reason.
- **whereTo**: one row per responsibility, not per file: before, after, and how.
- **transit**: every piece that moved: its old range at the base (`from`) and its new range now
  (`to`); `build.py` pulls in both. `mark` the words that changed meaning. A piece that moved as-is
  gets `unchanged` and needs no review.
- **behaviour**: a refactoring claims nothing changes. A ledger of each behaviour before and after,
  marked unchanged, changed or dropped; the tests as a `shape`, a moved test with its `was`.

A deleted test with no successor, a modified test, a deletion with no successor and a contract
that is more than renames each get a review card.
