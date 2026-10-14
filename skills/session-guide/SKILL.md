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

You write **data, not a page**: `guide.json`, against [guide.schema.ts](guide.schema.ts). Two
scripts do the mechanical work, so spend your tokens on the *why*:

- `scripts/gather.py` measures the change: files, line counts, tiers, layers, renames, modules.
- `scripts/build.py` checks your `guide.json` against the code, pastes in the real hunks, and
  renders the page and the MR text.

Run both with `python3`, from the repo root, by their path in this skill's folder. On Windows,
`python3` can point to the Microsoft Store stub: use `py -3` there.

## 1. Pick the scope

- `session`: the changes made in this session. Pass `--base <sha>`, the commit HEAD was on when the
  session started (from the conversation, or `git reflog`). Name: `<branch>--<YYYY-MM-DD-HHMM>`.
- `ticket`: the branch since its merge-base with the default branch. Pass `--ticket`. Name:
  `<branch>`. A branch built on another feature branch is compared with that branch:
  `--against <branch>`.
- No argument: ask which.

The guide is the folder `.claude/session-guides/<name>/` (slashes in the name become `-`). Confirm
with `git check-ignore -q .claude/session-guides/x` that it is ignored; if it is not, ask the user
where to write before going on.

## 2. Gather

Run `gather.py .claude/session-guides/<name> <--base <sha> | --ticket>`, adding `--reviewed <sha>`
with the last sha in `.claude/session-guides/<branch>.reviewed` when that file exists. It writes
`facts.json` and prints a summary: the base, totals per tier, **LARGE** or not, the jobs, suggested
groups, and for a small change the files to read.

If the summary says **CHECK BASE**, the branch builds on other branches and the scope may be wrong.
Stop and ask the user: "Compare with `<default branch>` or with `<branch>`?" Run `gather.py` again
with their answer (`--against <branch>`, or `--base <sha>` to keep the base it printed). Nothing
else happens on an unconfirmed base: a wrong scope wastes every step after it. Work from the summary; `scripts/files.py <guide-dir> [--job N] [--tier T]`
lists files when you need them.

Read code as **hunks, never the whole diff**: `git diff <base> -- <path>` for one file at a time,
only for read-tier files and the contracts. A skim or skip file needs its path, not its lines.

Then the conversation: the ask, clarifications, every decision, dead ends, the user's corrections.
For `ticket` with an existing `guide.json`: its decisions and sessions log carry the earlier
sessions' *why*, which is otherwise lost. Keep them. Use the repo's own records (ADRs,
`CONTEXT.md`, glossary): their terms, and links to them.

No conversation to draw from (a `ticket` whose sessions you did not see): the *why* lives in the
ticket's folder, the ADRs and the commit messages. Read them, take each decision from there with
`by: "you"`, and name the source in `why` ("from ADR-0012", "from the commit message of abc123").
A decision the code shows but no record explains is not yours to invent: write what the code does,
`alt: "unknown"`, and a review card asking the user why.

If the summary says **LARGE**, tell the user the base and the number of jobs, and wait for their
yes before you follow [SUBAGENTS.md](SUBAGENTS.md): one subagent per job reads
the code and writes a part; you read the parts.

Done when you can name, for every read-tier file, the stop, decision, contract or card it belongs
to, and every other file has one or belongs in a group.

## 3. Write guide.json

The language is the one the session was held in; if that is unclear, ask. For `ticket` with an
existing guide, rewrite it as one coherent story and add a line to the sessions log. Write only what
`facts.json` cannot know. A hunk is a `path:from-to` reference into the file as it is now: keep it
tight and never paste diff text.

- **Walkthrough** (`flows`): one real request through the changed code in execution order:
  entrypoint → validation → domain → persistence or external call → back. Each stop: where, what
  happens and why it is shaped so, then the change in its *smallest view*: pseudocode for logic with
  the real hunk folded underneath, Mermaid for state. A stop the user must look at hardest gets
  `review` (Diff / Why / Alternatives). Several independent flows get one flow each.
- **Decisions**: one per decision, small ones included (naming, seam placement, library, test
  strategy): the real reason, the alternatives and why they lost, who decided, its *door*, and
  every hunk that implements it.
- **Overview**: context and scope; `where`, the system at this commit as C4 level 2 (containers,
  components inside), from the repo's architecture doc or else its layout, every touched one `hit`;
  a call-tree diff of the changed flow; evidence as a picture (a timeline when dates or time matter,
  a Mermaid diagram otherwise) plus the test that pins it and what is not covered; merge danger
  (*door* and *blast radius*).
- **Contracts**: every changed signature, type, endpoint, event and schema, without bodies, saying
  who depends on each. It is what a reviewer reads first. More than three members changed, or lines
  too long to compare by eye: a `shape` instead.
- **Review cards**: one per point: every *agent default*, one-way door, doc/code mismatch, race,
  unproven assumption, shortcut and open TODO. State the point as a claim, say why it matters,
  show the **proof** in the smallest form that convinces (what the docs claim beside what the code
  does; a scenario step by step with the step where it goes wrong marked; or the hunk, query or
  command that settles it), and end on the decision that is the user's. A point you checked and
  found sound stays as a card with `sev: "ok"`, so the user sees it was looked at.
- **Merge request**: `gather.py` guessed a tier per file (*read* logic, *skim* tests, DTOs, config,
  docs, *skip* generated, deleted, moved unchanged); correct a wrong guess in `files` or a group.
  `readOrder` covers every read-tier file in the order a reviewer should take them. `ship`: Ship,
  Show or Ask, Ask for any one-way door. `split` when the read lines exceed the `budget` or the change mixes
  refactoring with behaviour: the same work as a stack of smaller MRs in safe merge order, one kind
  of thing each.
- **Groups**: files that need no explanation of their own (fixtures, tests that follow a rename,
  generated code) as one group each, so one line explains many files. Start from the suggested
  groups in the summary (docs, lockfiles); drop one when its files do need a word.

When files were deleted, renamed, split or merged, also follow [REFACTORING.md](REFACTORING.md).

**Verify every edge** of each call tree and walkthrough against the code (`grep` the caller for
the callee) before writing it down: the guide is drawn from what the code says, not from memory.
An edge you could not confirm is marked *unverified*. Write what you know and mark what you
assumed ("assumed X").

### Vocabulary

- **Smallest view.** Explain with the smallest view that makes the point: call tree for flow,
  pseudocode for logic, Mermaid for state or sequence, and a diff of any of these to show change.
  A sentence or two beside each view; hunks only where they teach.
- **Door.** One-way (destructive, data-migrating, hard to walk back) or two-way.
- **Blast radius.** What a merge could break, and for whom.
- **Agent default.** A decision you took without the user discussing it: `by: "agent"` and a
  review card. These are what the user most needs to see.
- An architectural decision in a repo that keeps ADRs: propose an ADR in a review card.

## 4. Build

Run `build.py .claude/session-guides/<name>`. It prints `ok <path>`, or one problem per line: a
changed file nothing explains, a read file missing from `readOrder`, a reference past the end of
its file, a hunk range with no changed lines, a decision without hunks, a link to a panel that
does not exist. Fix each in `guide.json` (or the part a problem names) and run it again.

Done when `build.py` prints `ok`, every decision from the conversation has a deep dive, and every
agent default has a review card.

## 5. Hand over

Open the page (`open <path>` on macOS, `start "" <path>` on Windows, `xdg-open <path>` on Linux), then give the user its path and the open review cards in chat.
