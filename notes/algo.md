
I am confused overall regarding this problem statement
Sharing my raw thoughts

We = the company providing settlement

We make an offer to creditor where we agree with creditor to pay settlement_pct of current_balance_cents and we agree that first payment date is first_payment_date. (assuming: this should be after first_draft_date)



We charge a program fee overall as program_fee_pct of original_percentage_cents



Creditor has some rules which we have to agree:
- Complete your payment at min(max_terms, max_payments), let called k: 1<=k<=min(max_terms, max_payments)
- Minimum token amount is min_payment_cents which can not be paid to creditor more than max_token_pays times
- even_pays means payment are splitted equally among payments being made to creditor
- bank_fee_cents is actual fixed charge everytime a payment is being made to creditor

we upfront calculate all days at which we have to make payment to creditor and also make sure this falls <= last_draft_date. Lets call it settlement_days

The days where ledge make a payment to us lets call it draft_days

total_offer = settlement_pct * current_balance_cents
We have to always pay to creditor consecutively at codance dates if total_offer is not completed yet.

Right now the algo for even pays shaped and first case only:
we will keep k as max_payments for now and simply pay the amount = total_offer / k (yes adjusting for those remainder case)
and for each payment we will take all remaning money to fee which is max we can get

So we start iterating over dates starting from as_of_date and for each day:
