# Quiz

Test the user's ownership of the change, in chat. Source the questions from the guide for the
current branch in `.claude/session-guides/` and from the diff; if no guide exists, use the diff and
the conversation.

Ask 3–5 questions, one at a time, each answerable only by someone who understands the code:
behaviour on an edge case ("what happens when X is null?"), the reason for a shape ("why does this
live in the service, not the controller?"), the consequence of a decision ("what breaks if V9 is
rolled back?"). Weight them towards agent defaults and one-way doors.

After each answer: say whether it holds, and when it does not, point to the `path:line` that shows
why. Wait for the answer before asking the next question.

Done when every question is answered. Close with which areas were shaky. Store nothing.
