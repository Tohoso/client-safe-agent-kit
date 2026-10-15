---
name: send-gate
description: Stops an agent from sending a message to the wrong person, with a wrong weekday, a made-up quote, a dead link, or an untraceable amount. Run it on every outgoing draft (email, Slack, chat, client reports) before it is sent; it blocks with a reason instead of letting the mistake go out.
---

# send-gate

**Stops the one-way mistakes an agent makes when it sends messages for you: wrong recipient, wrong weekday, invented quote, dead link, untraceable amount.**

A sent message cannot be unsent. Agents get these five things wrong most often, and every one of them is checkable by machine before sending:

| Check | What goes wrong without it | What send-gate does |
|---|---|---|
| Recipient | The agent copies an ID from an old thread, or greets "Bob" in a message addressed to Alice | Every `--to` ID and every `<@ID>` / `[To:ID]` mention must be in your roster. A greeting that names another roster person blocks |
| Date + weekday | "Tuesday, October 19" when the 19th is a Monday | Every date written with a weekday is recomputed (English and Japanese formats; a missing year means the nearest one) |
| Quote | The agent "quotes" what the client said, but paraphrases | Text in quote marks must appear verbatim in a source you pass in (whitespace and full-width differences are ignored) |
| URL | A hallucinated or moved link | With `--check-urls`, each link is fetched (HEAD, then GET). Private and local addresses are never fetched |
| Amount | A price nobody can trace back to the quote or invoice | Every amount ($, ¥, €, £, USD/JPY codes, 万円) must appear as a number in a source |

## When to use

- Before any message leaves on your behalf: email, Slack or other team chat, client reports, proposals
- As a required step in an agent's "send" procedure: draft -> **send-gate** -> human approval -> send
- After editing a draft, run it again. It takes well under a second without `--check-urls`

## Install

Copy this folder into your skills directory (for example `~/.claude/skills/send-gate/` or your OpenClaw skills folder). Python 3.9+ and the standard library only. No packages to install.

```bash
python3 scripts/send_gate.py --help
```

## Usage

```bash
python3 scripts/send_gate.py \
  --draft draft.txt \
  --roster roster.json \
  --to U01ALICE \
  --source meeting-notes.txt --source quote.txt \
  --check-urls
```

- `--draft` the message text (`-` reads stdin)
- `--roster` who you are allowed to address (format below). Without it, recipient IDs are reported as unverified
- `--to` the recipient ID(s) the message will actually be sent to. Repeat or comma-separate
- `--source` the originals the message relies on: meeting notes, the client's email, the quote, the invoice. Quotes and amounts are checked against these
- `--today YYYY-MM-DD` reference date for dates without a year (default: today)
- `--check-urls` fetch every link. Off by default so the check runs offline
- `--json` machine-readable report
- `--strict` exit 1 on WARN too (for pipelines that must not send anything unverified)

Exit code: `0` = PASS or WARN, `1` = BLOCK. On BLOCK, **do not send**: fix the lines marked BLOCK and run again.

### Roster format

```json
{
  "recipients": [
    {"id": "U01ALICE", "name": "Alice Tanaka", "aliases": ["Alice", "Tanaka-san"], "org": "Acme Corp"},
    {"id": "U02BOB", "name": "Bob Sato", "aliases": ["Bob"]}
  ]
}
```

Keep one roster per client or workspace, and build it from the system of record (your CRM, the chat's member list), not from past messages. Copying IDs out of old threads is exactly the mistake this check exists to catch.

## Example

```
$ python3 scripts/send_gate.py --draft examples/draft_bad.example.txt \
    --roster examples/roster.example.json --to U01ALICE \
    --source examples/source.example.txt --today 2026-11-05 --check-urls
send-gate: BLOCK
  [BLOCK] recipient Bob  - the greeting names Bob Sato, but the message goes to Alice Tanaka
  [BLOCK] date      Wednesday, November 12, 2026  - 2026-11-12 is a Thursday, not a Wednesday
  [BLOCK] quote     we want to pilot with all teams at once  - not found verbatim in any source: quote it exactly or drop the quote marks
  [BLOCK] amount    $1,500  - this amount does not appear in any source
  [BLOCK] url       https://example.com/this-page-does-not-exist-404  - HTTP 404
  [OK   ] recipient U01ALICE  - matches Alice Tanaka
Do not send. Fix the BLOCK lines, then run again.
```

The fixed draft (`examples/draft_ok.example.txt`) passes all five.

## Instructions for the agent

1. Write the draft to a file. Collect the sources it relies on (the message you are replying to, notes, quotes, invoices) as files.
2. Run send-gate with the real recipient ID(s) in `--to`.
3. If the result is BLOCK, fix every BLOCK line. Do not argue with the check and do not remove quote marks just to pass unless the text really is a paraphrase. Run again.
4. If the result is WARN, tell the human which items are unverified (for example, "amount not traced: no invoice given") when you ask for approval.
5. Only a PASS (or an explained WARN) goes to the human for approval. send-gate does not send anything itself.

## Limits

- It checks facts that can be checked by machine. It does not judge tone, politeness or whether the message should be sent at all
- Quote marks used for labels or emphasis (8 characters or longer) are treated as quotes. Put the label in a source file, or use different brackets
- Amounts are matched by number, not by currency
- `--check-urls` needs network access; a site that blocks bots may report 403

## License

MIT. Copyright (c) 2026 Toru Hosokawa (PHAI).
