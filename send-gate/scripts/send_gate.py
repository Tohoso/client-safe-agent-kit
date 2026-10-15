#!/usr/bin/env python3
"""send-gate: check an outgoing message against the facts before it leaves.

Stops the five mistakes that make an agent's message embarrassing or harmful
once it is sent: the wrong recipient, a date whose weekday is wrong, a "quote"
the other person never said, a dead link, and an amount nobody can trace.

Standard library only. Exit code 0 = PASS or WARN, 1 = BLOCK (or WARN with --strict).
MIT License. Copyright (c) 2026 Toru Hosokawa (PHAI).
"""
from __future__ import annotations

import argparse
import calendar
import ipaddress
import json
import re
import socket
import sys
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime

# --------------------------------------------------------------------------
# helpers

EN_WEEKDAYS = {
    "mon": 0, "monday": 0, "tue": 1, "tues": 1, "tuesday": 1, "wed": 2, "wednesday": 2,
    "thu": 3, "thur": 3, "thurs": 3, "thursday": 3, "fri": 4, "friday": 4,
    "sat": 5, "saturday": 5, "sun": 6, "sunday": 6,
}
JA_WEEKDAYS = {"月": 0, "火": 1, "水": 2, "木": 3, "金": 4, "土": 5, "日": 6}
EN_MONTHS = {m.lower(): i for i, m in enumerate(calendar.month_abbr) if m}
EN_MONTHS.update({m.lower(): i for i, m in enumerate(calendar.month_name) if m})
EN_MONTHS["sept"] = 9

WD = r"(Mon(?:day)?|Tue(?:s(?:day)?)?|Wed(?:nesday)?|Thu(?:r(?:s(?:day)?)?)?|Fri(?:day)?|Sat(?:urday)?|Sun(?:day)?)"
MON = r"(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|June?|July?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
JWD = r"[（(]\s*([月火水木金土日])(?:曜日?)?\s*[）)]"
EWD_PAREN = r"\(\s*" + WD + r"\.?\s*\)"

DATE_PATTERNS = [
    # Monday, October 19, 2026 / Mon Oct 19
    ("en_wd_first", re.compile(r"\b" + WD + r"\.?,?\s+" + MON + r"\.?\s+(\d{1,2})(?:st|nd|rd|th)?(?:,?\s+(\d{4}))?\b", re.I)),
    # October 19, 2026 (Mon) / Oct 19 (Monday)
    ("en_month_first", re.compile(r"\b" + MON + r"\.?\s+(\d{1,2})(?:st|nd|rd|th)?(?:,?\s+(\d{4}))?\s*" + EWD_PAREN, re.I)),
    # 2026-10-19 (Mon) / 2026/10/19 (月)
    ("iso", re.compile(r"\b(\d{4})[-/](\d{1,2})[-/](\d{1,2})\s*(?:" + EWD_PAREN + r"|" + JWD + r")", re.I)),
    # 2026年10月19日（月） / 10月19日(月)
    ("ja", re.compile(r"(?:(\d{4})\s*年\s*)?(\d{1,2})\s*月\s*(\d{1,2})\s*日\s*" + JWD)),
    # 10/19（月） / 10/19 (Mon)
    ("slash", re.compile(r"(?<![\d/])(\d{1,2})/(\d{1,2})(?![\d/])\s*(?:" + EWD_PAREN + r"|" + JWD + r")", re.I)),
]

QUOTE_PATTERNS = [
    re.compile(r"“([^”\n]{1,600})”"),  # “...”
    re.compile(r'"([^"\n]{1,600})"'),                  # "..."
    re.compile(r"「([^」]{1,600})」"),
    re.compile(r"『([^』]{1,600})』"),
]
MIN_QUOTE_CHARS = 8

URL_RE = re.compile(r"https?://[^\s<>\"'）)」】\]]+")
URL_TRAIL = ".,;:!?。、"

