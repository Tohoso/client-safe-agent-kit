# Client-Safe Agent Kit

Three small skills (Claude Code / OpenClaw style `SKILL.md` folders) that stop an agent from making the mistakes you cannot take back in front of a client. Python standard library only, 49 tests, MIT.

| Skill | What it stops |
|---|---|
| [send-gate](send-gate/) | Sending to the wrong person, with a wrong weekday, a made-up quote, a dead link, or an untraceable amount |
| [preflight-ledger](preflight-ledger/) | Running an irreversible action (send, delete, deploy, pay, publish) on a hunch, without first writing down what would be lost and one check to run |
| [reply-trim](reply-trim/) | Client replies that grow padding, unrequested warnings, new asks and technical asides |

[client-safe-agent-kit](client-safe-agent-kit/) is the bundle with the recommended order: draft -> reply-trim -> send-gate -> preflight-ledger -> human approval -> send.

## Install

Copy a skill folder into your skills directory (for example `~/.claude/skills/send-gate/`). Each `SKILL.md` has the install line, usage and limits.

## 日本語

エージェントが客先に向けて書き、動く時の、取り返しのつかない間違いを止める 3 本です。各フォルダの README に日本語の説明があります。

Author: Toru Hosokawa (PHAI). License: MIT.
