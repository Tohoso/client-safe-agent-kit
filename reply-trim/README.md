# reply-trim

Stops an agent's replies to clients from carrying sentences the client never needed (recaps, unrequested warnings, new asks, technical asides), and proves the trimmed reply added nothing new.

- `scan` flags `known` / `unrequested` / `task` / `offtopic` sentences (English and Japanese)
- `scan --worksheet` makes the agent answer "Would the reader be worse off without this sentence?" for every sentence
- `compare` exits 1 if the trimmed reply contains a sentence that was not in the original
- One Python script, standard library only, 8 tests (`python3 -m pytest tests`)

Full instructions in `SKILL.md`.

---

# reply-trim (日本語)

エージェントが書く客先への返信から、相手に要らない文を削る skill です。

削る候補は 4 種です。
1. **known**: 相手も分かっていること (「ご存知の通り」、相手の言葉の繰り返し)
2. **unrequested**: 頼まれていない注意や付け足し (「念のため」)
3. **task**: 相手に作業・期限・条件を課す一文 (「〜までにお送りいただけますか」)
4. **offtopic**: 技術的には正しいが、相手の関心から外れた指摘 (「仕様上」)

印はあくまで手掛かりです。1 文ずつ「この文が無いと相手が困るか」を問い、困らない文を消します。最後に `compare` で、削った版に元に無い文 (新しい依頼や約束) が入っていないかを機械で確かめます。受領の返事に新しい依頼や約束を足さない、という使い方に特に効きます。

Python 3.9 以上、標準ライブラリだけ。ライセンスは MIT (Copyright (c) 2026 Toru Hosokawa (PHAI))。