MENTION_PATTERNS = [
    re.compile(r"<@([A-Za-z0-9_]+)>"),   # Slack style
    re.compile(r"\[To:([A-Za-z0-9_]+)\]"),  # bracket style used by some chat tools
]

AMOUNT_PATTERNS = [
    ("man_yen", re.compile(r"(\d+(?:\.\d+)?)\s*万\s*円")),
    ("symbol", re.compile(r"[$€£¥￥]\s?(\d[\d,]*(?:\.\d+)?)")),
    ("code_before", re.compile(r"\b(?:USD|JPY|EUR|GBP|US\$)\s?(\d[\d,]*(?:\.\d+)?)", re.I)),
    ("code_after", re.compile(r"(\d[\d,]*(?:\.\d+)?)\s?(?:USD|JPY|EUR|GBP|dollars?|yen|円)\b", re.I)),
    ("ja_yen", re.compile(r"(\d[\d,]*(?:\.\d+)?)\s?円")),
]
BARE_NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")


def norm(s: str) -> str:
    """NFKC, drop all whitespace. Used for verbatim comparison."""
    s = unicodedata.normalize("NFKC", s)
    return re.sub(r"\s+", "", s)


def to_number(raw: str) -> float | None:
    try:
        return float(raw.replace(",", ""))
    except ValueError:
        return None


def is_private_host(host: str) -> bool:
    """True if host is (or resolves to) a non-public address. Never fetch those."""
    try:
        ip = ipaddress.ip_address(host)
        return not ip.is_global
    except ValueError:
        pass
    try:
        infos = socket.getaddrinfo(host, None)
    except OSError:
        return True  # unresolvable: treat as unsafe, the probe will report it
    for info in infos:
        try:
            if not ipaddress.ip_address(info[4][0]).is_global:
                return True
        except ValueError:
            return True
    return False


