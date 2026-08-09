import logging
import math
import datetime

from feasibility.models import Client, CreditorRules, LedgerEntry, Offer
from feasibility.engine import Result, ScheduleRow, AdditionalFunds, FundsOption

logger = logging.getLogger()
logger.setLevel(logging.INFO)


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
    min_payment_tiers: list[tuple[int, int]],
    pay_shape: str,
    max_segments: int,
):
    remaining_max_token_pays = max_token_pays
    last_pay = None

    active_tier_index = -1

    unique_pays = set()

    for i, pay in enumerate(creditor_payments):
        unique_pays.add(pay)
        if pay == min_payment_cents:
            if remaining_max_token_pays > 0:
                remaining_max_token_pays -= 1
            else:
                return False
        if pay < min_payment_cents:
            return False

        if len(min_payment_tiers) > (active_tier_index + 1) and min_payment_tiers[
            active_tier_index + 1
        ][0] <= (i + 1):
            active_tier_index += 1

        if active_tier_index != -1 and min_payment_tiers[active_tier_index][1] > pay:
            return False

        if last_pay is not None and (last_pay > pay):
            return False

        last_pay = pay

    if sum(creditor_payments) != total_offer:
        return False

    if pay_shape == "staircase":
        if len(unique_pays) > max_segments:
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
            rules.min_payment_tiers,
            pay_shape,
            rules.max_segments,
        ):
            return []

        return creditor_payments

    elif pay_shape == "balloon":
        creditor_payments = []

        remaining_max_token_pays = rules.max_token_pays
        remaining_creditor_amount = total_offer

        active_index_tier = -1

        for i in range(k - 1):
            if len(rules.min_payment_tiers) > (
                active_index_tier + 1
            ) and rules.min_payment_tiers[active_index_tier + 1][0] <= (i + 1):
                active_index_tier += 1

            if active_index_tier != -1:
                min_payment_cents = rules.min_payment_tiers[active_index_tier][1]
            elif remaining_max_token_pays > 0:
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
            rules.min_payment_tiers,
            pay_shape,
            rules.max_segments,
        ):
            return []

        return creditor_payments
    elif pay_shape == "staircase":
        if rules.max_segments == 1:
            creditor_payments = calculate_creditor_payments(
                k, "even", total_offer, rules
            )

            if not validate_payments(
                creditor_payments,
                rules.min_payment_cents,
                rules.max_token_pays,
                total_offer,
                rules.min_payment_tiers,
                pay_shape,
                rules.max_segments,
            ):
                return []

            return creditor_payments
        else:
            m_max = max(0, min(k - 2, rules.max_token_pays))

            for m in range(m_max, -1, -1):
                creditor_payments = []

                remaining_creditor_amount = total_offer
                active_index_tier = -1

                for i in range(m):
                    if len(rules.min_payment_tiers) > (
                        active_index_tier + 1
                    ) and rules.min_payment_tiers[active_index_tier + 1][0] <= (i + 1):
                        active_index_tier += 1

                    min_payment_cents = rules.min_payment_cents

                    if active_index_tier != -1:
                        min_payment_cents = rules.min_payment_tiers[active_index_tier][
                            1
                        ]

                    amount_to_paid = min(min_payment_cents, remaining_creditor_amount)
                    creditor_payments.append(amount_to_paid)
                    remaining_creditor_amount -= amount_to_paid

                    if remaining_creditor_amount == 0:
                        break

                if remaining_creditor_amount > 0:
                    k_second_segment = k - len(creditor_payments)
                    if k_second_segment == 0:
                        continue

                    base_amount = remaining_creditor_amount // k_second_segment
                    remaining_cents = remaining_creditor_amount % k_second_segment

                    if remaining_cents > 0:
                        continue

                    minimum_base_amount = 0

                    for i in range(len(creditor_payments), k):
                        if len(rules.min_payment_tiers) > (
                            active_index_tier + 1
                        ) and rules.min_payment_tiers[active_index_tier + 1][0] <= (
                            i + 1
                        ):
                            active_index_tier += 1

                        if active_index_tier != -1:
                            minimum_base_amount = max(
                                minimum_base_amount,
                                rules.min_payment_tiers[active_index_tier][1],
                            )

                    if (
                        base_amount < minimum_base_amount
                    ) or base_amount < rules.min_payment_cents:
                        continue

                    creditor_payments += [base_amount] * k_second_segment

                if not validate_payments(
                    creditor_payments,
                    rules.min_payment_cents,
                    rules.max_token_pays,
                    total_offer,
                    rules.min_payment_tiers,
                    pay_shape,
                    rules.max_segments,
                ):
                    continue

                return creditor_payments

            return []


