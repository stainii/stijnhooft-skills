// guide.json: what you write. build.py merges parts/*.json into it, checks it, and renders the page and the MR text.
// Everything measurable (files, line counts, tiers, renames, the change map, the file tree, review size, the
// since-last-review rows, lineage nodes and the links git detects) comes from facts.json: write only what it can't know.
//
// Text  plain text, never HTML: `code`, **bold**, *italic* and [label](#id) links to a panel are rendered.
// Ref   "path:line" or "path:from-to" in the file as it is now; for a deleted file, in the file at the base.
//       Always with line numbers: a bare path is not a Ref.
// Hunk  a Ref whose range holds changed lines: build.py pastes in the real diff lines. Keep ranges tight.
// Code  a Ref read as plain lines (no diff): Transit.from is read at the base, Transit.to as it is now.
// Id    [a-z0-9-]+, unique. Panels: overview, contracts, review, readorder, split, since, mr, lineage, transit,
//       behaviour, plus every Stop.id and Decision.id.
type Text = string; type Ref = string; type Hunk = Ref; type Code = Ref; type Id = string;
type Tier = "read" | "skim" | "skip";
type Door = "one-way" | "two-way";
type Call = "ship" | "show" | "ask"; // ask for any one-way door

interface Guide {
  title: string;                       // ticket number + short title
  meta?: string;                       // ADR refs · branch · updated YYYY-MM-DD
  context: Text;                       // the problem in the user's terms, why now
  outOfScope?: Text;
  ship: { call: Call; why: Text };
  budget?: number;                     // lines a reviewer can read in one sitting; default 400
  where?: C4 | { before: C4; after: C4 }; // the system at this commit; before/after for a refactoring
  callTree?: string;                   // the changed flow as a call tree, +/- marking added and removed calls
  files?: { [path: string]: { panel?: Id; tier?: Tier; layer?: string; review?: boolean } }; // overrides facts.json
  groups?: { name: string; match: string[]; panel?: Id; tier?: Tier; layer?: string }[]; // globs (** allowed): files explained as one chip
  evidence: { timeline?: Timeline; mermaid?: string; before?: string; after?: string;
              test?: Ref;              // path:line of the test that pins it, not just its file
              notCovered: Text };
  danger: { door: Door; why: Text; blast: Text };
  sessions: { date: string; text: Text }[]; // ticket scope: keep the earlier sessions' lines
  contracts: Contract[];
  review: Card[];                      // any order: the page sorts by severity
  deadEnds?: Text[];
  flows: { title: string; stops: Stop[] }[]; // one per independent request followed
  decisions: Decision[];
  readOrder: { tier: Tier; files: string[]; why: Text }[]; // globs; together they cover every read-tier file
  split?: { title: string; kind: "refactor" | "new" | "behaviour"; call: Call; files: string[]; items: Text[];
            alone?: Text }[];          // alone: what it must merge with, when it can't merge on its own
  findings?: { text: Text; open?: boolean }[]; // since last review: each earlier finding → where it was answered
  mr: { summary: Text; mermaid?: string };     // the rest of the MR text is generated
  refactoring?: Refactoring;
}

interface Stop {
  id: Id; at: Ref; title: string;
  depth?: number;                      // indent in the call tree, 0 = entry
  text: Text;                          // what happens here and why it is shaped so
  pseudo?: string;                     // logic: pseudocode first, +/- markers allowed
  hunk?: Hunk;                         // the real change, folded under the pseudocode (open when there is no pseudo)
  mermaid?: string;                    // state that matters: stateDiagram-v2
  review?: { why: Text; alt: Text };   // turns the stop into Diff / Why / Alternatives tabs
}

interface Decision {
  id: Id; title: string; door: Door; by: "you" | "agent"; // agent = an agent default: also gets a review card
  why: Text;                           // the real reason, from the session, or from the record it came from (ADR, ticket)
  alt: Text;                           // each alternative and why it lost, or "none considered"
  hunks: { at: Hunk; text: Text }[];   // every hunk that implements it
}

interface Contract {
  at: Ref; who: Text;                  // who depends on it
  hunk?: Hunk;                         // signature or type only, no bodies
  shape?: { name: string; before: Member[]; after: Member[] }; // > 3 members changed, or too long to compare by eye
}
type Member = [name: string, type?: string, note?: string] | { name: string; type?: string; was?: string; note?: string };

interface Card {
  id: Id; sev: "high" | "med" | "low" | "ok"; // ok = checked, holds
  claim: string;                       // the point, as a claim
  kinds: string[];                     // doc ≠ code, race, untested, one-way door, agent default, drift, ...
  why: Text;                           // why it matters, one or two sentences
  says?: { label: string; text: Text }; does?: { label: string; text: Text }; // claim vs code, side by side
  steps?: { text: Text; mark?: "bad" | "good" }[]; // a scenario, the step where it goes wrong marked
  hunk?: Hunk; command?: string;       // the hunk, query or command that settles it
  ask: Text;                           // the decision or check that is the user's
  see?: Id[];
}

interface C4 { person?: string; rows: Box[][] } // row 1: the request path; row 2: stores and external systems
interface Box { name: string; tech?: string; kind?: "db" | "ext"; hit?: boolean; link?: string; // link: label to the next box
                comps?: { name: string; hit?: boolean; panel?: Id }[] }

interface Timeline { now?: string; unit?: string; // dates YYYY-MM-DD, or numbers with a unit such as "s"
  rows: { label: string; events: { at: string; text: string; tone?: Tone }[];
          spans?: { from: string; to: string; text: string; tone?: Tone }[] }[] }
type Tone = "ok" | "bad" | "neutral";

interface Refactoring {
  // Nodes and git-detected links come from facts.json, one lineage per job. Add the links git cannot see.
  links: { from: string[]; to: string[]; kind: "kept" | "moved" | "renamed" | "merged" | "split" | "rewritten";
           note?: string }[];
  gone?: { [oldPath: string]: Text };  // intentionally gone: why, for a deletion with no successor
  whereTo: { what: string; before: string; after: string;
             how: "moved" | "merged" | "rewritten" | "deleted" | "derived" | "new" }[]; // one row per responsibility
  transit: { from: Code; to: Code; text: Text; unchanged?: boolean; mark?: string[] }[]; // mark: substrings that changed meaning
  behaviour: { what: string; before: string; after: string; status: "unchanged" | "changed" | "dropped" }[];
  tests?: { before: Member[]; after: Member[] };
}
