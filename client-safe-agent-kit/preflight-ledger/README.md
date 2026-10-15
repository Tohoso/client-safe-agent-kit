# preflight-ledger

Stops an agent from sending, deleting, deploying or paying on a hunch: no "go" until it has written down what it would lose and one check has actually passed.

- `begin` (action, loss, one check) -> `verify` (the ledger runs the check) -> `go` (refused unless it passed and the evidence did not change) -> `close` (outcome and lesson)
- `search` recalls similar past entries before the next action
- One Python script, standard library only, 12 tests (`python3 -m pytest tests`), append-only JSONL ledger

Try it: `bash examples/walkthrough.sh`. Full instructions in `SKILL.md`.

---

# preflight-ledger (日本語)

取り消せない操作 (送信、削除、デプロイ、支払い、公開) を、エージェントが思い込みで実行するのを止める skill です。

1. **begin**: 何をするか、外れていた時に失う物、確かめる 1 点 (根拠のファイル) を書く
2. **verify**: 確かめは ledger 自身がファイルを読んで実行する。エージェントの「確認しました」は受け付けない
3. **go**: 直前の verify が通り、根拠のファイルがその後変わっていない時だけ許可する。許可が出てから実際の操作をする
4. **close**: 結果 (useful / harmful / false_alarm / unknown) と 1 行の教訓を残す

次に似た操作をする前に `search` で過去の記録を引くので、前回の失敗が目の前に出てから動けます。

Python 3.9 以上、標準ライブラリだけ。記録は追記だけの JSONL 1 本です。ライセンスは MIT (Copyright (c) 2026 Toru Hosokawa (PHAI))。
