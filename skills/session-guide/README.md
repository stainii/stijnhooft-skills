# session-guide

A [Claude Code](https://claude.com/claude-code) skill that turns an agent's coding session into a
**guide you can review and own**: what the context was, which decisions were taken and why, what the
alternatives were, a walkthrough from entrypoint to persistence, and the proof that it works. It
also turns that guide into a merge request your colleagues can get through.

Working with agents shouldn't mean giving up control of your code. The diff shows *what* changed;
only the session knows *why*, what else was considered, and what was tried and abandoned. This
skill captures that while the agent still has it in context.

## What a guide looks like

One self-contained HTML page per session or ticket, with a sidebar and two ways in:

- **Walkthrough**: one real request through the changed code, in execution order. Each stop shows
  `path:line`, why the code is shaped that way, pseudocode first and the real change folded
  underneath.
- **Decision deep dives**: one page per decision, small ones included. Each has the real reason,
  the rejected alternatives, who decided (you, or the agent by default), whether it's a one-way or
  two-way door, and every code change that implements it.

The overview page is visual first:

| View | What it shows |
|---|---|
| **Where we are** | The system as C4 containers and components, with what this change touches highlighted |
| **Walkthrough chain** | The request path as boxes, changed steps marked |
| **Change map** | Every changed file in its layer, with +/− bars, each linked to its explanation |
| **Decisions at a glance** | A grid of door × who decided. The "one-way, agent default" cell is where to look hardest |
| **Evidence** | Before/after as a picture: a timeline, a state diagram, a screenshot, and the test that pins it |
| **Merge danger** | Door and blast radius |

Plus:

- **Contracts**: every changed signature, type, endpoint and schema, with no bodies. Big ones get a
  **shape table**: before and after side by side, each member marked added, removed, type changed or
  renamed.
- **Review this**: one card per point, most severe first. Each states the claim, tags its kind
  (doc ≠ code, race, untested, one-way door, agent default), shows the **proof** (docs beside code,
  or a concrete scenario step by step with the step where it goes wrong marked), and ends with the
  decision that's yours. Points that were checked and hold stay visible as green cards. Tick a card
  off when you've reviewed it.

### Refactoring mode

When files were deleted, created, renamed, split or merged, three more panels:

- **Lineage**: old files on the left, new on the right, joined by what happened (kept, moved,
  renamed, merged, split, rewritten). Links git detected are solid; links only the session knows are
  dashed. A deleted file with no successor and a new file with no predecessor stand out. Below it,
  **where did it go**, by responsibility rather than by file.
- **Changed in transit**: each moved piece before and after, with the lines that changed meaning
  marked. Pieces that moved unchanged say so in one line.
- **Behaviour**: a refactoring claims nothing changes. A ledger of what stayed the same, what
  changed on purpose and what was dropped, plus the tests mapped old → new.

Git can't see a merge or a rewrite under a new name, so record the lineage **during** the work
(`/session-guide ticket` at the end of every session), not afterwards.

### Merge request mode

- **Review size**: every changed line sorted into *read* / *skim* / *skip*, against a budget of 400
  lines to read, next to a **Ship / Show / Ask** call.
- **Read in this order**: where a reviewer should start, and what they can skip.
- **Split plan**: when it's over budget or mixes refactoring with behaviour, the same work as a stack
  of smaller MRs in a safe merge order.
- **MR description**: the guide condensed into Markdown for GitLab or GitHub, with a Mermaid diagram
  and the review focus as checkboxes.
- **Since last review**: after a review round, `git range-diff` against the version reviewers saw.
  It shows which commits are unchanged, changed or new, and where each finding was answered.

## Install

With the [`skills`](https://github.com/vercel-labs/skills) CLI, into every project on this machine:

```bash
npx skills add stainii/stijnhooft-skills --skill session-guide -g
```

Or into the current project only (`.claude/skills/`, which you can commit so your team gets it too):

```bash
npx skills add stainii/stijnhooft-skills --skill session-guide
```

`-a claude-code` limits the install to Claude Code, and `--copy` copies the files instead of
symlinking them. The CLI installs the whole skill folder (see [Files](#files)). It needs
`python3` (standard library only) and `git`. To update later:

```bash
npx skills update session-guide
```

### From a clone, to work on the skill itself

```bash
git clone https://github.com/stainii/stijnhooft-skills.git ~/projecten/stijnhooft-skills
```

```bash
ln -s ~/projecten/stijnhooft-skills/skills/session-guide ~/.claude/skills/session-guide
```

Every edit in the clone is then live in Claude Code. A local path works with the CLI too:
`npx skills add ~/projecten/stijnhooft-skills --skill session-guide`.

## Use

Run it yourself at the end of a session, while the agent still has the conversation:

| Command | Does |
|---|---|
| `/session-guide session` | A guide to what this session changed |
| `/session-guide ticket` | A guide to the whole branch, rewritten as one story across sessions |
| `/session-guide mr` | The merge request description, written next to the guide |
| `/session-guide reviewed` | Marks the branch head as the version reviewers saw (local file, never pushed) |
| `/session-guide quiz` | 3–5 questions on the change, one at a time, to check you really own it |

Guides are written to `.claude/session-guides/` in the repo: a folder per guide holding its data
(`facts.json`, `guide.json`, `parts/`), and next to it the page (`<name>.html`) and the MR text
(`<name>.mr.md`). The skill checks that this folder is
gitignored and asks before writing anywhere else. Open them in a browser. A static server makes
in-page links and hashes behave best:

```bash
python3 -m http.server 4310 --directory .claude/session-guides
```

It is manual on purpose. A hook that runs after the session has ended no longer has the
conversation, and a reminder on every turn is noise.

## How it stays honest

- **A script checks the guide against the code** before it renders. A changed file nothing
  explains, a `path:line` past the end of its file, a hunk range with no changed lines, a decision
  with no code behind it: each is reported, and the page is only written when there are none.
- **Hunks are pulled from git**, never retyped by the agent, so the code on the page is the code in
  the repo.
- **Every call-tree edge is checked against the code** (`grep` the caller for the callee) before it
  goes into the guide. Anything that couldn't be confirmed is marked *unverified*.
- **Assumptions are labelled** as *assumed*, never stated as fact.
- **Decisions the agent took on its own are badged** *agent default* and put on the review list.
- It uses the repo's own records: it links ADRs and `CONTEXT.md` terms instead of restating them,
  and proposes an ADR for architectural decisions.

## How it keeps the cost down

The agent writes **data, not a page**. Everything measurable comes from scripts: line counts,
tiers, layers, renames, the change map, the file tree, the review size, the lineage git can see,
and the code in every hunk. The agent reads code one file at a time, only for the files a reviewer
must read, and writes only what the scripts can't know: the *why*.

A large change (more than 50 files or 3000 changed lines) is split into jobs of up to 1500 lines to
read. A subagent per job reads that code and writes its part of the guide; the main session reads
the parts, not the code, so its context stays small. Large guides also group the change map per
directory.

## Files

| File | Role |
|---|---|
| `SKILL.md` | The steps the agent follows, and the vocabulary (*door*, *blast radius*, *agent default*, *smallest view*) |
| `guide.schema.ts` | The format of `guide.json`, the only thing the agent writes |
| `scripts/gather.py` | Measures the change into `facts.json`: files, lines, tiers, layers, renames, modules, jobs, since-last-review |
| `scripts/build.py` | Merges the parts, checks the guide against the code, renders the page and the MR text |
| `scripts/guide.py`, `source.py`, `views.py` | What `build.py` is made of: the guide as data, the code as git sees it, and what the page and MR show |
| `scripts/files.py` | Lists the changed files, per job or tier |
| `template.html` | The page: Bento-style theme (light and dark), every component, drawn from the embedded data. Nobody edits it per guide |
| `SUBAGENTS.md` | Large changes: one subagent per job, loaded only then |
| `REFACTORING.md` | Lineage, changed in transit, behaviour, loaded only for a refactoring |
| `MERGE-REQUEST.md` | `mr` and `reviewed`, loaded only for those |
| `QUIZ.md` | `quiz`, loaded only for that |

Each page is one self-contained HTML file. Fonts (Geist) and Mermaid come from CDNs and the page
still renders without them, apart from the Mermaid diagrams.

The scripts' tests are in [`tests/session-guide`](../../tests/session-guide), outside the skill so
they aren't installed: `python3 -m unittest discover -s tests/session-guide` from the repo root.

## Credits and further reading

- The visual-first vocabulary (call trees, file trees and pseudocode as diffs) comes from
  HumanLayer's [show-me](https://www.humanlayer.com/blog/show-me-skill) skill and Matt Pocock's
  `/pr` skill built on it. *Evidence* and *Merge danger* come from the latter.
- Refactoring kept apart from behaviour changes: Chromium's
  [CL tips](https://chromium.googlesource.com/chromium/src.git/+show/HEAD/docs/cl_tips.md), after
  Google's *Small CLs*.
- The 200–400 line review budget: the
  [SmartBear/Cisco study](https://agileconnection.com/article/largest-case-study-code-reviews-ever).
  One company's data, so a guideline rather than a law.
- [Ship / Show / Ask](https://martinfowler.com/tags/version%20control.html), Rouan Wilsenach.
- [`git range-diff`](https://www.git-scm.com/docs/git-range-diff) for re-review after a rebase.
