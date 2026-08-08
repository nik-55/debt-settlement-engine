import math
import datetime

from feasibility.models import Client, CreditorRules, Offer
from feasibility.engine import Result, ScheduleRow


def round_half_up(x: float | int):
    fraction = x - int(x)
    if fraction < 0.5:
        return math.floor(x)
    else:
        return math.ceil(x)


def get_last_day_in_month(year, month):
    first_day = datetime.date(year, month, 1)
    iter_day = first_day

    while (iter_day + datetime.timedelta(days=1)).month == month:
        iter_day = iter_day + datetime.timedelta(days=1)

    return iter_day.day


def next_month(d: datetime.date, is_last_day_celing, anchor_day):
    if d.month == 12:
        year, month = d.year + 1, 1
    else:
        year, month = d.year, d.month + 1

    last_day_of_month = get_last_day_in_month(year, month)

    if is_last_day_celing:
        return datetime.date(year, month, last_day_of_month)

    return datetime.date(year, month, min(anchor_day, last_day_of_month))


def get_cadence_dates(offer: Offer, k_max: int):
    cadence_dates = []
    first_payment_date = offer.first_payment_date
    iter_date = first_payment_date
    i = 0

    is_last_day_ceiling = (
        get_last_day_in_month(first_payment_date.year, first_payment_date.month)
        == first_payment_date.day
    )

    anchor_day = first_payment_date.day

    while i < k_max:
        i += 1
        cadence_dates.append(iter_date)
        iter_date = next_month(iter_date, is_last_day_ceiling, anchor_day)

    return cadence_dates


def calculate_even_pay_payments(total_offer: int, k: int):
    base_amount = total_offer // k
    remaining_cents = total_offer % k

    creditor_payments = [base_amount] * k

    for i in range(remaining_cents):
        creditor_payments[k - 1 - i] += 1

    print(f"Creditor payments: {creditor_payments}")

    return creditor_payments


def evaluate_offer_pipeline(
    client: Client, offer: Offer, rules: CreditorRules
) -> Result:
    total_offer = round_half_up(offer.current_balance_cents * offer.settlement_pct)
    program_fee = round_half_up(offer.original_balance_cents * rules.program_fee_pct)

    k_max = min(rules.max_terms, rules.max_payments)
    cadence_dates = get_cadence_dates(offer, k_max)

    date_to_draft_map = {}

    for draft in client.ledger:
        date_to_draft_map[draft.date] = draft

    movement_days = cadence_dates + list(date_to_draft_map.keys())
    movement_days = sorted(movement_days)

    print(f"Movement days: {movement_days}")

    if rules.even_pays:
        creditor_payments = calculate_even_pay_payments(total_offer, k_max)
        pay_shape_used = "even"
    elif rules.is_ballooning_allowed:
        pass
    else:
        pay_shape_used = "staircase"
        if rules.max_segments >= 2:
            creditor_payments = [rules.min_payment_cents] * rules.max_token_pays

            remaining_k = k_max - rules.max_token_pays
            amount_rem_to_creditor = total_offer - sum(creditor_payments)

            remaining_payments = calculate_even_pay_payments(
                amount_rem_to_creditor, remaining_k
            )
            creditor_payments += remaining_payments

    date_to_creditor_amount_map = {
        cadence_dates[i]: payment for i, payment in enumerate(creditor_payments)
    }

    current_escor_balance = client.current_balance_cents
    program_fee_remaining = program_fee

    rows = []
    for date in movement_days:
        if date in date_to_creditor_amount_map:
            amount_to_creditor = date_to_creditor_amount_map[date]
            bank_fee = 0
            if amount_to_creditor > 0:
                bank_fee = rules.bank_fee_cents

            remaining_amount = current_escor_balance - (amount_to_creditor + bank_fee)

            p_fee = min(remaining_amount, program_fee_remaining)
            program_fee_remaining -= p_fee

            current_escor_balance -= amount_to_creditor + bank_fee + p_fee

            print(
                f"Debited: Creditor {amount_to_creditor} Bank fee: {bank_fee} p_fee: {p_fee}"
            )
            rows.append(
                ScheduleRow(
                    date=date,
                    creditor_payment_cents=amount_to_creditor,
                    program_fee_cents=p_fee,
                    bank_fee_cents=bank_fee,
                    balance_cents=current_escor_balance,
                )
            )
        elif date in date_to_draft_map:
            draft = date_to_draft_map[date]
            current_escor_balance += draft.amount_cents
            print(f"Credited {draft.amount_cents}. Total: {current_escor_balance}")

    result = Result(feasible=True, schedule=rows, pay_shape_used=pay_shape_used)
    return result
