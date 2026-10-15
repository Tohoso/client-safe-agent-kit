import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import trim_check as tc  # noqa: E402


def flags_of(text):
    return [(s["n"], sorted(s["flags"])) for s in tc.analyze(text)["sentences"]]


def test_splits_english_and_japanese_sentences():
    a = tc.split_sentences("Thanks for the file. I will send the draft today! Is Friday OK?")
    assert a == ["Thanks for the file.", "I will send the draft today!", "Is Friday OK?"]
    b = tc.split_sentences("資料をありがとうございます。本日中に下書きを送ります。金曜日でよろしいでしょうか？")
    assert len(b) == 3


def test_flags_known_unrequested_task_offtopic():
    text = (
        "As you know, the meeting is on Friday. "
        "Please note that the room is small. "
        "Could you send the slides by Thursday? "
        "Technically, the projector uses HDMI 2.1. "
        "I will bring the printed copies."
    )
    f = dict(flags_of(text))
    assert f[1] == ["known"]
    assert f[2] == ["unrequested"]
    assert f[3] == ["task"]
    assert f[4] == ["offtopic"]
    assert f[5] == []


def test_japanese_flags():
    text = "ご存知の通り、定例は金曜です。念のため、会場は狭いです。資料は木曜までにお送りいただけますか。厳密には、仕様上の制約があります。印刷物はこちらで用意します。"
    f = dict(flags_of(text))
    assert f[1] == ["known"]
    assert f[2] == ["unrequested"]
    assert f[3] == ["task"]
    assert f[4] == ["offtopic"]
    assert f[5] == []


def test_worksheet_asks_the_question_for_every_sentence():
    ws = tc.worksheet("Thanks. Please note the change.")
    assert ws.count("Would the reader be worse off without this sentence?") == 2
    assert "[unrequested]" in ws


def test_compare_detects_added_sentence():
    before = "Thanks for the file. Please note that the room is small. I will bring copies."
    after = "Thanks for the file. I will bring copies. Could you also confirm the headcount?"
    r = tc.compare(before, after)
    assert r["removed"] == ["Please note that the room is small."]
    assert r["added"] == ["Could you also confirm the headcount?"]
    assert r["ok"] is False


def test_compare_allows_pure_deletion_and_small_edits():
    before = "Thanks for the file. As you know, the meeting is Friday. I will bring the copies."
    after = "Thanks for the file. I will bring copies."
    r = tc.compare(before, after)
    assert r["added"] == []
    assert r["ok"] is True
    assert r["removed"] == ["As you know, the meeting is Friday."]


def test_cli_compare_exit_code(tmp_path, capsys):
    b = tmp_path / "b.txt"; a = tmp_path / "a.txt"
    b.write_text("Thanks. Please note the change. See you.", encoding="utf-8")
    a.write_text("Thanks. See you. Also please pay by Monday.", encoding="utf-8")
    assert tc.main(["compare", str(b), str(a)]) == 1
    assert "ADDED" in capsys.readouterr().out
    a.write_text("Thanks. See you.", encoding="utf-8")
    assert tc.main(["compare", str(b), str(a)]) == 0


def test_cli_scan_json(tmp_path, capsys):
    d = tmp_path / "d.txt"
    d.write_text("Please note the change. See you.", encoding="utf-8")
    assert tc.main(["scan", str(d), "--json"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["sentences"][0]["flags"] == ["unrequested"]
    assert out["flagged"] == 1
