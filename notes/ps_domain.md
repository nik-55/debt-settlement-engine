Alright.

---

# Part 1 — The three parties

There are **three** separate entities. Most of your confusion comes from the story having three players but me only naming two.

|                            | Who                                                         | What they want                                     |
| -------------------------- | ----------------------------------------------------------- | -------------------------------------------------- |
| **You**                    | the client, in debt                                         | to get out of debt for less than you owe           |
| **The bank**               | the *creditor* — whoever you owe money to                   | to recover as much as possible before you go broke |
| **The settlement company** | the middleman (this is the company you're writing code for) | to get paid a fee for negotiating on your behalf   |

"Creditor" is not a technical term. It just means **the one who is owed**. If you owe your friend $20, your friend is your creditor. Here the creditor is a credit card bank.

The key thing: **there are two separate contracts.**

1. You ↔ the bank (the original credit card agreement)
2. You ↔ the settlement company (the service agreement you sign when you hire them)

Each contract has its own number. That's why there are two balances. Hold that thought.

---

# Part 2 — The full timeline, dated

Concrete story that produces exactly the numbers in `case1`.

### March 2024 — you borrow

You get a credit card and spend **$1,000** on it. Rent, car repair, whatever. This is real money you actually received. Call it the *principal*.

> **This $1,000 is not `creditor_balance_cents`. Coincidence of numbers. Ignore it for now — I'm only mentioning it so you know where the debt physically came from.**

### 2024–2025 — you fall behind

You miss payments. Two things stack on top:

- **Interest** — the card charges maybe 24% a year on the unpaid balance
- **Late fees** — a flat penalty, maybe $35, each month you miss

The balance climbs: $1,000 → $1,050 → $1,110 → and so on. This is the part you correctly said: *"bank will keep adding interest every single month."* Yes. At this stage, exactly right.

### November 2025 — you hire the settlement company

You give up on paying it yourself. You call a debt settlement company. On the day you sign their contract, they ask the bank (or read your statement) for the current balance.

**It says $1,200.**

They write that number into your service agreement and it never changes again.

> ### ➜ **This $1,200 is `original_balance_cents = 120000`.**
> It is the balance **on the day you enrolled in the program**.

### Why $1,200 is frozen — answering your question directly

You asked: *"why is it $1,200 frozen, the bank will keep adding interest every month?"*

Because **$1,200 is not the bank's number anymore.** It stopped being a live debt figure the moment it was copied into your contract with the settlement company.

Think of it like this. The settlement company's fee is 25%. Of what? They have to pick something, and it has to be **fixed at signing** — otherwise:

- if the fee were 25% of the *live growing* balance, the company would earn more the longer they stall. That's a perverse incentive and regulators ban it.
- and you'd have signed a contract where you don't know what you'll be charged. Nobody signs that.

So the number is snapshotted. `original_balance_cents` is a **price tag**, not a debt. The bank has no idea it exists. It could say `service_fee_basis_cents` and nothing would change.

**$1,200 exists for exactly one purpose:** `0.25 × $1,200 = $300`. That's the company's fee. That's it. That's the entire job of that field.

### Late 2025 — the account charges off

Now the other half of your question: *does interest really keep growing every month, forever?*

**No.** Here's what actually happens.

After roughly 180 days of you not paying, the bank does something called a **charge-off**: it declares the debt a loss on its own accounting books. Legally you still owe it, but on the bank's internal books it's now worth $0.

At charge-off, **interest and fees typically stop accruing.** The account is dead. Nobody is running the interest calculator on it anymore. It gets parked, sold to a debt buyer, or handed to a collections department.

So the growth is not infinite. It grows while the account is alive and delinquent, then it freezes when the bank gives up on it. That's the piece nobody told you.

### January 2026 — the bank quotes a settlement figure

The settlement company calls the collections department. Collections pulls the file and says:

> "Balance is $1,200. But we'll drop the accrued late fees and penalty interest — that's $200 of junk we tacked on. **Call it $1,000.** We'll take 50% of that. **Pay us $500 and the account is closed.**"

> ### ➜ **This $1,000 is `creditor_balance_cents = 100000`.**
> It is what the creditor asserts you owe **right now, at the moment of negotiation**.
>
> ### ➜ **50% is `settlement_pct = 0.5`.**
> ### ➜ **$500 is the "offer total"** — `0.5 × $1,000`. This is the money the bank actually receives.

Waiving penalty fees is the first thing a creditor does in a settlement negotiation — those fees cost them nothing to give up, and it makes the offer look generous. That's why the current balance came *down* from $1,200 to $1,000 rather than up.

---

# Part 3 — Straight answer on the two numbers

You asked: *do I take a loan of $1,000 or $1,200?*

**Neither is a loan amount.** Both are balances at different moments, used by different people, for different math:

```
$1,000  ← what you originally spent on the card (backstory only, never appears in the code)

$1,200  ← original_balance_cents
          balance on ENROLLMENT DAY, frozen into your contract with the SETTLEMENT COMPANY
          used ONLY for:  fee = 25% × $1,200 = $300

$1,000  ← creditor_balance_cents
          balance TODAY as stated by the BANK during negotiation
          used ONLY for:  payoff = 50% × $1,000 = $500
```

These two never touch each other. They live in different formulas, in service of different contracts. If you swapped them, the client would be overcharged and the bank underpaid, and nothing in the program would crash — which is precisely why the take-home gave them different values.

**And here's the blunt engineering truth:** the reason `case1` has 120000 and 100000 rather than the same number is so that if you use the wrong field, the output is visibly wrong. The backstory above is plausible and real, but the take-home author picked two numbers mainly to make bugs detectable. Don't burn energy justifying the gap.

---

# Part 4 — Why the bank takes $500 instead of $1,000

Credit card debt is **unsecured** — nothing backs it. No car to repossess, no house to foreclose on. If you don't pay, the bank cannot take anything.

Their options and what each is worth:

| Option                       | Realistic outcome                                                                                                                                |
| ---------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------ |
| Keep calling you             | You have no money. $0.                                                                                                                           |
| Sue you                      | Costs them lawyers and months. They win a judgment — a piece of paper saying you owe. If you're broke, it collects nothing. Net: often negative. |
| Sell the debt to a collector | Charged-off paper sells for roughly **4–10 cents on the dollar**. On $1,000, that's $40–$100.                                                    |
| **Take $500 now**            | **$500, guaranteed, today, zero further cost.**                                                                                                  |

That's why. **$500 guaranteed beats $80 from a debt buyer, and beats a lawsuit against someone with nothing.** Banks have entire departments doing this and they price it in from the start.

And yes — they *could* sue, that's a real risk in this business. But by the time an account is charged off and in settlement talks, the bank has already concluded suing isn't worth it for this account.

---

# Part 5 — The escrow account: how the money physically moves

You can't hand the bank $500 — you don't have $500. So the settlement company sets up an account for you.

**`case1/client.json`, field by field:**

```jsonc
"draft_amount_cents": 20000     // you deposit $200 into the account, monthly
"draft_day": 1                  // on the 1st of each month
"first_draft_date": "2026-01-01"// first deposit
"last_draft_date":  "2026-07-01"// last deposit — this is also the HORIZON, the deadline
"as_of_date":       "2025-12-31"// "today" — the moment you're running the calculation
"current_balance_cents": 0      // the account is empty right now
"ledger": [ ...7 credits of $200... ]  // the deposits, already scheduled
```

- **Escrow account** (the assignment calls it the **SDA**) — a bank account in your name, but the settlement company controls what leaves it. You feed it; they pay out of it.
- **Draft** — one monthly deposit. $200. Called a "draft" because it's auto-drafted from your checking account.
- **Ledger** — the list of money movements on that account. `credit` = money in. `debit` = money out.
- **Horizon** — `last_draft_date`, here **2026-07-01**. Nothing can be scheduled after this. It's the program's end date.

Seven deposits, Jan 1 through Jul 1 2026, $200 each = **$1,400 total will ever enter this account.**

---

# Part 6 — What has to come OUT of that account

Three different things, three different recipients:

```
$500   →  the bank         (the settlement:  50% × $1,000)
$300   →  the company      (the program fee: 25% × $1,200)   ← their revenue
$10    →  the bank's wire desk, EVERY TIME a payment is sent  ← pure cost
```

**`case1/creditor_rules.json`:**

```jsonc
"program_fee_pct": 0.25   // company fee = 25% × original_balance = $300
"bank_fee_cents": 1000    // $10 wire fee per payment sent
"max_terms": 6            // at most 6 installments...
"max_payments": 6         // ...same cap, stated twice (the assignment admits this is redundant)
"min_payment_cents": 2500 // each installment must be ≥ $25
"even_pays": true         // all installments must be EQUAL
"is_ballooning_allowed": false  // no "tiny payments then one huge one at the end"
```

Two things are called "fee" and they are completely different:

- **Program fee ($300)** — the settlement company's paycheck. This is what your employer earns. The entire optimization objective in this assignment is *get this money as early as possible.*
- **Bank fee ($10)** — a wire transfer charge. Nobody earns it. It's friction. Charged only on dates where money actually goes to the creditor — a date with only fee collection and no creditor payment costs $0.

---

# Part 7 — The actual cash flow, month by month

**Money in** — deposits, on the **1st** of each month:
Jan 1, Feb 1, Mar 1, Apr 1, May 1, Jun 1, Jul 1 — $200 each.

**Money out** — payments to the creditor start on `first_payment_date: 2026-01-31`, then recur monthly. Because Jan 31 is the last day of January, the cadence is **true end-of-month**:

`Jan 31 → Feb 28 → Mar 31 → Apr 30 → May 31 → Jun 30 → Jul 31`

But the horizon is **Jul 1**, so **Jul 31 is off the table**. Six usable dates.

### ⚠️ The trap hiding here

Deposits land on the **1st**. Payments go out on the **month-end**. Different rhythms — that's why the assignment insists you simulate date by date instead of thinking in "months."

And notice: the **Jul 1 deposit of $200 arrives, but there is no payment date left after it.** Jun 30 is the final usable date. So that $200 lands in the account and can never be spent. **Only $1,200 of the $1,400 is actually usable.** This is exactly the "money that arrives too late to be useful" the assignment warns about in §8.

### Running it with 6 equal payments

$500 ÷ 6 = $83.33..., so in cents: `50000 / 6 = 8333` with 2 left over. Remainder goes on the **latest** payments to keep the sequence non-decreasing → `8333, 8333, 8333, 8333, 8334, 8334`.

| Date       | In    | To bank | Wire fee | Company fee taken | Balance | Fee still owed |
| ---------- | ----- | ------- | -------- | ----------------- | ------- | -------------- |
| Jan 1      | +$200 |         |          |                   | $200    | $300           |
| **Jan 31** |       | $83.33  | $10      | **$106.67**       | $0      | $193.33        |
| Feb 1      | +$200 |         |          |                   | $200    |                |
| **Feb 28** |       | $83.33  | $10      | **$106.67**       | $0      | $86.66         |
| Mar 1      | +$200 |         |          |                   | $200    |                |
| **Mar 31** |       | $83.33  | $10      | **$86.66**        | $20.01  | **$0 ✓**       |
| Apr 1      | +$200 |         |          |                   | $220.01 |                |
| **Apr 30** |       | $83.33  | $10      | —                 | $126.68 |                |
| May 1      | +$200 |         |          |                   | $326.68 |                |
| **May 31** |       | $83.34  | $10      | —                 | $233.34 |                |
| Jun 1      | +$200 |         |          |                   | $433.34 |                |
| **Jun 30** |       | $83.34  | $10      | —                 | $340.00 |                |

Bank gets exactly $500. Company gets its full $300 **by March 31**. Balance never goes below zero. **Feasible.**

Compare: if you'd chosen only **3** payments instead of 6, each would be ~$166.67, eating most of each month's $200 — and the company's $300 wouldn't be fully collected until **May 31**, two months later. **Smaller creditor payments early = more room for your fee early.** That's the entire economic intuition behind the assignment, and it's why the shape of the payment schedule "falls out of" the objective instead of being hard-coded.

---

# Part 8 — One repo bug to know about

`ASSIGNMENT.md` §3 says the offer's balance field was renamed to **`creditor_balance_cents`**. But the actual file on disk, `cases/case1_feasible_even/offer.json`, still uses the old name **`current_balance_cents`**. Check what `feasibility/models.py` actually reads before you trust either — the docs and the data disagree.

---

**In one sentence:** you owe a bank money it will never fully collect, so it agrees to take half; a middleman company collects your $200/month into a controlled account, pays the bank in installments out of it, and takes its own $300 fee — priced off a *frozen* balance from the day you signed up — as early as the rules allow; your job is to decide whether that account can cover all of it without ever hitting empty.