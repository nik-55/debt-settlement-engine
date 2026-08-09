# Scheduling Engine

We have designed an engine that finds the schedule from the rules, offer and drafts given by the client. If no feasible schedule exists, we have to suggest the optimal extra payment that makes scheduling possible, either as a lump sum or as a monthly increment.

When we say schedule, we mean the schedule of payments to the creditor.

There are three shapes given: Even, Balloon and Staircase.

The core objective is to find the schedule that collects the program fee as early as possible.

## The core pipeline

The core pipeline works as follows:

- We calculate the total offer to be paid to the creditor.
- No payment to the program or creditor can be made once the horizon date has passed.
- k is the number of times a payment is made, either to the creditor or just to the program. `1 <= k <= k_max`
- We loop from k_max down to 1. Why reverse? Because a higher k indirectly implies that the payment to the creditor is distributed over more payments, and hence we collect the payment fee early.
- For each k we simulate the movement of credits and debits. If a schedule is found we return it, otherwise we continue with a lower k.

## Inside Simulation (for a given k)

- We first calculate the creditor_payments vector, that is, the payments to be made to the creditor. This vector must obey the constraints: the sum must be total_offer, it must be non decreasing, and it must respect max_token_pays and minimum tiers.
- Then we iterate over all movement_days.

For each day:

- We first check whether there is a credit from the client, and if so we increase the balance. If there is a debit from the client, we decrease the balance.
- Then we check whether the day falls in cadence_dates. If it does, we take the amount to be paid to the creditor from the creditor_payments vector, and then greedily pay the program fee from the remaining amount. We record that day in the schedule along with how much goes to whom.

This gives us a list of scheduled days, and we end the simulation by returning the valid schedule for the given k.

## Inside calculate_creditor_payments

- If the shape is even, distribute the total offer equally over k, handling the remaining cents.
- If the shape is balloon, fill the payment vector up to k-1 with min_payment_cents limited by max_token_pays, then start filling with min_payment_cents + 1 cents. The last payment in the vector takes all the remaining money.
- If the shape is staircase and only one segment is allowed, then for k-2 it is almost the same as the even shape (a staircase requires at least two payments of the same amount, otherwise it becomes a balloon). If more segments are allowed, fill with min_payment_cents limited by max_token_pays, and then distribute the remaining payments evenly.

## When the schedule is infeasible

If there is no valid schedule and hence the schedule is infeasible, we have to find:

- **Minimum lump amount:** the amount that can be credited on a given date so that a valid schedule does exist.
  We assume the lump amount payment is made at `lump_date = as_of_date + 1`.
  Low is the minimum lump amount, high is the maximum lump amount (equal to the entire payment required).
  We do a binary search over low and high to find the minimum lump amount that, added as a new ledger entry at lump_date, makes a valid schedule. If it exists, we also check the guardrail condition on the minimum lump amount.

- **Minimum increment amount:** how much can be added to future drafts so that a valid schedule is possible.
  Low is the minimum lump amount, high is the maximum lump amount (equal to the entire payment required). We do a binary search over low and high to find the increment x to future drafts that makes a valid schedule possible. If it exists, we check the guardrail condition on minimum_increment over future drafts.

We suggest minimum_lump_amount and minimum_increment_amount that make a valid schedule possible.
