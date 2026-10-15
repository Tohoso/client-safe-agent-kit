# Client-Safe Agent Kit

reply-trim + send-gate + preflight-ledger: keeps an agent that writes and acts for you from making the mistakes you cannot take back in front of a client. Standard library Python, 49 tests, MIT. Start with `SKILL.md`.

---

# Client-Safe Agent Kit (日本語)

エージェントが客先に向けて書き、動く時の、取り返しのつかない間違いを止める 3 本の skill の束です。

- **reply-trim**: 返信から相手に要らない文 (分かっていること、頼まれていない注意、相手への作業、関心の外の指摘) を削り、削った版に新しい依頼や約束が入っていないかを確かめる
- **send-gate**: 宛先、曜日、引用、URL、金額を送る前に原文と照合し、合わなければ止める
- **preflight-ledger**: 送信・削除・デプロイ・支払いの前に、外れた時に失う物と確かめる 1 点を書かせ、確かめが通るまで実行を許さない

使う順は、下書き → reply-trim → send-gate → preflight-ledger → 人の承認 → 送信・実行。エージェントへの常設の指示の例は SKILL.md にあります。

Python 3.9 以上、標準ライブラリだけ。ライセンスは MIT (Copyright (c) 2026 Toru Hosokawa (PHAI))。
