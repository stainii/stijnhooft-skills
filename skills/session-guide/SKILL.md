---
name: session-guide
description: Write an HTML guide to the code changed in this session or ticket — walkthrough, decision deep dives, evidence — so you can own what the agent wrote; then turn it into a merge request reviewers can get through. Optional quiz.
argument-hint: "session | ticket | mr | reviewed | quiz"
disable-model-invocation: true
---

# Session guide

The user works with agents and keeps full ownership of the code. This guide is how they take it:
written for a reviewer who did not watch the session and must be able to defend every line. The
diff shows *what*; only this conversation holds *why*, the alternatives, and the dead ends — that
is the guide's real content.

If the argument is `quiz`, follow [QUIZ.md](QUIZ.md) instead of the steps below. If it is `mr` or
`reviewed`, follow [MERGE-REQUEST.md](MERGE-REQUEST.md).

## 1. Pick the scope

- `session` — the changes made in this session. File: `<branch>--<YYYY-MM-DD-HHMM>.html`.
- `ticket` — everything on the branch since its merge-base with the default branch. File:
  `<branch>.html`.
- No argument — ask which.

Path: `.claude/session-guides/` at the repo root. Confirm with `git check-ignore` that it is
ignored; if it is not, ask the user where to write before going on.

## 2. Gather

- The change set for the scope: commits, `git diff`, untracked files.
- The conversation: the ask, clarifications, every decision, dead ends, the user's corrections.
- For `ticket`, an existing `<branch>.html`: its decisions and sessions log carry the earlier
  sessions' *why*, which is otherwise lost. Keep them.
- The repo's own records (ADRs, `CONTEXT.md`, glossary): use their terms and link to them.

Done when you can name, for every changed file, which decision or stop it belongs to.

## 3. Write

Copy [template.html](template.html) and fill it. The language is the one the session was held in;
if that is unclear, ask. For `ticket` with an existing guide, rewrite it as one coherent story and
add a line to the sessions log.

Two ways in, both from the left-hand nav:

- **Walkthrough** — one real request through the changed code in execution order: entrypoint →
  validation → domain → persistence or external call → back. Each stop: `path:line`, what happens
  and why it is shaped so, then the change in its *smallest view* — for logic, pseudocode first
  with the real hunk folded underneath; for state, a Mermaid state diagram. Stops flagged *review*
  use the Diff / Why / Alternatives tabs. Several independent flows get a list each.
- **Decision deep dives** — one panel per decision, including the small ones that shape code
  (naming, seam placement, library, test strategy): the decision, the real reason, the
  alternatives and why they lost, who decided, its *door* — then a scroll of every hunk that
  implements it.

Overview panel: context and scope; **where we are** — the system at this commit as C4 level 2
(containers, with their components inside), taken from the repo's architecture doc or else its
directory layout, with every touched container and component highlighted; a call-tree diff of the changed flow; a **change map** placing
**every** changed file in its layer with its line counts (`git diff --numstat`), each chip linked to
the stop or decision that explains it — trivial files grouped into one chip; Evidence as a picture
(a before/after timeline when dates or time matter, a screenshot for UI, a Mermaid state or
sequence diagram otherwise, and the test that pins it) and what is not covered; Merge danger
(*door* plus *blast radius*); sessions log. The walkthrough chain and the decision grid (door ×
who decided) draw themselves from the nav and the decision badges.

Contracts panel: every changed signature, type, endpoint, event and schema, as a diff with no
bodies, saying who depends on each. It is what a reviewer reads first. A big contract — more than
three members changed, or lines too long to compare by eye — gets a **shape table**: before and
after side by side, one row per member marked added, removed, type changed or renamed, a note on
the rows that matter, and the raw diff folded underneath.

Review panel: one **review card** per point, most severe first — every *agent default*, one-way
door, doc/code mismatch, race, unproven assumption, shortcut and open TODO. Each card states the
point as a claim, tags its kind, says in a sentence why it matters, then shows the **proof** in the
smallest form that convinces: what the docs or comment claim beside what the code does; a concrete
scenario step by step, marking the step where it goes wrong; or the hunk, query or command that
settles it. It ends on the decision or check that is the user's. A point you checked and found
sound stays as a card marked *holds*, so the user sees it was looked at. Dead ends and surprises
follow the cards.

### Merge request

Every guide also prepares the review. Sort every changed line into a **tier** — *read* (logic),
*skim* (tests, DTOs, config, docs), *skip* (moved unchanged, generated, deleted: the reviewer checks
the list, not the lines) — and show the totals as the **review size** against a budget of 400 read
lines, beside a **Ship / Show / Ask** call (Ask for any one-way door). Then:

- **Read in this order** — the files in the order a reviewer should take them, each with its tier
  and why it comes at that point. The review cards come first.
- **Split plan** — when the read lines exceed the budget, or the change mixes refactoring with
  behaviour: the same work as a stack of smaller MRs in safe merge order, each doing one kind of
  thing (new code, refactoring, behaviour), each with its size and Ship / Show / Ask. Mark an MR
  that must not merge alone and say what it travels with.
- **Since last review** — when a version was marked reviewed (see MERGE-REQUEST.md).

### Refactoring

When files were deleted, created, renamed, split or merged, add the three Refactoring panels and
show the system before and after side by side under *where we are*. Record the lineage **during**
the work, in `ticket` scope: git sees a rename only when a file survives mostly intact
(`git diff -M -C --name-status`, with its similarity), and every merge, split or rewrite under a
new name is known only to the session.

- **Lineage** — every old file on the left, every new one on the right, joined by what happened:
  kept, moved, renamed, merged, split, rewritten. Each link says whether git detected it or the
  session states it. An old file with no successor and a new one with no predecessor stand out on
  their own; each deletion either has a successor or a written "intentionally gone".
  Below it, **where did it go**: one row per responsibility, not per file — before, after, and
  how (moved, merged, rewritten, deleted, derived, new).
- **Changed in transit** — every piece that moved, before and after side by side, with the lines
  that changed meaning marked. A piece that moved as-is says so in one line; those need no review.
- **Behaviour** — a refactoring claims nothing changes. A ledger of each behaviour before and
  after, marked unchanged, changed on purpose, or dropped; the tests as a shape table, a moved
  test linked to where it went. A deleted test with no successor, a modified test, a deletion
  with no successor and a contract that is more than renames each get a review card.

A large refactoring gets one lineage per module rather than one map nobody can read.

### Vocabulary

- **Smallest view.** Explain with the smallest view that makes the point: call tree for flow, file
  tree for layout, pseudocode for logic, Mermaid for state or sequence, and a `diff` of any of
  these to show change. A sentence or two beside each view; hunks only where they teach.
- **Door.** One-way (destructive, data-migrating, hard to walk back) or two-way.
- **Blast radius.** What a merge could break, and for whom.
- **Agent default.** A decision you took without the user discussing it. Badge every one and put it
  on the review checklist: these are what the user most needs to see.
- An architectural decision in a repo that keeps ADRs: propose an ADR in the review list.

Write what you know and mark what you assumed ("assumed X"). A section with nothing in it gets
one line saying so.

**Verify every edge** of each call tree and walkthrough against the code (`grep` the caller for the
callee) before writing it down: the guide is drawn from what the code says, not from memory. An
edge you could not confirm is marked *unverified*.

Done when every edge is verified, every changed file is in the change map, every decision from the conversation has a deep
dive, every agent default is on the review list, and every `path:line` points at the line meant.

## 4. Hand over

Open the file (`open <path>`), then give the user its path and the review checklist in chat.
