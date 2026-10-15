#!/usr/bin/env python3
"""preflight-ledger: before an irreversible action, write down what you would lose
and the one thing to check; the ledger runs the check itself and refuses "go" until it passes.

Append-only JSONL. Standard library only.
MIT License. Copyright (c) 2026 Toru Hosokawa (PHAI).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import secrets
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

METHODS = ("file_exists", "text_contains", "text_absent", "quote", "json_equals")
OUTCOMES = ("useful", "harmful", "false_alarm", "unknown")
KINDS = ("send", "delete", "deploy", "payment", "publish", "config", "other")
MIN_QUOTE_CHARS = 8


class NotVerified(Exception):
    """Raised when 'go' is asked for an action whose check has not passed (or went stale)."""


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _norm(s: str) -> str:
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", s))


def _fingerprint(path: str) -> str | None:
    p = Path(path)
    if not p.is_file():
        return None
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _get_field(obj, dotted: str):
    cur = obj
    for part in dotted.split("."):
        if isinstance(cur, list) and part.isdigit():
            cur = cur[int(part)]
        elif isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            raise KeyError(dotted)
    return cur


def run_check(check: dict) -> tuple[bool, str]:
    """Run a check against the real file. The caller's opinion is never accepted as a result."""
    method, path = check.get("method"), check.get("path", "")
    p = Path(path)
    if method == "file_exists":
        return (p.exists(), "exists" if p.exists() else "missing")
    if not p.is_file():
        return False, f"file not found: {path}"
    text = p.read_text(encoding="utf-8", errors="replace")
    if method in ("text_contains", "quote"):
        needle = check.get("text", "")
        if method == "quote" and len(needle.strip()) < MIN_QUOTE_CHARS:
            return False, f"quote too short to be evidence (min {MIN_QUOTE_CHARS} chars)"
        found = bool(needle) and _norm(needle) in _norm(text)
        return found, "found verbatim" if found else "not found"
    if method == "text_absent":
        needle = check.get("text", "")
        found = bool(needle) and _norm(needle) in _norm(text)
        return (not found), "absent" if not found else "present"
    if method == "json_equals":
        try:
            value = _get_field(json.loads(text), check.get("field", ""))
        except (json.JSONDecodeError, KeyError, IndexError) as e:
            return False, f"cannot read field: {e}"
        ok = value == check.get("expected")
        return ok, f"{check.get('field')} = {value!r}"
    return False, f"unknown method: {method}"


