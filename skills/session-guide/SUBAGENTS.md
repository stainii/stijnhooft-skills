# Large change: one subagent per job

A large change does not fit one context: reading it all is what made a guide expensive. The
summary listed **jobs**, neighbouring modules of up to 1500 read lines each. A subagent per job
reads that job's code and writes a **part**, `parts/job-<N>.json`; you read the parts, never the
code itself. Your context stays small, and that is the saving.

1. Write the decisions you already know from the conversation into `guide.json`: `id`, `title`,
   `door`, `by`, `why`, `alt`, and `hunks: []`. Subagents attach hunks to them by `id`.
2. Dispatch every job in one turn, in the background, on the `sonnet` model, each with the brief
   below filled in. A subagent starts cold: the brief is all it knows.
3. When all have reported, read each part. Write the *why* everywhere a subagent could only say
   *what*: the decisions, the overview, the review cards' asks. Order the flows of one request in
   execution order, and drop stops that say nothing new.

Done when every job has reported and its part is read.

## The brief

```
You write one part of a session guide: a page that explains a code change to its author.

Repo: <repo root>. The change: `git diff <base>` against the working tree.
Your job: <N>, modules <modules>. Its files: python3 <skill>/scripts/files.py <guide-dir> --job <N>
Read code per file with `git diff <base> -- <path>`: read-tier files and contracts only.
The format: <skill>/guide.schema.ts. Write <guide-dir>/parts/job-<N>.json, a partial guide with
only these keys, each holding only what concerns your modules:

- flows: each request path through your modules as stops, in execution order: `at`, `title`,
  `depth`, `text` (what the code does here), `pseudo` for logic, `hunk`. Verify every call edge
  with grep before writing it down; write "(unverified)" in the text of one you could not confirm.
- decisions: [{"id", "hunks": [{"at", "text"}]}] for every hunk that implements one of these:
  <id: title, one per line>
  Leave out a decision with no hunk in your job's files: another job holds its code.
  A decision you notice that is not listed: a review card "agent default?" with its hunk.
- contracts: every changed signature, type, endpoint, event and schema, with who depends on it.
- review: a card for each doc/code mismatch, untested change, deleted test without a successor,
  race or shortcut you find, with its proof.
- files / groups: every file of your job explained; readOrder: your read-tier files.
<refactoring only> refactoring: the links git cannot see (merged, split, rewritten), `gone` for a
  deletion with no successor, whereTo, transit, behaviour, tests. See <skill>/REFACTORING.md.

A hunk is a `path:from-to` reference into the file as it is now: never paste code.
Check with: python3 <skill>/scripts/build.py <guide-dir> --part parts/job-<N>.json
It prints only the problems of your part and your job's files; never stub other keys to silence it.
Done when it prints ok. Reply with one line: the
part's path and how many stops, hunks and cards it holds.
```
