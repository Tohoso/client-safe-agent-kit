---
name: client-safe-agent-kit
description: Three small checks that keep an agent from embarrassing you in front of clients - reply-trim (cut the sentences the client never needed and prove nothing new was added), send-gate (block wrong recipients, wrong weekdays, fake quotes, dead links, untraceable amounts) and preflight-ledger (no irreversible send/delete/deploy/payment until the loss is written down and one check has passed). Use them in that order on every outgoing message and every irreversible action.
---

# Client-Safe Agent Kit

**Keeps an agent that writes and acts for you from making the mistakes you cannot take back in front of a client.**

Three skills, one pipeline. Each one stops a different failure, and each one is a plain Python script with tests, so the agent cannot talk its way past it.

```
draft ──> reply-trim ──> send-gate ──> preflight-ledger ──> human approval ──> send / act
          cut padding,   facts match    loss written down,
          nothing added  the sources    one check passed
```

| skill | stops | how |
|---|---|---|
| `reply-trim/` | recaps, unrequested warnings, new asks and technical asides in client replies; new promises slipped in while editing | flags 4 kinds of sentences, asks "would the reader be worse off without this?" per sentence, `compare` fails if the trimmed reply added text |
| `send-gate/` | wrong recipient, wrong weekday, invented quote, dead link, untraceable amount | roster check, weekday recomputation (English and Japanese), verbatim quote check, link check, amount tracing; exit 1 on BLOCK |
| `preflight-ledger/` | irreversible actions done on a hunch | `begin` (action, loss, one check) -> `verify` (the ledger runs the check) -> `go` (refused unless passed and unchanged) -> `close` (lesson), with `search` to recall past lessons |

## Install

Copy the three folders into your skills directory (for example `~/.claude/skills/` or your OpenClaw skills folder), or keep this folder as is. Python 3.9+, standard library only. Run each folder's tests with `python3 -m pytest <folder>/tests` (49 tests in total).

## Standing instructions to give your agent

Paste this into the agent's instructions, adjusted to your tools:

> Before any message leaves on my behalf:
> 1. Run `reply-trim scan --worksheet` on the draft, delete every sentence the reader would not miss, then run `reply-trim compare` and remove anything it reports as ADDED.
> 2. Run `send-gate` with the real recipient IDs, my roster, and the sources the message relies on. Fix every BLOCK. Tell me about every WARN.
> 3. For a send, delete, deploy, payment or public post: `preflight-ledger begin` with the concrete loss and one check, `verify`, and only on `go` exit 0 do it.
> 4. Ask me for approval with the trimmed draft, the send-gate result and the ledger entry. Close the ledger entry when the outcome is known.

## Why these three

Most agent mistakes with clients are not about intelligence. They are a wrong ID copied from an old thread, a weekday computed in the head, a paraphrase put in quote marks, a "quick note" that gives the client homework, a deploy to the wrong target. All of them are cheap to check by machine and expensive once they are out. Each skill does one of those checks and nothing else.

## License

MIT. Copyright (c) 2026 Toru Hosokawa (PHAI).