class Ledger:
    def __init__(self, path):
        self.path = Path(path)

    # ---- storage ---------------------------------------------------------
    def _append(self, row: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    def _events(self):
        if not self.path.exists():
            return []
        return [json.loads(x) for x in self.path.read_text(encoding="utf-8").splitlines() if x.strip()]

    def _entries(self) -> dict:
        entries = {}
        for ev in self._events():
            eid = ev["id"]
            if ev["event"] == "begin":
                entries[eid] = {k: v for k, v in ev.items() if k != "event"} | {"status": "open", "verify": None}
            elif eid in entries:
                e = entries[eid]
                if ev["event"] == "verify":
                    e["verify"] = {k: ev[k] for k in ("passed", "detail", "fingerprint", "at")}
                    e["status"] = "verified" if ev["passed"] else "open"
                elif ev["event"] == "go":
                    e["status"] = "executed"
                    e["executed_at"] = ev["at"]
                elif ev["event"] == "close":
                    e["status"] = "closed"
                    e["outcome"], e["note"], e["closed_at"] = ev["outcome"], ev.get("note", ""), ev["at"]
        return entries

    def _get(self, eid: str) -> dict:
        e = self._entries().get(eid)
        if not e:
            raise KeyError(f"no such entry: {eid}")
        return e

    # ---- actions ---------------------------------------------------------
    def begin(self, *, action: str, kind: str, loss: str, check: dict | None, impact: str = "") -> dict:
        if not (action or "").strip():
            raise ValueError("action is required: what are you about to do?")
        if not (loss or "").strip():
            raise ValueError("loss is required: what do you lose if this turns out to be wrong?")
        if not check or check.get("method") not in METHODS or not check.get("path"):
            raise ValueError(f"check is required: one method of {METHODS} and a path to the evidence")
        if kind not in KINDS:
            raise ValueError(f"kind must be one of {KINDS}")
        eid = datetime.now().strftime("pf-%Y%m%d-%H%M%S-") + secrets.token_hex(2)
        row = {"event": "begin", "id": eid, "at": _now(), "action": action.strip(), "kind": kind,
               "loss": loss.strip(), "impact": impact, "check": check}
        self._append(row)
        return self._get(eid)

    def verify(self, eid: str) -> dict:
        e = self._get(eid)
        passed, detail = run_check(e["check"])
        row = {"event": "verify", "id": eid, "at": _now(), "passed": passed, "detail": detail,
               "fingerprint": _fingerprint(e["check"]["path"])}
        self._append(row)
        return {"id": eid, "passed": passed, "detail": detail}

    def go(self, eid: str) -> dict:
        e = self._get(eid)
        if e["status"] in ("executed", "closed"):
            raise NotVerified(f"{eid} is already {e['status']}")
        v = e.get("verify")
        if not v or not v["passed"]:
            raise NotVerified(f"{eid}: the check has not passed. Run 'verify' and fix what it reports.")
        if v["fingerprint"] != _fingerprint(e["check"]["path"]):
            raise NotVerified(f"{eid}: the evidence file changed after it was verified. Run 'verify' again.")
        self._append({"event": "go", "id": eid, "at": _now()})
        return self._get(eid)

    def close(self, eid: str, *, outcome: str, note: str = "") -> dict:
        if outcome not in OUTCOMES:
            raise ValueError(f"outcome must be one of {OUTCOMES}")
        self._get(eid)
        self._append({"event": "close", "id": eid, "at": _now(), "outcome": outcome, "note": note})
        return self._get(eid)

    # ---- reading ---------------------------------------------------------
    def list(self, status: str | None = None) -> list:
        es = list(self._entries().values())
        return [e for e in es if status is None or e["status"] == status]

    def stats(self) -> dict:
        es = list(self._entries().values())
        by = {o: 0 for o in OUTCOMES}
        for e in es:
            if e["status"] == "closed":
                by[e["outcome"]] += 1
        return {"total": len(es), "open": sum(e["status"] in ("open", "verified") for e in es),
                "executed_not_closed": sum(e["status"] == "executed" for e in es), "by_outcome": by}

    def search(self, query: str, limit: int = 5) -> list:
        words = [w.lower() for w in query.split() if w]
        scored = []
        for e in self._entries().values():
            hay = " ".join([e.get("action", ""), e.get("loss", ""), e.get("note", "") or "",
                            e["check"].get("question", "")]).lower()
            score = sum(w in hay for w in words)
            if score:
                scored.append((score, e.get("closed_at") or "", e))
        scored.sort(key=lambda t: (t[0], t[1]), reverse=True)
        return [t[2] for t in scored[:limit]]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Record loss and one check before an irreversible action.")
    ap.add_argument("--ledger", default=os.environ.get("PREFLIGHT_LEDGER", ".preflight/ledger.jsonl"))
    sub = ap.add_subparsers(dest="cmd", required=True)

    b = sub.add_parser("begin", help="declare the action, what you would lose, and the one check")
    b.add_argument("--action", required=True)
    b.add_argument("--kind", default="other", choices=KINDS)
    b.add_argument("--loss", required=True, help="what is lost if this is wrong")
    b.add_argument("--impact", default="", help="optional: minor / major / severe")
    b.add_argument("--question", default="", help="the one thing to confirm, as a sentence")
    b.add_argument("--method", required=True, choices=METHODS)
    b.add_argument("--path", required=True, help="the evidence file the check reads")
    b.add_argument("--text", default="")
    b.add_argument("--field", default="")
    b.add_argument("--expected", default=None, help="JSON value for json_equals (e.g. '\"sandbox\"' or 'true')")

    for name in ("verify", "go"):
        p = sub.add_parser(name)
        p.add_argument("id")
    c = sub.add_parser("close", help="record how it turned out")
    c.add_argument("id")
    c.add_argument("--outcome", required=True, choices=OUTCOMES)
    c.add_argument("--note", default="")
    li = sub.add_parser("list")
    li.add_argument("--open", action="store_true")
    sub.add_parser("stats")
    s = sub.add_parser("search", help="recall past entries before a similar action")
    s.add_argument("query")

    a = ap.parse_args(argv)
    L = Ledger(a.ledger)
    out = lambda obj: print(json.dumps(obj, ensure_ascii=False, indent=2))  # noqa: E731
    try:
        if a.cmd == "begin":
            expected = a.expected
            if expected is not None:
                try:
                    expected = json.loads(expected)
                except json.JSONDecodeError:
                    pass  # a bare string
            check = {"question": a.question, "method": a.method, "path": a.path}
            if a.text:
                check["text"] = a.text
            if a.field:
                check["field"], check["expected"] = a.field, expected
            out(L.begin(action=a.action, kind=a.kind, loss=a.loss, check=check, impact=a.impact))
            return 0
        if a.cmd == "verify":
            r = L.verify(a.id)
            out(r)
            return 0 if r["passed"] else 1
        if a.cmd == "go":
            out(L.go(a.id))
            return 0
        if a.cmd == "close":
            out(L.close(a.id, outcome=a.outcome, note=a.note))
            return 0
        if a.cmd == "list":
            out(L.list(status="open") if a.open else L.list())
            return 0
        if a.cmd == "stats":
            out(L.stats())
            return 0
        if a.cmd == "search":
            out(L.search(a.query))
            return 0
    except NotVerified as e:
        print(f"NOT VERIFIED: {e}", file=sys.stderr)
        return 2
    except (ValueError, KeyError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 3
    return 3


if __name__ == "__main__":
    sys.exit(main())
