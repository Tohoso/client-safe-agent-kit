---
name: preflight-ledger
description: Stops an agent from running an irreversible action (send, delete, deploy, pay, publish) on a hunch. Before acting it must record what would be lost if it is wrong and one concrete check; the ledger runs the check itself against a real file and refuses "go" until it passes, then records how it turned out so the next similar action starts from that lesson.
---

# preflight-ledger

**Stops an agent from sending, deleting, deploying or paying on a hunch: no "go" until it has written down what it would lose and one check has actually passed.**

Agents are confident. "The target is staging", "the client approved this", "the backup exists" get said, not checked, and the action cannot be undone. This skill turns that moment into four short steps the agent cannot skip:

1. **begin** - name the action, *what is lost if this is wrong*, and *the one thing to confirm*, pointing at the evidence file
2. **verify** - the ledger runs the check itself. The agent's own "I checked" is never accepted
3. **go** - allowed only if the last verify passed **and the evidence file has not changed since**. Then the agent performs the real action
4. **close** - record the outcome (`useful`, `harmful`, `false_alarm`, `unknown`) and a one-line note

Before a new action, `search` brings back past entries with similar words, so last month's mistake is in front of the agent before it repeats it.

## When to use

Any action that cannot be taken back, or that leaves your machine:
- sending a message or email to a client, posting publicly
- deleting files, records, branches, backups
- deploying, migrating, changing production settings
- payments, refunds, purchases, subscription changes

Skip it for reversible, local work (editing a draft, running tests). The point is to spend thirty seconds only where a mistake costs a day.

## Install

Copy this folder into your skills directory (for example `~/.claude/skills/preflight-ledger/` or your OpenClaw skills folder). Python 3.9+ and the standard library only.

The ledger is one append-only JSONL file: `.preflight/ledger.jsonl` in the current folder, or set `PREFLIGHT_LEDGER=/path/to/ledger.jsonl` to share one ledger across projects.

## Usage

```bash
python3 scripts/ledger.py search "invoice acme"            # recall first

python3 scripts/ledger.py begin \
  --action "send the October invoice to Acme" --kind send \
  --loss "Acme receives a wrong amount; we look careless and must re-issue" \
  --question "the invoice PDF text says 1,200" \
  --method text_contains --path out/invoice-october.txt --text "1,200"
# -> prints the entry with its id, e.g. pf-20261015-223313-1816

python3 scripts/ledger.py verify pf-20261015-223313-1816   # exit 0 = passed, 1 = failed
python3 scripts/ledger.py go     pf-20261015-223313-1816   # exit 0 = do it now, 2 = refused
# ... perform the real action here ...
python3 scripts/ledger.py close  pf-20261015-223313-1816 --outcome useful --note "amount matched"
python3 scripts/ledger.py stats
```

### Check methods

| method | passes when | typical use |
|---|---|---|
| `file_exists` | the path exists | the backup is really there before deleting the original |
| `text_contains` | the file contains `--text` (whitespace-insensitive) | the invoice says the amount you are about to quote |
| `text_absent` | the file does **not** contain `--text` | the config has no `production` before a test run |
| `quote` | `--text` (8+ chars) appears verbatim in the file | the approval you rely on is really in the email |
| `json_equals` | `--field` (dotted path) equals `--expected` (JSON) | the deploy target is `"staging"` |

The evidence must be a file. If the evidence lives in an API or a web page, save the response to a file first, then check the file. That also leaves a record of what you saw.

## Instructions for the agent

1. Before any irreversible action, run `search` with two or three words of the action. Read what comes back.
2. Run `begin`. The `--loss` is concrete ("the client gets last month's price", not "something might go wrong"). The check is the single thing that, if false, makes the action wrong.
3. Run `verify`. If it fails, fix the cause or stop and tell the human. Do not change the check to make it pass.
4. Run `go`. Only on exit 0 perform the action, immediately, without editing the evidence file in between.
5. When the outcome is known, `close` it. If you decided not to act, close it as `harmful` (the action would have caused harm) or `false_alarm` (the check worried you for nothing), with a note.
6. When asking a human for approval, quote the entry's `loss` and the `verify` result.

## Example

`bash examples/walkthrough.sh` runs a deploy whose config still points at production: verify fails (exit 1), go is refused (exit 2), the config is fixed, verify passes, go is allowed, the entry is closed as `useful`.

## Limits

- It checks one thing per entry, on purpose. If two things must be true, open two entries
- It cannot stop an agent that skips the ledger entirely. Put "begin / verify / go" into the agent's standing instructions for the action types above, or into a pre-action hook
- The search is plain keyword matching over your own entries

## License

MIT. Copyright (c) 2026 Toru Hosokawa (PHAI).
