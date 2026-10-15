---
name: reply-trim
description: Stops an agent's client replies from growing padding, unrequested warnings, new asks and technical asides. It flags the four kinds of sentences that usually should go, makes the agent answer "would the reader be worse off without this sentence?" for each one, and then proves the trimmed reply only removed text, so no new request or promise slipped in while editing.
---

# reply-trim

**Stops an agent's replies to clients from carrying sentences the client never needed: recaps, unrequested warnings, new asks, and technical asides. And proves the trimmed reply added nothing new.**

Agent-written replies are long in a specific way. They repeat what the client just said, add "please note" cautions nobody asked for, slip in a task or a deadline for the client, and explain implementation details the client does not care about. Each sentence looks polite; together they make the client do more reading and more work, and they read as machine-written.

This skill removes those sentences with a fixed procedure:

1. **scan** flags the four kinds of sentences that usually should go:

| flag | what it is | example |
|---|---|---|
| `known` | the reader already knows it | "As you know, the kickoff is on Thursday." |
| `unrequested` | a caution or extra they did not ask for | "Please note that the room has no projector." |
| `task` | puts work, a deadline or a condition on them | "Could you send the attendee list by Wednesday?" |
| `offtopic` | technically true, outside their interest | "Technically, our scheduler stores times in UTC." |

2. For **every** sentence (flagged or not) the agent answers one question: *Would the reader be worse off without this sentence?* Every "no" is deleted. Flags are hints; the question decides. A flagged `task` that the reply really needs (the one thing you must ask) stays.
3. **compare** checks the trimmed reply against the original. Each sentence must come from the original (light edits allowed). A new sentence means the agent added an ask or a promise while "trimming", and the check fails.

## When to use

- Every reply to a client, customer or partner that an agent drafts, before it goes to a human for approval
- Especially acknowledgments ("received, thank you"): these should almost never carry a new request or promise

## Install

Copy this folder into your skills directory (for example `~/.claude/skills/reply-trim/` or your OpenClaw skills folder). Python 3.9+ and the standard library only. English and Japanese.

## Usage

```bash
python3 scripts/trim_check.py scan draft.txt               # flags per sentence
python3 scripts/trim_check.py scan draft.txt --worksheet   # yes/no worksheet for every sentence
python3 scripts/trim_check.py compare draft.txt trimmed.txt   # exit 0 = only removed, 1 = text was added
```

## Example

```
$ python3 scripts/trim_check.py scan examples/draft.example.txt
reply-trim: 4 of 8 sentences flagged
   1. [-] Hi Alice,
   2. [-] Thanks for sending the signed order form.
   3. [known] As you know, the kickoff is on Thursday at 3 pm.
   4. [unrequested] Please note that the meeting room has no projector.
   5. [offtopic] Technically, our scheduler stores times in UTC internally.
   6. [task] Could you send the list of attendees by Wednesday?
   7. [-] I will bring the printed agenda.
   8. [-] Best regards,

$ python3 scripts/trim_check.py compare examples/draft.example.txt examples/trimmed_bad.example.txt
reply-trim compare: ADDED TEXT (8 -> 5 sentences)
  ...
  ADDED:   I will bring the printed agenda and a short demo.
  ADDED:   Also, please confirm your budget owner before Thursday.
Trimming must not add sentences. Remove the ADDED lines or get them approved separately.
```

`examples/trimmed.example.txt` is the clean result (8 -> 4 sentences, nothing added). `examples/draft_ja.example.txt` shows the same flags in Japanese.

## Instructions for the agent

1. Run `scan --worksheet` on the draft.
2. Answer the question for every sentence, honestly, from the reader's side. Delete each "no". Keep one `task` only if the reply exists to ask it.
3. Do not rewrite while trimming. If something must be added, that is a new message for the human to approve, not part of the trim.
4. Run `compare` on the original and the trimmed version. On exit 1, remove the added lines.
5. Show the human the trimmed reply, with the removed sentences listed underneath, so they can put one back if it mattered.

## Limits

- The flags are keyword hints in English and Japanese. They miss sentences phrased differently; the per-sentence question is what catches those
- `compare` matches sentences by similarity (80%). A rewrite of a sentence that keeps most words passes; a new sentence does not
- It does not judge tone or correctness. Pair it with a fact check (for example send-gate) before sending

## License

MIT. Copyright (c) 2026 Toru Hosokawa (PHAI).