def default_prober(url: str, timeout: int = 8) -> tuple[int | None, str]:
    host = urllib.parse.urlparse(url).hostname or ""
    if not host or is_private_host(host):
        return None, "refused: private or unresolvable address"
    headers = {"User-Agent": "send-gate/1.0 (+link check)"}
    for method in ("HEAD", "GET"):
        req = urllib.request.Request(url, method=method, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.status, ""
        except urllib.error.HTTPError as e:
            if method == "HEAD" and e.code in (403, 405, 501):
                continue  # some servers refuse HEAD; retry with GET
            return e.code, str(e.reason)
        except (urllib.error.URLError, OSError) as e:
            return None, str(getattr(e, "reason", e))
    return None, "no response"


# --------------------------------------------------------------------------
# checks

def _roster_index(roster: dict | None) -> dict:
    idx = {}
    for r in (roster or {}).get("recipients", []):
        if r.get("id"):
            idx[str(r["id"])] = r
    return idx


def _names_of(person: dict) -> list[str]:
    names = [person.get("name", "")] + list(person.get("aliases", []))
    first = (person.get("name") or "").split()
    if len(first) > 1:
        names.append(first[0])
    return [n for n in names if n]


def _name_in(text: str, name: str) -> bool:
    if re.fullmatch(r"[\x00-\x7f]+", name):
        return re.search(r"(?<![A-Za-z])" + re.escape(name) + r"(?![A-Za-z])", text) is not None
    return name in text


def check_recipients(text, roster, to_ids, add):
    idx = _roster_index(roster)
    if to_ids and not idx:
        add("recipient", ",".join(to_ids), "warn", "no roster given, recipient IDs not verified")
    for rid in to_ids:
        if not idx:
            break
        if rid in idx:
            add("recipient", rid, "ok", f"matches {idx[rid].get('name', rid)}")
        else:
            add("recipient", rid, "block", f"ID {rid} is not in the roster")
    seen = set(to_ids)
    for pat in MENTION_PATTERNS:
        for m in pat.finditer(text):
            mid = m.group(1)
            if mid in seen or not idx:
                continue
            seen.add(mid)
            if mid in idx:
                add("recipient", m.group(0), "ok", f"mention matches {idx[mid].get('name', mid)}")
            else:
                add("recipient", m.group(0), "block", f"mentioned ID {mid} is not in the roster")
    # greeting zone: the first non-empty line once mention tokens are removed
    if to_ids and idx:
        first = ""
        for line in text.splitlines():
            for pat in MENTION_PATTERNS:
                line = pat.sub("", line)
            if line.strip():
                first = line
                break
        wanted = set()
        for rid in to_ids:
            if rid in idx:
                wanted.update(_names_of(idx[rid]))
        for rid, person in idx.items():
            if rid in to_ids:
                continue
            for n in _names_of(person):
                if n not in wanted and _name_in(first, n):
                    add("recipient", n, "block",
                        f"the greeting names {person.get('name')}, but the message goes to "
                        + ", ".join(idx[r].get("name", r) for r in to_ids if r in idx))
                    break


def _infer_year(month: int, day: int, today: date) -> int | None:
    best = None
    for y in (today.year - 1, today.year, today.year + 1):
        try:
            d = date(y, month, day)
        except ValueError:
            continue
        if best is None or abs((d - today).days) < abs((best - today).days):
            best = d
    return best.year if best else None


def check_dates(text, today, add):
    taken = []
    for kind, pat in DATE_PATTERNS:
        for m in pat.finditer(text):
            if any(s <= m.start() < e for s, e in taken):
                continue
            taken.append((m.start(), m.end()))
            g = m.groups()
            if kind == "en_wd_first":
                wd, mon, day, year = g[0], g[1], g[2], g[3]
            elif kind == "en_month_first":
                mon, day, year, wd = g[0], g[1], g[2], g[3]
            elif kind == "iso":
                year, mon, day, wd = g[0], g[1], g[2], g[3] or g[4]
            elif kind == "ja":
                year, mon, day, wd = g[0], g[1], g[2], g[3]
            else:  # slash
                mon, day, wd, year = g[0], g[1], g[2] or g[3], None
            month = int(mon) if str(mon).isdigit() else EN_MONTHS.get(str(mon).lower().rstrip("."))
            want = JA_WEEKDAYS.get(wd) if wd in JA_WEEKDAYS else EN_WEEKDAYS.get(str(wd).lower().rstrip("."))
            value = m.group(0).strip()
            if month is None or want is None:
                continue
            y = int(year) if year else _infer_year(month, int(day), today)
            try:
                d = date(y, month, int(day)) if y else None
            except ValueError:
                d = None
            if d is None:
                add("date", value, "block", "this date does not exist")
                continue
            actual = calendar.day_name[d.weekday()]
            if d.weekday() == want:
                add("date", value, "ok", f"{d.isoformat()} is a {actual}")
            else:
                add("date", value, "block",
                    f"{d.isoformat()} is a {actual}, not a {calendar.day_name[want]}"
                    + ("" if year else " (year inferred as the nearest one)"))


def check_quotes(text, sources, add):
    pool = [norm(s) for s in sources]
    seen = set()
    for pat in QUOTE_PATTERNS:
        for m in pat.finditer(text):
            q = m.group(1).strip().rstrip(".,。、!！?？")
            if len(q) < MIN_QUOTE_CHARS or q in seen:
                continue
            seen.add(q)
            if not pool:
                add("quote", q, "warn", "no source given, quote not verified")
            elif any(norm(q) in p for p in pool):
                add("quote", q, "ok", "found verbatim in a source")
            else:
                add("quote", q, "block", "not found verbatim in any source: quote it exactly or drop the quote marks")


def extract_amounts(text: str) -> list[tuple[str, float]]:
    out = []
    masked = text
    for kind, pat in AMOUNT_PATTERNS:
        for m in pat.finditer(masked):
            v = to_number(m.group(1))
            if v is None:
                continue
            if kind == "man_yen":
                v *= 10000
            out.append((m.group(0).strip(), v))
        masked = pat.sub(lambda mm: " " * len(mm.group(0)), masked)
    return out


def source_numbers(sources: list[str]) -> set[float]:
    vals = set()
    for s in sources:
        for _, v in extract_amounts(s):
            vals.add(v)
        for m in BARE_NUMBER.finditer(s):
            v = to_number(m.group(0))
            if v is not None:
                vals.add(v)
    return vals


def check_amounts(text, sources, add):
    vals = source_numbers(sources) if sources else set()
    for raw, v in extract_amounts(text):
        if not sources:
            add("amount", raw, "warn", "no source given, amount not traced")
        elif v in vals:
            add("amount", raw, "ok", "the same number appears in a source")
        else:
            add("amount", raw, "block", "this amount does not appear in any source")


def check_links(text, do_check, prober, add):
    seen = []
    for m in URL_RE.finditer(text):
        u = m.group(0).rstrip(URL_TRAIL)
        if u in seen:
            continue
        seen.append(u)
        if not do_check:
            add("url", u, "warn", "not checked (run with --check-urls)")
            continue
        status, err = (prober or default_prober)(u)
        if status is not None and status < 400:
            add("url", u, "ok", f"HTTP {status}")
        else:
            add("url", u, "block", f"HTTP {status}" if status else (err or "unreachable"))


def run_gate(text, *, roster=None, to_ids=(), sources=(), today=None, check_urls=False, prober=None):
    findings = []

    def add(kind, value, verdict, reason=""):
        findings.append({"kind": kind, "value": value, "verdict": verdict, "reason": reason})

    today = today or date.today()
    to_ids = [t for t in to_ids if t]
    check_recipients(text, roster, to_ids, add)
    check_dates(text, today, add)
    check_quotes(text, list(sources), add)
    check_amounts(text, list(sources), add)
    check_links(text, check_urls, prober, add)
    verdicts = {f["verdict"] for f in findings}
    result = "BLOCK" if "block" in verdicts else "WARN" if "warn" in verdicts else "PASS"
    return {"result": result, "findings": findings}



def human_report(report: dict) -> str:
    lines = [f"send-gate: {report['result']}"]
    order = {"block": 0, "warn": 1, "ok": 2}
    for f in sorted(report["findings"], key=lambda f: order[f["verdict"]]):
        lines.append(f"  [{f['verdict'].upper():5}] {f['kind']:9} {f['value']}  - {f['reason']}")
    if report["result"] == "BLOCK":
        lines.append("Do not send. Fix the BLOCK lines, then run again.")
    return "\n".join(lines)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Check an outgoing message before it is sent.")
    ap.add_argument("--draft", required=True, help="file with the message text ('-' for stdin)")
    ap.add_argument("--roster", help="JSON roster: {\"recipients\": [{\"id\", \"name\", \"aliases\"}]}")
    ap.add_argument("--to", action="append", default=[], help="recipient ID (repeat or comma-separate)")
    ap.add_argument("--source", action="append", default=[], help="original text the message relies on (repeatable)")
    ap.add_argument("--today", help="YYYY-MM-DD, for dates written without a year (default: today)")
    ap.add_argument("--check-urls", action="store_true", help="fetch each URL (public addresses only)")
    ap.add_argument("--json", action="store_true", help="print the report as JSON")
    ap.add_argument("--strict", action="store_true", help="treat WARN as a failure (exit 1)")
    a = ap.parse_args(argv)

    text = sys.stdin.read() if a.draft == "-" else open(a.draft, encoding="utf-8").read()
    roster = json.load(open(a.roster, encoding="utf-8")) if a.roster else None
    to_ids = [t.strip() for v in a.to for t in v.split(",") if t.strip()]
    sources = [open(p, encoding="utf-8").read() for p in a.source]
    today = datetime.strptime(a.today, "%Y-%m-%d").date() if a.today else date.today()

    report = run_gate(text, roster=roster, to_ids=to_ids, sources=sources, today=today, check_urls=a.check_urls)
    print(json.dumps(report, ensure_ascii=False, indent=2) if a.json else human_report(report))
    if report["result"] == "BLOCK" or (a.strict and report["result"] == "WARN"):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
