#!/usr/bin/env python3
"""reply-trim: find the sentences a client reply does not need, and prove the trimmed
version only removed things (no new asks or promises slipped in).

scan     - split a draft into sentences and flag the four kinds that usually should go
compare  - check a trimmed draft against the original: every sentence must come from it

Standard library only. MIT License. Copyright (c) 2026 Toru Hosokawa (PHAI).
"""
from __future__ import annotations

import argparse
import difflib
import json
import re
import sys
import unicodedata

QUESTION = "Would the reader be worse off without this sentence?"

KINDS = {
    "known": "the reader already knows this (recap, 'as you know', restating their own words)",
    "unrequested": "a caution or extra the reader did not ask for ('please note', 'just in case')",
    "task": "puts work, a deadline or a condition on the reader",
    "offtopic": "technically true but outside what the reader cares about",
}

PATTERNS = {
    "known": re.compile(
        r"\bas you know\b|\bas (?:you )?(?:mentioned|discussed|noted)\b|\bas you are aware\b|"
        r"\bjust to recap\b|\bto reiterate\b|"
        r"ご存[知じ]の(?:通り|とおり)|先日お伝えした(?:通り|とおり)|改めてになりますが|繰り返しになりますが",
        re.I),
    "unrequested": re.compile(
        r"\bplease note\b|\bnote that\b|\bjust a (?:quick )?reminder\b|\bfriendly reminder\b|\bbe careful\b|"
        r"\bmake sure\b|\bkeep in mind\b|\bbe aware\b|\bjust in case\b|"
        r"念のため|ご注意|お気をつけ|ご留意|お忘れなく",
        re.I),
    "task": re.compile(
        r"\bcould you\b|\bcan you\b|\bwould you\b|"
        r"\bplease (?:send|confirm|check|reply|review|provide|fill|sign|pay|update|submit|prepare)\b|"
        r"\byou(?:'ll| will)? need to\b|\byou (?:must|should)\b|"
        r"\bby (?:monday|tuesday|wednesday|thursday|friday|saturday|sunday|tomorrow|eod|end of)\b|"
        r"いただけますか|いただけますでしょうか|(?<!よろしく)お願い(?:します|いたします)|ください(?!ませ)|までに",
        re.I),
    "offtopic": re.compile(
        r"\btechnically\b|\bstrictly speaking\b|\bunder the hood\b|\binternally\b|\bimplementation detail|"
        r"厳密には|技術的には|仕様上|内部的には",
        re.I),
}

SPLIT = re.compile(r"(?<=[.!?])\s+|(?<=[。！？])")
MATCH_RATIO = 0.8


def split_sentences(text: str) -> list[str]:
    parts = []
    for block in text.splitlines():
        parts.extend(p.strip() for p in SPLIT.split(block))
    return [p for p in parts if p]


def flags_for(sentence: str) -> list[str]:
    return [k for k, pat in PATTERNS.items() if pat.search(sentence)]


def analyze(text: str) -> dict:
    sents = [{"n": i + 1, "text": s, "flags": flags_for(s)} for i, s in enumerate(split_sentences(text))]
    return {"sentences": sents, "flagged": sum(1 for s in sents if s["flags"]), "total": len(sents)}


def worksheet(text: str) -> str:
    a = analyze(text)
    lines = ["# reply-trim worksheet", "",
             "Answer the question for every sentence. Delete each 'no'. Flags are hints, not verdicts.", ""]
    for s in a["sentences"]:
        tag = " ".join(f"[{f}]" for f in s["flags"])
        lines.append(f"{s['n']}. {s['text']} {tag}".rstrip())
        lines.append(f"   - {QUESTION} yes / no")
    lines += ["", "Flags:"] + [f"- [{k}] {v}" for k, v in KINDS.items()]
    return "\n".join(lines)


def _key(s: str) -> str:
    s = unicodedata.normalize("NFKC", s).lower()
    s = re.sub(r"[^\w\s]", "", s)
    return re.sub(r"\s+", " ", s).strip()


def _best(s: str, pool: list[str]) -> float:
    k = _key(s)
    return max((difflib.SequenceMatcher(None, k, _key(p)).ratio() for p in pool), default=0.0)


def compare(before: str, after: str) -> dict:
    b, a = split_sentences(before), split_sentences(after)
    added = [s for s in a if _best(s, b) < MATCH_RATIO]
    removed = [s for s in b if _best(s, a) < MATCH_RATIO]
    return {"ok": not added, "added": added, "removed": removed, "before": len(b), "after": len(a)}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Trim a client reply and prove nothing new was added.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("scan", help="flag sentences that usually should go")
    s.add_argument("draft")
    s.add_argument("--json", action="store_true")
    s.add_argument("--worksheet", action="store_true", help="print a yes/no worksheet for every sentence")
    c = sub.add_parser("compare", help="check the trimmed version only removed or lightly edited sentences")
    c.add_argument("before")
    c.add_argument("after")
    c.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)

    read = lambda p: sys.stdin.read() if p == "-" else open(p, encoding="utf-8").read()  # noqa: E731
    if a.cmd == "scan":
        text = read(a.draft)
        if a.worksheet:
            print(worksheet(text))
        elif a.json:
            print(json.dumps(analyze(text), ensure_ascii=False, indent=2))
        else:
            r = analyze(text)
            print(f"reply-trim: {r['flagged']} of {r['total']} sentences flagged")
            for x in r["sentences"]:
                mark = ",".join(x["flags"]) if x["flags"] else "-"
                print(f"  {x['n']:>2}. [{mark}] {x['text']}")
        return 0
    r = compare(read(a.before), read(a.after))
    if a.json:
        print(json.dumps(r, ensure_ascii=False, indent=2))
    else:
        print(f"reply-trim compare: {'OK' if r['ok'] else 'ADDED TEXT'} ({r['before']} -> {r['after']} sentences)")
        for x in r["removed"]:
            print(f"  removed: {x}")
        for x in r["added"]:
            print(f"  ADDED:   {x}")
        if not r["ok"]:
            print("Trimming must not add sentences. Remove the ADDED lines or get them approved separately.")
    return 0 if r["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
