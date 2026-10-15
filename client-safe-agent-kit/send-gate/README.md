# send-gate

Stops an agent from sending a message to the wrong person, with a wrong weekday, a made-up quote, a dead link, or an untraceable amount.

- One Python script, standard library only, 29 tests (`python3 -m pytest tests`)
- Works offline; link checking is opt-in (`--check-urls`) and never touches private addresses
- English and Japanese date formats (`Monday, October 19, 2026`, `2026-10-19 (Mon)`, `10月19日（月）`, `10/19（月）`)
- Exit code 1 on BLOCK, so it fits in any "draft -> check -> approve -> send" pipeline

Quick start:

```bash
python3 scripts/send_gate.py --draft examples/draft_bad.example.txt \
  --roster examples/roster.example.json --to U01ALICE \
  --source examples/source.example.txt --today 2026-11-05
```

See `SKILL.md` for the full instructions and the roster format.

---

# send-gate (日本語)

エージェントが代わりに送るメッセージの、取り返しのつかない 5 つの間違いを送る前に止める skill です。

1. **宛先**: `--to` の ID と本文の `<@ID>` / `[To:ID]` が名簿にあるか。宛先と違う人の名前で挨拶していないか
2. **日付と曜日**: 曜日を添えた日付を全部計算し直す。年が無い日付は一番近い年として扱う
3. **引用**: 鉤括弧や引用符の中の文が、渡した原文 (相手のメール、議事録など) に一字一句あるか。空白と全角半角の違いは無視する
4. **URL**: `--check-urls` を付けると実際に開いて確かめる。社内やローカルのアドレスは開かない
5. **金額**: 書いた金額 ($、¥、円、万円など) が原文 (見積書、請求書) のどこかに数字としてあるか

BLOCK が 1 つでもあれば終了コード 1 で、送ってはいけません。直してもう一度かけます。WARN (原文が無くて確かめられなかった物) は、承認を頼む時に人に伝えます。

名簿は過去のやり取りから写さず、CRM やチャットのメンバー一覧など元の記録から作ってください。過去の便から ID を写すことこそが、この確認で止めたい間違いです。

Python 3.9 以上、標準ライブラリだけで動きます。ライセンスは MIT (Copyright (c) 2026 Toru Hosokawa (PHAI))。
