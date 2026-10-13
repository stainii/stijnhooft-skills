# stijnhooft-skills

Agent skills I use with [Claude Code](https://claude.com/claude-code), installable with the
[`skills`](https://github.com/vercel-labs/skills) CLI.

## Skills

| Skill | What it does |
|---|---|
| [**session-guide**](skills/session-guide/README.md) | Turns an agent's coding session into an HTML guide you can review and own: context, decisions and their alternatives, a walkthrough from entrypoint to persistence, proof, and review cards. It then turns that guide into a merge request reviewers can get through. Has a refactoring mode with a lineage map. |

## Install

One skill, for every project on this machine:

```bash
npx skills add stainii/stijnhooft-skills --skill session-guide -g
```

Leave out `-g` to install into the current project's `.claude/skills/` instead. To see what's
available:

```bash
npx skills add stainii/stijnhooft-skills --list
```

To update what you installed:

```bash
npx skills update
```

## Layout

```
skills/
└── <name>/
    ├── SKILL.md      the instructions the agent follows (name + description in the frontmatter)
    ├── README.md     for people
    └── …             whatever the skill loads on demand
tests/
└── <name>/           tests for a skill's scripts, kept out of the installed folder
```

A new skill is a new folder under `skills/`. The CLI finds it with no manifest, and it gets a row
in the table above.

### Working on a skill

Clone the repo and link the skill into Claude Code, so every edit is live:

```bash
git clone https://github.com/stainii/stijnhooft-skills.git ~/projecten/stijnhooft-skills
```

```bash
ln -s ~/projecten/stijnhooft-skills/skills/session-guide ~/.claude/skills/session-guide
```