def simulate_movement_days(
    k: int,
    pay_shape_used: str,
    total_offer: int,
    rules: CreditorRules,
    cadence_dates: list[datetime.date],
    client: Client,
    program_fee: int,
    movement_days: list[int],
    date_to_draft_map: dict,
):
    creditor_payments = calculate_creditor_payments(
        k, pay_shape_used, total_offer, rules
    )

    if not creditor_payments:
        return []

    date_to_creditor_amount_map = {
        cadence_dates[i]: payment for i, payment in enumerate(creditor_payments)
    }

    current_escor_balance = client.current_balance_cents
    program_fee_remaining = program_fee

    rows = []
    for date in movement_days:
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
                    logger.debug(
                        f"[CREDIT] {draft.amount_cents}. Total: {current_escor_balance}"
                    )
                elif draft.type == "debit":
                    if (current_escor_balance - draft.amount_cents) < 0:
                        return []

                    current_escor_balance -= draft.amount_cents
                    logger.debug(
                        f"[DEBIT] {draft.amount_cents}. Total: {current_escor_balance}"
                    )

        if date in cadence_dates:
            amount_to_creditor = (
                date_to_creditor_amount_map[date]
                if date in date_to_creditor_amount_map
                else 0
            )
            bank_fee = 0
            if amount_to_creditor > 0:
                bank_fee = rules.bank_fee_cents

            remaining_amount = current_escor_balance - (amount_to_creditor + bank_fee)

            if remaining_amount < 0:
                return []

            program_fee_part = min(remaining_amount, program_fee_remaining)
            program_fee_remaining -= program_fee_part

            current_escor_balance -= amount_to_creditor + bank_fee + program_fee_part

            logger.debug(
                f"[DEBIT]: Creditor {amount_to_creditor} Bank fee: {bank_fee} program_fee_part: {program_fee_part}"
            )

            if amount_to_creditor != 0 or program_fee_part != 0:
                rows.append(
                    ScheduleRow(
                        date=date,
                        creditor_payment_cents=amount_to_creditor,
                        program_fee_cents=program_fee_part,
                        bank_fee_cents=bank_fee,
                        balance_cents=current_escor_balance,
                    )
                )

    if program_fee_remaining != 0:
        return []

    return rows


def loop_over_k(
    k_max: int,
    pay_shape_used: str,
    total_offer: int,
    rules: CreditorRules,
    cadence_dates: list[datetime.date],
    client: Client,
    program_fee: int,
    ledger: list[LedgerEntry],
):
    date_to_draft_map: dict[datetime.date, list[LedgerEntry]] = {}

    for draft in ledger:
        if draft.date > client.as_of_date:
            date_to_draft_map.setdefault(draft.date, [])
            date_to_draft_map[draft.date].append(draft)

    movement_days = cadence_dates + list(date_to_draft_map.keys())
    movement_days = list(sorted(set(movement_days)))

    logger.debug(f"Movement days: {movement_days}")

    for k in range(k_max, 0, -1):
        schedule = simulate_movement_days(
            k=k,
            pay_shape_used=pay_shape_used,
            total_offer=total_offer,
            rules=rules,
            cadence_dates=cadence_dates,
            client=client,
            program_fee=program_fee,
            movement_days=movement_days,
            date_to_draft_map=date_to_draft_map,
        )

        if schedule:
            return schedule

    return []


def minimum_lump_finder(
    k_max: int,
    pay_shape_used: str,
    total_offer: int,
    rules: CreditorRules,
    cadence_dates: list[datetime.date],
    client: Client,
    program_fee: int,
    bank_fee_cents: int,
):
    lump_date = client.as_of_date + datetime.timedelta(days=1)

    low = 0
    high = total_offer + program_fee + k_max * bank_fee_cents

    ans = None

    while low <= high:
        mid = (low + high) // 2
        schedule = loop_over_k(
            k_max=k_max,
            pay_shape_used=pay_shape_used,
            total_offer=total_offer,
            rules=rules,
            cadence_dates=cadence_dates,
            client=client,
            program_fee=program_fee,
            ledger=client.ledger + [LedgerEntry(lump_date, mid, "credit")],
        )

        if schedule:
            ans = mid, lump_date
            high = mid - 1
        else:
            low = mid + 1

    if ans is not None:
        return ans

    return None


