# Blind MCP usability test: 20 questions

Server: `https://api.vitalyreznik.com/mcp`. It reported itself as `ztl-judge` version `c7e6f19`. Run on 2026-09-29.
All documents sent and the judge's key fields are in `results.json`. Every attempt is kept, including rejected ones.

## 1. Connection

- **Client:** curl with JSON-RPC 2.0, one POST per call. The session had no native MCP client for this server.
- **First try: blocked.** The sandbox's outbound proxy refused `CONNECT api.vitalyreznik.com:443` with HTTP 403. The cause was the cloud environment's network policy, not the server. After the user added the domain to the allowlist, every call went through.
- **Server behaviour:**
  - `initialize` answered with plain `application/json`, not SSE.
  - No `Mcp-Session-Id` header was issued, and later calls worked without one.
  - I did not send `notifications/initialized`, and nothing complained.
- **Requests made:** initialize ×1, tools/list ×1, language ×1, examples ×1, judge ×25, for 29 in total. No rate-limit errors. No transport or JSON-RPC errors.
- **Judge rejections:** 3 attempts came back `ok:false`. That was 2 × `E_TOOBIG` on Q12 and 1 × `E_NO_VALUE` on Q10. One attempt on Q10 was accepted but answered the wrong question (see Friction §1).

## 2. Results

Verdict/disposition is from the attempt I used, which is the last one. For numeric claims the verdict comes from `report.numeric`, because `report.judge` was empty (see §4).

| id | verdict / disposition | answer to the user (one line) |
|----|----|----|
| Q01 | F OPEN | Not yet: the lawyer approved, but payment is unconfirmed. Open, not refuted. |
| Q02 | T EARNED | Да, допустить можно: обучение и допуск подтверждены. |
| Q03 | T EARNED | Yes: passed tests alone suffice, and the missing QA doesn't matter. |
| Q04 | Z OPEN + passport PARADOX (permanent) | No consistent truth value: it's the liar paradox. |
| Q05 | F OPEN | Нет, вывод не обоснован: «после» подтверждено, «из-за» — нет. |
| Q06 | F REFUTED | No: it arrived two days late. |
| Q07 | Z OPEN | Unknown: nothing establishes it. Audit them or get references. |
| Q08 | T EARNED | Да, формально соблюдено: правило «оплата → отгрузка» не запрещает отгрузку без оплаты. |
| Q09 | T EARNED (numeric) | Yes: 1500 ≤ 2000 EUR. |
| Q10 | Z OPEN (numeric) | Unknown until the amount is known. It fits only if it is ≤ 2000 EUR. |
| Q11 | F REFUTED | No: the March incident report refutes "never loses data". |
| Q12 | F REFUTED | Нет: нагрузочный тест не пройден. |
| Q13 | F REFUTED | No: "locked and not locked" is a contradiction. |
| Q14 | T EARNED | Yes: invoice verified and CFO authorised. |
| Q15 | T EARNED (numeric) | Да: при 85 ≤ 90 правило ничего не требует. |
| Q16 | Z OPEN + passport UNDERDETERMINED | Неизвестно: оба варианта согласованы, нужна внешняя проверка. |
| Q17 | F OPEN | Not established: check either the backup or the snapshot. |
| Q18 | T EARNED | Yes: the account passed KYC, so "unverified" is false. |
| Q19 | F REFUTED | Нет: третьей подписи нет. |
| Q20 | F OPEN | Depends only on stock: payment is fine and credit was refused. Check stock. |

## 3. Friction: unclear or misleading text, and places I had to guess

1. **`value: "?"` means "solve for this", not "unknown" (Q10). This one is the most serious.**
   - `language` says: *"a number, an interval [0,10], or ? for unknown"*.
   - What happened: I wrote the unknown invoice amount as `"?"`. The judge came back with **T EARNED**, `solved: line ∈ (-inf, 2000]`, `next_check: ["narrow line further (still a box)"]`. It solved for the value that would make the claim true and reported the claim as established. The honest answer is "unknown".
   - The real meaning only shows up in an error hint, which I got after removing the value: *"give it a number, an interval [0,10], or ? if 'line' is what the question asks for"*.
   - I had to guess `"[0,inf]"`. Nothing documents that `inf` is accepted. That attempt gave the correct Z OPEN.
   - A user who reads only `language` will get a confident, wrong "yes".
