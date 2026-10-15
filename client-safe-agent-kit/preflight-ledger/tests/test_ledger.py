import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import ledger as lg  # noqa: E402


@pytest.fixture
def L(tmp_path):
    return lg.Ledger(tmp_path / "ledger.jsonl")


def begin(L, **kw):
    args = dict(action="send the invoice email to the client", kind="send",
                loss="client receives a wrong amount and we look careless",
                check={"question": "the invoice file says 1,200", "method": "text_contains",
                       "path": kw.pop("path"), "text": "1,200"})
    args.update(kw)
    return L.begin(**args)


def test_begin_requires_loss_and_check(L, tmp_path):
    with pytest.raises(ValueError):
        L.begin(action="delete old backups", kind="delete", loss="", check={"method": "file_exists", "path": "x"})
    with pytest.raises(ValueError):
        L.begin(action="delete old backups", kind="delete", loss="lose the only copy", check=None)


def test_go_refused_until_check_passes(L, tmp_path):
    inv = tmp_path / "invoice.txt"
    inv.write_text("Total: 1,500", encoding="utf-8")
    e = begin(L, path=str(inv))
    with pytest.raises(lg.NotVerified):
        L.go(e["id"])
    r = L.verify(e["id"])
    assert r["passed"] is False
    with pytest.raises(lg.NotVerified):
        L.go(e["id"])


def test_check_is_run_by_the_ledger_not_self_reported(L, tmp_path):
    inv = tmp_path / "invoice.txt"
    inv.write_text("Total: 1,200", encoding="utf-8")
    e = begin(L, path=str(inv))
    r = L.verify(e["id"])
    assert r["passed"] is True
    assert L.go(e["id"])["status"] == "executed"


def test_file_changed_after_verify_blocks_go(L, tmp_path):
    inv = tmp_path / "invoice.txt"
    inv.write_text("Total: 1,200", encoding="utf-8")
    e = begin(L, path=str(inv))
    L.verify(e["id"])
    inv.write_text("Total: 1,200 (revised to 1,500)", encoding="utf-8")
    with pytest.raises(lg.NotVerified) as ex:
        L.go(e["id"])
    assert "changed" in str(ex.value)


def test_json_equals_and_file_exists(L, tmp_path):
    cfg = tmp_path / "deploy.json"
    cfg.write_text(json.dumps({"target": {"env": "sandbox"}}), encoding="utf-8")
    e = L.begin(action="deploy to the target org", kind="deploy", loss="production changed by mistake",
                check={"question": "target is the sandbox", "method": "json_equals",
                       "path": str(cfg), "field": "target.env", "expected": "sandbox"})
    assert L.verify(e["id"])["passed"] is True
    e2 = L.begin(action="restore from backup", kind="delete", loss="restore overwrites newer data",
                 check={"question": "backup exists", "method": "file_exists", "path": str(tmp_path / "nope.tar")})
    assert L.verify(e2["id"])["passed"] is False


def test_evidence_quote_must_be_verbatim(L, tmp_path):
    mail = tmp_path / "mail.txt"
    mail.write_text("Please go ahead and send it to everyone on Friday.", encoding="utf-8")
    ok = L.begin(action="send the newsletter", kind="send", loss="sent without approval",
                 check={"question": "the owner approved sending", "method": "quote",
                        "path": str(mail), "text": "go ahead and send it"})
    bad = L.begin(action="send the newsletter", kind="send", loss="sent without approval",
                  check={"question": "the owner approved sending", "method": "quote",
                         "path": str(mail), "text": "approved, send now"})
    assert L.verify(ok["id"])["passed"] is True
    assert L.verify(bad["id"])["passed"] is False


def test_close_records_outcome_and_stats(L, tmp_path):
    inv = tmp_path / "invoice.txt"
    inv.write_text("Total: 1,200", encoding="utf-8")
    a = begin(L, path=str(inv))
    L.verify(a["id"]); L.go(a["id"])
    L.close(a["id"], outcome="useful", note="caught nothing, but the check was cheap")
    b = begin(L, path=str(inv), action="send the second invoice")
    L.close(b["id"], outcome="harmful", note="dropped: the check failed and we fixed the amount")
    s = L.stats()
    assert s["total"] == 2
    assert s["by_outcome"]["useful"] == 1
    assert s["by_outcome"]["harmful"] == 1
    assert s["open"] == 0


def test_close_rejects_unknown_outcome(L, tmp_path):
    inv = tmp_path / "invoice.txt"; inv.write_text("1,200", encoding="utf-8")
    e = begin(L, path=str(inv))
    with pytest.raises(ValueError):
        L.close(e["id"], outcome="great")


def test_search_recalls_past_lessons(L, tmp_path):
    inv = tmp_path / "invoice.txt"; inv.write_text("1,200", encoding="utf-8")
    e = begin(L, path=str(inv), action="send the invoice email to Acme")
    L.close(e["id"], outcome="harmful", note="amount was from last month's quote")
    hits = L.search("invoice acme")
    assert hits and hits[0]["id"] == e["id"]
    assert "last month" in hits[0]["note"]


def test_open_entries_listed(L, tmp_path):
    inv = tmp_path / "invoice.txt"; inv.write_text("1,200", encoding="utf-8")
    begin(L, path=str(inv))
    assert len(L.list(status="open")) == 1


def test_ledger_is_append_only_jsonl(L, tmp_path):
    inv = tmp_path / "invoice.txt"; inv.write_text("1,200", encoding="utf-8")
    e = begin(L, path=str(inv))
    L.verify(e["id"]); L.go(e["id"]); L.close(e["id"], outcome="useful")
    lines = (tmp_path / "ledger.jsonl").read_text(encoding="utf-8").splitlines()
    assert [json.loads(x)["event"] for x in lines] == ["begin", "verify", "go", "close"]


def test_cli_go_exit_code(tmp_path, capsys):
    led = str(tmp_path / "l.jsonl")
    inv = tmp_path / "invoice.txt"; inv.write_text("Total: 1,500", encoding="utf-8")
    code = lg.main(["--ledger", led, "begin", "--action", "send invoice", "--kind", "send",
                    "--loss", "wrong amount goes out", "--question", "invoice says 1,200",
                    "--method", "text_contains", "--path", str(inv), "--text", "1,200"])
    assert code == 0
    eid = json.loads(capsys.readouterr().out)["id"]
    assert lg.main(["--ledger", led, "verify", eid]) == 1
    assert lg.main(["--ledger", led, "go", eid]) == 2
    inv.write_text("Total: 1,200", encoding="utf-8")
    assert lg.main(["--ledger", led, "verify", eid]) == 0
    assert lg.main(["--ledger", led, "go", eid]) == 0
