import json
import os
import sys
from datetime import date

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import send_gate as sg  # noqa: E402


ROSTER = {
    "recipients": [
        {"id": "U111", "name": "Alice Tanaka", "aliases": ["Alice", "Tanaka-san"], "org": "Acme"},
        {"id": "U222", "name": "Bob Sato", "aliases": ["Bob"], "org": "Acme"},
    ]
}


def run(draft, to=None, sources=None, today=date(2026, 10, 15), check_urls=False, prober=None):
    return sg.run_gate(
        draft,
        roster=ROSTER,
        to_ids=to or [],
        sources=sources or [],
        today=today,
        check_urls=check_urls,
        prober=prober,
    )


def verdicts(report, kind):
    return [f["verdict"] for f in report["findings"] if f["kind"] == kind]


# ---- recipients ----------------------------------------------------------

def test_unknown_recipient_id_blocks():
    r = run("Hi Alice, thanks.", to=["U999"])
    assert r["result"] == "BLOCK"
    assert "U999" in " ".join(f["reason"] for f in r["findings"])


def test_known_recipient_passes():
    r = run("Hi Alice, thanks.", to=["U111"])
    assert verdicts(r, "recipient") == ["ok"]
    assert r["result"] == "PASS"


def test_greeting_names_someone_else_blocks():
    # addressed to Alice's ID but the text greets Bob: the classic copy-paste mix-up
    r = run("Hi Bob, here is the file.", to=["U111"])
    assert r["result"] == "BLOCK"
    assert any(f["kind"] == "recipient" and f["verdict"] == "block" for f in r["findings"])


def test_mention_ids_in_text_are_checked_against_roster():
    r = run("<@U111> <@U333> please see below.")
    assert r["result"] == "BLOCK"
    assert any("U333" in f["value"] for f in r["findings"])


# ---- dates ---------------------------------------------------------------

@pytest.mark.parametrize("text", [
    "Let's meet on Monday, October 19, 2026.",
    "Meeting: Mon Oct 19 at 18:00",
    "Due 2026-10-23 (Fri).",
    "10月19日（月）18時から",
    "2026年10月23日(金)まで",
])
def test_correct_weekdays_pass(text):
    r = run(text)
    assert verdicts(r, "date") and all(v == "ok" for v in verdicts(r, "date")), r["findings"]


@pytest.mark.parametrize("text", [
    "Let's meet on Tuesday, October 19, 2026.",
    "Due 2026-10-23 (Thu).",
    "10月19日（火）18時から",
])
def test_wrong_weekday_blocks(text):
    r = run(text)
    assert "block" in verdicts(r, "date")
    assert r["result"] == "BLOCK"


def test_date_without_year_uses_nearest_upcoming():
    # on 2026-12-28, "1月4日（月）" means 2027-01-04, which is a Monday
    r = run("1月4日（月）に伺います", today=date(2026, 12, 28))
    assert verdicts(r, "date") == ["ok"]


# ---- quotes --------------------------------------------------------------

def test_verbatim_quote_passes():
    src = "Customer said: we would like to move the deadline to the end of May."
    r = run('As you said, "we would like to move the deadline to the end of May".', sources=[src])
    assert verdicts(r, "quote") == ["ok"]


def test_paraphrased_quote_blocks():
    src = "Customer said: we would like to move the deadline to the end of May."
    r = run('As you said, "we want to push the deadline to June".', sources=[src])
    assert verdicts(r, "quote") == ["block"]


def test_japanese_quote_whitespace_insensitive():
    src = "担当者「 来週の打ち合わせの資料は前日までに送ってほしい 」"
    r = run("「来週の打ち合わせの資料は前日までに送ってほしい」とのことでした", sources=[src])
    assert verdicts(r, "quote") == ["ok"]


def test_short_scare_quotes_are_ignored():
    r = run('This is the "new" plan.')
    assert verdicts(r, "quote") == []


def test_quote_without_sources_is_warn_not_block():
    r = run('You wrote "please send the invoice by Friday".')
    assert verdicts(r, "quote") == ["warn"]
    assert r["result"] == "WARN"


# ---- amounts -------------------------------------------------------------

def test_amount_found_in_source_passes():
    r = run("The total is $1,200.", sources=["Invoice total: USD 1200"])
    assert verdicts(r, "amount") == ["ok"]


def test_amount_not_in_source_blocks():
    r = run("The total is $1,500.", sources=["Invoice total: USD 1200"])
    assert verdicts(r, "amount") == ["block"]


def test_japanese_man_yen_normalized():
    r = run("費用は48万円です。", sources=["見積 ¥480,000"])
    assert verdicts(r, "amount") == ["ok"]


def test_amount_without_sources_warns():
    r = run("The total is $1,500.")
    assert verdicts(r, "amount") == ["warn"]


# ---- urls ----------------------------------------------------------------

def test_urls_listed_but_unverified_offline():
    r = run("See https://example.com/page.")
    assert [f["value"] for f in r["findings"] if f["kind"] == "url"] == ["https://example.com/page"]
    assert verdicts(r, "url") == ["warn"]


def test_url_probe_ok_and_dead():
    def prober(url):
        return (200, "") if "good" in url else (404, "not found")
    r = run("A https://good.example.org/x B https://bad.example.org/y", check_urls=True, prober=prober)
    assert verdicts(r, "url") == ["ok", "block"]


def test_private_address_is_never_fetched():
    assert sg.is_private_host("127.0.0.1")
    assert sg.is_private_host("10.1.2.3")
    assert sg.is_private_host("192.168.0.5")
    assert not sg.is_private_host("93.184.216.34")


# ---- report and cli ------------------------------------------------------

def test_clean_draft_passes_with_exit_zero(tmp_path, capsys):
    draft = tmp_path / "d.txt"
    draft.write_text("Hi Alice, see you on 2026-10-19 (Mon).", encoding="utf-8")
    roster = tmp_path / "r.json"
    roster.write_text(json.dumps(ROSTER), encoding="utf-8")
    code = sg.main(["--draft", str(draft), "--roster", str(roster), "--to", "U111", "--today", "2026-10-15"])
    assert code == 0
    assert "PASS" in capsys.readouterr().out


def test_block_exits_one_and_json_output(tmp_path, capsys):
    draft = tmp_path / "d.txt"
    draft.write_text("Hi Bob, see you on 2026-10-19 (Tue).", encoding="utf-8")
    roster = tmp_path / "r.json"
    roster.write_text(json.dumps(ROSTER), encoding="utf-8")
    code = sg.main(["--draft", str(draft), "--roster", str(roster), "--to", "U111",
                    "--today", "2026-10-15", "--json"])
    assert code == 1
    out = json.loads(capsys.readouterr().out)
    assert out["result"] == "BLOCK"
    kinds = {f["kind"] for f in out["findings"] if f["verdict"] == "block"}
    assert kinds == {"recipient", "date"}


def test_warn_exits_zero_unless_strict(tmp_path):
    draft = tmp_path / "d.txt"
    draft.write_text("The total is $1,500.", encoding="utf-8")
    assert sg.main(["--draft", str(draft), "--today", "2026-10-15"]) == 0
    assert sg.main(["--draft", str(draft), "--today", "2026-10-15", "--strict"]) == 1


def test_greeting_on_line_after_mentions_is_checked():
    # chat messages often put mentions on their own first line
    r = run("<@U111>\nHi Bob,\nhere is the file.", to=["U111"])
    assert r["result"] == "BLOCK"
    assert any(f["kind"] == "recipient" and f["verdict"] == "block" and f["value"] == "Bob" for f in r["findings"])