2. **The atom limit is described as a name limit (Q12).**
   - `language` says `"max_names": 10`.
   - The error says: *"12 plain atoms in the formulas … capped at 10 (rows are NOT capped — split the question instead)"*.
   - Wrapping the conjunction in a `defined` row did not help: `Tr(x)` reads count too ("13 plain atoms").
   - *"split the question"* is vague. A 12-way AND cannot be split into two documents without combining the results by hand.
   - I aggregated the 11 logged checks into one verified row. That loses per-check traceability.
3. **Connective syntax is not documented.**
   - `language` lists no operators. I learned `~ & -> not() = == <= Tr()` from `examples`.
   - **`|` for OR never appears anywhere.** I guessed it for Q03, Q17 and Q20, and it was accepted.
   - Comparison with a bare literal (`score > 90`, Q15) was a guess too.
   - Why grounds use `Tr(name)` while claims use the bare `name` is never explained.
4. **Numeric verdicts are not where the tool description points.**
   - The `judge` description says it returns *"The verdict with its disposition and grade"*.
   - For numeric claims (Q09, Q10, Q15), `report.judge` is `{}` even though `applies.judge` is `true`. The verdict is in `report.numeric`.
   - Unexplained fields there: `lazy`, `sheet`, `solved`, and `"credit"` in the sheet.
5. **An internal name leaks (Q10).** `numeric.unverified: ["nc1"]`. There is no row `nc1`, and nothing tells you what it is.
6. **"verify" is advised where verification is impossible (Q04, Q16).**
   - Q04: `why` says *"not established — verify ['L'] (it could still turn either way)"*. But `L` is a `defined` paradox, and the same report says `credit: UNREDEEMABLE` and passport *"refusal PERMANENT"*. Both "verify" and "could still turn either way" are wrong here.
   - Q16: the passport says *"refusal until stipulation"*, but "stipulation" is never defined. It appears only as an `ask` option.
7. **No verdict without a claim (Q04).** Every paradox example in `examples` has no `claim`. Sent that way, the judge did not apply: `applies.judge:false`, passport only. The `initialize` instructions ("Put the formula itself in the claim for a T/F verdict") helped, but copying an example gives no verdict.
8. **F OPEN vs Z OPEN.** The same "unknown" comes out as `F OPEN` for compound claims (Q01, Q17, Q20) and as `Z OPEN` for a single name (Q07). The docs do warn (*"do not report it as false"*). Still, the letter F for "not established" is a trap for any reader who skims.
9. **`refuted` vs `unverified` for "not done / absent" (Q12, Q19).** Nothing helps decide whether "the load test was not run" or "the third signature is missing" is `refuted` (on the log / scan) or `unverified`. I chose `refuted`, and the answer depends on that choice.
10. **Material implication is not flagged (Q08).** `paid -> shipped` with shipped verified is T EARNED. That is correct as logic. But an everyday "if paid, ship" often means "only if", and the tool gives no hint about which one it reads.
11. **Fields with no visible effect or explanation:**
    - `dimension` (evidence/authority) and `ground_kind` (act/certificate) changed nothing I could see (Q02, Q13, Q14).
    - Unexplained output: `back_reading_facts.claim_bypassed_passport: true` (on every document), and `ledger.brackets` / `ledger.naming`.
    - `language` offers `ask` options, then says *"`ask` does not narrow it here"*.
12. **No guidance on causal questions (Q05).** Nothing shows how to encode "X happened after Y, therefore Y caused X". I chose `after -> caused`. The verdict depends on that choice.

## 4. Rule breaks

- **Repository files:** none opened besides the two output files.
- **Websites / search:** nothing read about ZTL, ZFL, zero-trust logic or the author, and no web search. I read only the cloud platform's own help text about network settings and the local proxy status JSON.
- **Incidental repository metadata:** to create the branch I ran `git status`, `git branch -a` and `git log --oneline -1`. The last one printed the head commit subject: *"examples: contingent liar world A - g is the grass, not Curry's sentence"*. That concerns an example I had already seen through the server. I also noticed that its hash, `c7e6f19`, equals the server's `serverInfo.version`. This is not a file read, but it is repository content, so I am reporting it.
