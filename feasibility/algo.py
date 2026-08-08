import math
import datetime

from feasibility.models import Client, CreditorRules, LedgerEntry, Offer
from feasibility.engine import Result, ScheduleRow, AdditionalFunds, FundsOption


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


def get_cadence_date_range(first_payment_date: datetime.date, num_of_months: int):
    cadence_dates = []
    iter_date = first_payment_date
    i = 0

    is_last_day_ceiling = (
        get_last_day_in_month(first_payment_date.year, first_payment_date.month)
        == first_payment_date.day
    )

    anchor_day = first_payment_date.day

    while i < num_of_months:
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


def get_default_first_payment_date(first_draft_date: datetime.date) -> datetime.date:
    year = first_draft_date.year
    month = first_draft_date.month
    last_day = get_last_day_in_month(year, month)
    return datetime.date(year, month, last_day)


def validate_payments(
    creditor_payments: list[int],
    min_payment_cents: int,
    max_token_pays: int,
    total_offer: int,
):
    remaining_max_token_pays = max_token_pays
    last_pay = None
    for pay in creditor_payments:
        if pay == min_payment_cents:
            if remaining_max_token_pays > 0:
                remaining_max_token_pays -= 1
            else:
                return False
        if pay < min_payment_cents:
            return False

        if last_pay is not None and (last_pay > pay):
            return False

        last_pay = pay

    if sum(creditor_payments) != total_offer:
        return False

    return True


def calculate_creditor_payments(
    k: int, pay_shape: str, total_offer: int, rules: CreditorRules
):
    if pay_shape == "even":
        base_amount = total_offer // k
        remaining_cents = total_offer % k

        creditor_payments = [base_amount] * k

        for i in range(remaining_cents):
            creditor_payments[k - 1 - i] += 1

        if not validate_payments(
            creditor_payments,
            rules.min_payment_cents,
            rules.max_token_pays,
            total_offer,
        ):
            return []

        return creditor_payments

    elif pay_shape == "balloon":
        creditor_payments = []

        remaining_max_token_pays = rules.max_token_pays
        remaining_creditor_amount = total_offer

        for i in range(k - 1):
            if remaining_max_token_pays > 0:
                min_payment_cents = rules.min_payment_cents
                remaining_max_token_pays -= 1
            else:
                min_payment_cents = rules.min_payment_cents + 1

            amount_to_paid = min(min_payment_cents, remaining_creditor_amount)
            creditor_payments.append(amount_to_paid)
            remaining_creditor_amount -= amount_to_paid

            if remaining_creditor_amount == 0:
                break

        if remaining_creditor_amount > 0:
            creditor_payments.append(remaining_creditor_amount)

        if not validate_payments(
            creditor_payments,
            rules.min_payment_cents,
            rules.max_token_pays,
            total_offer,
        ):
            return []

        return creditor_payments
    elif pay_shape == "staircase":
        if rules.max_segments == 1:
            return calculate_creditor_payments(k, "even", total_offer, rules)
        else:
            creditor_payments = []

            remaining_max_token_pays = rules.max_token_pays
            remaining_creditor_amount = total_offer

            for i in range(k):
                if remaining_max_token_pays > 0:
                    min_payment_cents = rules.min_payment_cents
                    remaining_max_token_pays -= 1
                else:
                    break

                amount_to_paid = min(min_payment_cents, remaining_creditor_amount)
                creditor_payments.append(amount_to_paid)
                remaining_creditor_amount -= amount_to_paid

                if remaining_creditor_amount == 0:
                    break

            if rules.max_segments > 2:
                next_index = len(creditor_payments)
                min_payment_cents = rules.min_payment_cents + 1

                for i in range(next_index, k - 1):
                    amount_to_paid = min(min_payment_cents, remaining_creditor_amount)
                    creditor_payments.append(amount_to_paid)
                    remaining_creditor_amount -= amount_to_paid

                    if remaining_creditor_amount == 0:
                        break

            if remaining_creditor_amount > 0:
                k_second_segment = k - len(creditor_payments)
                if k_second_segment == 0:
                    return []

                base_amount = remaining_creditor_amount // k_second_segment
                remaining_cents = remaining_creditor_amount % k_second_segment

                if remaining_cents > 0:
                    return []

                creditor_payments += [base_amount] * k_second_segment

            if not validate_payments(
                creditor_payments,
                rules.min_payment_cents,
                rules.max_token_pays,
                total_offer,
            ):
                return []

            return creditor_payments


def evaluate_offer_pipeline(
    client: Client, offer: Offer, rules: CreditorRules
) -> Result:
    total_offer = round_half_up(offer.current_balance_cents * offer.settlement_pct)
    program_fee = round_half_up(offer.original_balance_cents * rules.program_fee_pct)

    k_max = min(rules.max_terms, rules.max_payments)
    horizon_date = client.last_draft_date
    first_payment_date = offer.first_payment_date or get_default_first_payment_date(
        client.first_draft_date
    )

    print(
        f"Total Offer: {total_offer}, Program Fee: {program_fee}, horizon: {horizon_date}"
    )

    cadence_dates = get_cadence_date_range(first_payment_date, k_max)
    cadence_dates = [c for c in cadence_dates if c <= horizon_date]
    k_max = len(cadence_dates)

    print(f"k_max: {k_max}")

    date_to_draft_map: dict[datetime.date, list[LedgerEntry]] = {}

    for draft in client.ledger:
        if draft.date > client.as_of_date:
            date_to_draft_map.setdefault(draft.date, [])
            date_to_draft_map[draft.date].append(draft)

    movement_days = cadence_dates + list(date_to_draft_map.keys())
    movement_days = list(sorted(set(movement_days)))

    print(f"Movement days: {movement_days}")

    if k_max == 0:
        return Result(
            feasible=False,
            additional_funds=None,
        )

    if rules.even_pays:
        creditor_payments = calculate_even_pay_payments(total_offer, k_max)
        pay_shape_used = "even"
    elif rules.is_ballooning_allowed:
        pay_shape_used = "balloon"
        token_used = rules.max_token_pays - 1
        creditor_payments = [rules.min_payment_cents] * token_used

        remaining_k = k_max - token_used
        amount_rem_to_creditor = total_offer - sum(creditor_payments)

        remaining_payments = calculate_even_pay_payments(
            amount_rem_to_creditor, remaining_k
        )
        creditor_payments += remaining_payments
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

        if date in date_to_draft_map:
            drafts = date_to_draft_map[date]
            drafts = sorted(
                drafts,
                key=lambda x: int(x.type == "credit"),
                reverse=True,
            )

            for draft in drafts:
                if draft.type == "credit":
                    current_escor_balance += draft.amount_cents
                    print(
                        f"Credited {draft.amount_cents}. Total: {current_escor_balance}"
                    )
                elif draft.type == "debit":
                    current_escor_balance -= draft.amount_cents
                    print(
                        f"Debited {draft.amount_cents}. Total: {current_escor_balance}"
                    )

    result = Result(feasible=True, schedule=rows, pay_shape_used=pay_shape_used)
    return result