def get_modified_ledger(client: Client, x: int):
    modified_ledger = []
    num_futures = 0

    for l in client.ledger:
        if l.date > client.as_of_date and l.type == "credit":
            amount_cents = l.amount_cents + x
            num_futures += 1
        else:
            amount_cents = l.amount_cents

        modified_ledger.append(
            LedgerEntry(
                date=l.date,
                amount_cents=amount_cents,
                type=l.type,
            )
        )

    return modified_ledger, num_futures


def minimum_increment_finder(
    k_max: int,
    pay_shape_used: str,
    total_offer: int,
    rules: CreditorRules,
    cadence_dates: list[datetime.date],
    client: Client,
    program_fee: int,
    bank_fee_cents: int,
):
    low = 0
    high = total_offer + program_fee + k_max * bank_fee_cents

    ans = None

    while low <= high:
        mid = (low + high) // 2

        modified_ledger, num_futures = get_modified_ledger(
            client=client,
            x=mid,
        )

        schedule = loop_over_k(
            k_max=k_max,
            pay_shape_used=pay_shape_used,
            total_offer=total_offer,
            rules=rules,
            cadence_dates=cadence_dates,
            client=client,
            program_fee=program_fee,
            ledger=modified_ledger,
        )

        if schedule:
            ans = mid, num_futures
            high = mid - 1
        else:
            low = mid + 1

    if ans is not None:
        return ans

    return None


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

    logger.info(
        f"Total Offer: {total_offer}, Program Fee: {program_fee}, horizon: {horizon_date}"
    )

    cadence_dates = get_cadence_date_range(first_payment_date, k_max)
    cadence_dates = [c for c in cadence_dates if c <= horizon_date]
    k_max = len(cadence_dates)

    logger.info(f"k_max: {k_max}")

    if k_max == 0:
        return Result(
            feasible=False,
            additional_funds=None,
        )

    if rules.even_pays:
        pay_shape_used = "even"
    elif rules.is_ballooning_allowed:
        pay_shape_used = "balloon"
    else:
        pay_shape_used = "staircase"

    schedule = loop_over_k(
        k_max=k_max,
        pay_shape_used=pay_shape_used,
        total_offer=total_offer,
        rules=rules,
        cadence_dates=cadence_dates,
        client=client,
        program_fee=program_fee,
        ledger=client.ledger,
    )

    if schedule:
        return Result(feasible=True, schedule=schedule, pay_shape_used=pay_shape_used)

    lump_finder_output = minimum_lump_finder(
        k_max=k_max,
        pay_shape_used=pay_shape_used,
        total_offer=total_offer,
        rules=rules,
        cadence_dates=cadence_dates,
        client=client,
        program_fee=program_fee,
        bank_fee_cents=rules.bank_fee_cents,
    )

    lump_fund_option = None

    if lump_finder_output is not None:
        min_lump, lump_date = lump_finder_output
        lump_cap = round_half_up(0.65 * total_offer)
        within_guardrail = min_lump <= lump_cap
        lump_fund_option = FundsOption(
            amount_cents=min_lump,
            date=lump_date,
            within_guardrail=within_guardrail,
            reason=(
                f"Lump of {min_lump} is within the guardrail of {lump_cap} cents"
                if within_guardrail
                else f"Lump of {min_lump} exceeds the guardrail of {lump_cap} cents"
            ),
        )

    increment_finder_output = minimum_increment_finder(
        k_max=k_max,
        pay_shape_used=pay_shape_used,
        total_offer=total_offer,
        rules=rules,
        cadence_dates=cadence_dates,
        client=client,
        program_fee=program_fee,
        bank_fee_cents=rules.bank_fee_cents,
    )

    increment_fund_option = None

    if increment_finder_output is not None:
        min_increment, num_futures = increment_finder_output
        increment_cap = max(10_000, round_half_up(0.40 * client.draft_amount_cents))
        within_guardrail = min_increment <= increment_cap

        increment_fund_option = FundsOption(
            amount_cents=min_increment,
            within_guardrail=within_guardrail,
            num_drafts=num_futures,
            reason=(
                f"Increment of {min_increment} is within {increment_cap} cents"
                if within_guardrail
                else f"Increment of {min_increment} exceeds {increment_cap} cents"
            ),
        )

    if lump_fund_option is not None or increment_fund_option is not None:
        return Result(
            feasible=False,
            additional_funds=AdditionalFunds(
                lump_sum=lump_fund_option,
                monthly_increment=increment_fund_option,
            ),
        )

    return Result(
        feasible=False,
        additional_funds=None,
    )
