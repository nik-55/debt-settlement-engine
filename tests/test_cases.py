"""Example expectations for the four provided cases.

These FAIL until you implement feasibility/engine.py::evaluate_offer. Treat them
as the minimum bar — your own test suite should go well beyond these. They do not
pin an exact schedule (several valid schedules may exist); they assert the
verdict, the pay shape, and the Part 2 minima.
"""

from __future__ import annotations

import copy
from typing import Optional

from feasibility.engine import Result, ScheduleRow, evaluate_offer
from feasibility.models import Client, CreditorRules, LedgerEntry, Offer, load_case
from feasibility.utils import (
    round_half_up,
    get_cadence_date_range,
    get_default_first_payment_date,
)


# Assumptions:
# No payments, including fee payments, are possible beyond the cadence dates.
# If even_pays is True: then the shape is even, and vice versa.
# elIf is_balloon_allowed is True: then the shape is balloon, and vice versa.
# else neither even_pays nor is_balloon_allowed is True: then the shape must be staircase, and vice versa.
def _is_feasible_result_valid(
    result: Result,
    client: Client,
    offer: Offer,
    rules: CreditorRules,
):
    assert result.feasible is True

    schedule = result.schedule
    assert schedule is not None
    assert len(schedule) > 0

    schedule: list[ScheduleRow] = list(sorted(result.schedule, key=lambda x: x.date))
    assert len(schedule) == len(set([s.date for s in schedule]))

    first_payment_date = offer.first_payment_date or get_default_first_payment_date(
        client.first_draft_date
    )
    assert schedule[0].date == first_payment_date

    pay_shape_used = result.pay_shape_used

    if pay_shape_used == "even":
        assert rules.even_pays is True
    elif pay_shape_used == "balloon":
        assert rules.even_pays is False
        assert rules.is_ballooning_allowed is True
    elif pay_shape_used == "staircase":
        assert rules.even_pays is False
        assert rules.is_ballooning_allowed is False
    else:
        raise AssertionError(f"Pay shaped is invalid {pay_shape_used}")

    total_offer = round_half_up(offer.current_balance_cents * offer.settlement_pct)
    program_fee = round_half_up(offer.original_balance_cents * rules.program_fee_pct)
    k_max = min(rules.max_terms, rules.max_payments)

    assert k_max >= len(schedule)

    creditor_amount_collected = 0
    program_fee_collected = 0

    prev_creditor_payment = 0
    creditor_payments_unqiue = set()

    cadence_dates = get_cadence_date_range(
        first_payment_date,
        num_of_months=k_max,
    )
    cadence_dates = [c for c in cadence_dates if c <= client.last_draft_date]

    remaining_token_pays = rules.max_token_pays
    active_tier_index = -1

    is_creditor_payment_collected = creditor_amount_collected == total_offer

    min_payment_tiers = sorted(rules.min_payment_tiers, key=lambda x: (x[0], x[1]))

    for i, sr in enumerate(schedule):
        assert sr.balance_cents >= 0

        if sr.date not in cadence_dates:
            raise AssertionError(
                f"{sr.date} is not present in cadence_dates: {cadence_dates}"
            )

        creditor_payment_cents = sr.creditor_payment_cents
        program_fee_cents = sr.program_fee_cents
        bank_fee_cents = sr.bank_fee_cents

        assert creditor_payment_cents >= 0
        assert program_fee_cents >= 0

        if creditor_payment_cents == 0:
            assert bank_fee_cents == 0
        else:
            assert bank_fee_cents == rules.bank_fee_cents

        while len(min_payment_tiers) > (active_tier_index + 1) and min_payment_tiers[
            active_tier_index + 1
        ][0] <= (i + 1):
            active_tier_index += 1

        if is_creditor_payment_collected:
            assert creditor_payment_cents == 0
        else:
            assert creditor_payment_cents > 0
            assert creditor_payment_cents >= rules.min_payment_cents
            assert creditor_payment_cents >= prev_creditor_payment
            creditor_payments_unqiue.add(creditor_payment_cents)
            creditor_amount_collected += creditor_payment_cents

            assert creditor_amount_collected <= total_offer
            is_creditor_payment_collected = creditor_amount_collected == total_offer

            if creditor_payment_cents == rules.min_payment_cents:
                assert remaining_token_pays > 0
                remaining_token_pays -= 1

            if active_tier_index != -1:
                assert min_payment_tiers[active_tier_index][1] <= creditor_payment_cents

        program_fee_collected += program_fee_cents
        prev_creditor_payment = creditor_payment_cents

    assert is_creditor_payment_collected == True
    assert program_fee_collected == program_fee

    creditor_payments_unqiue = sorted(list(creditor_payments_unqiue))

    if pay_shape_used == "staircase":
        assert len(creditor_payments_unqiue) <= rules.max_segments
    elif pay_shape_used == "even":
        assert len(creditor_payments_unqiue) <= 2
        if len(creditor_payments_unqiue) == 2:
            assert (creditor_payments_unqiue[1] - creditor_payments_unqiue[0]) == 1


def is_infeasible_result_valid(
    result: Result,
    client: Client,
    offer: Offer,
    rules: CreditorRules,
):
    assert result.feasible == False
    assert result.schedule is None

    if result.additional_funds is not None:
        lump_fund_options = result.additional_funds.lump_sum

        if lump_fund_options is not None:
            assert lump_fund_options.date <= client.last_draft_date
            tmp_client: Client = copy.deepcopy(client)
            tmp_client.ledger = client.ledger + [
                LedgerEntry(
                    date=lump_fund_options.date,
                    amount_cents=lump_fund_options.amount_cents,
                    type="credit",
                )
            ]

            tmp_result = evaluate_offer(tmp_client, offer, rules)

            assert tmp_result.feasible == True
            _is_feasible_result_valid(tmp_result, tmp_client, offer, rules)

            # Check minimum
            tmp_client: Client = copy.deepcopy(client)
            tmp_client.ledger = client.ledger + [
                LedgerEntry(
                    date=lump_fund_options.date,
                    amount_cents=lump_fund_options.amount_cents - 1,
                    type="credit",
                )
            ]

            tmp_result = evaluate_offer(tmp_client, offer, rules)

            assert tmp_result.feasible == False
            assert tmp_result.additional_funds is not None
            assert tmp_result.additional_funds.lump_sum is not None
            assert tmp_result.additional_funds.lump_sum.amount_cents == 1
            assert tmp_result.additional_funds.lump_sum.date <= client.last_draft_date

            print("Validated Fund Options")

        increment_fund_options = result.additional_funds.monthly_increment

        if increment_fund_options is not None:
            tmp_client: Client = copy.deepcopy(client)
            ledger = tmp_client.ledger

            num_futures_remaining = increment_fund_options.num_drafts

            for i, l in enumerate(ledger):
                if l.date > tmp_client.as_of_date and l.type == "credit":
                    if num_futures_remaining == 0:
                        break
                    ledger[i] = LedgerEntry(
                        date=l.date,
                        amount_cents=l.amount_cents
                        + increment_fund_options.amount_cents,
                        type=l.type,
                    )
                    num_futures_remaining -= 1

            assert num_futures_remaining == 0

            tmp_client.ledger = ledger
            tmp_result = evaluate_offer(tmp_client, offer, rules)

            assert tmp_result.feasible == True
            _is_feasible_result_valid(tmp_result, tmp_client, offer, rules)

            # Check minimum
            tmp_client: Client = copy.deepcopy(client)
            ledger = tmp_client.ledger

            num_futures_remaining = increment_fund_options.num_drafts

            for i, l in enumerate(ledger):
                if l.date > tmp_client.as_of_date and l.type == "credit":
                    if num_futures_remaining == 0:
                        break
                    ledger[i] = LedgerEntry(
                        date=l.date,
                        amount_cents=l.amount_cents
                        + increment_fund_options.amount_cents
                        - 1,
                        type=l.type,
                    )
                    num_futures_remaining -= 1

            assert num_futures_remaining == 0
            tmp_client.ledger = ledger
            tmp_result = evaluate_offer(tmp_client, offer, rules)

            assert tmp_result.feasible == False
            assert tmp_result.additional_funds is not None
            assert tmp_result.additional_funds.monthly_increment is not None
            assert tmp_result.additional_funds.monthly_increment.amount_cents == 1

            print("Validated Increment Options")


def _is_result_valid(
    result: Result,
    client: Client,
    offer: Offer,
    rules: CreditorRules,
    feasible_value: Optional[bool] = None,
):
    if feasible_value is not None:
        assert result.feasible == feasible_value

    if result.feasible is True:
        _is_feasible_result_valid(result, client, offer, rules)
    elif result.feasible is False:
        is_infeasible_result_valid(result, client, offer, rules)
    else:
        raise AssertionError("feasible should be bool value")


def _run(case: str):
    client, offer, rules = load_case(f"cases/{case}")
    return client, offer, rules, evaluate_offer(client, offer, rules)


def test_case1_feasible_even():
    client, offer, rules, r = _run("case1_feasible_even")
    assert r.feasible is True
    assert r.pay_shape_used == "even"
    assert r.schedule is not None
    # balance must never go negative
    assert all(row.balance_cents >= 0 for row in r.schedule)

    _is_result_valid(r, client, offer, rules, True)


def test_case2_infeasible_minima():
    client, offer, rules, r = _run("case2_infeasible_minima")
    assert r.feasible is False
    af = r.additional_funds
    assert af is not None
    assert af.lump_sum.amount_cents == 10000
    assert af.lump_sum.within_guardrail is True
    assert af.monthly_increment.amount_cents == 2500
    assert af.monthly_increment.num_drafts == 5
    assert af.monthly_increment.within_guardrail is True

    _is_result_valid(r, client, offer, rules, False)


def test_case3_requires_balloon():
    client, offer, rules, r = _run("case3_balloon")
    assert r.feasible is True
    # this creditor allows ballooning; the solver defers payment into a final balloon
    assert r.pay_shape_used == "balloon"

    _is_result_valid(r, client, offer, rules, True)


def test_case4_tiered_minimums():
    client, offer, rules, r = _run("case4_tiers")
    assert r.feasible is True
    assert r.pay_shape_used == "staircase"
    # payments 7+ must respect the $50 tier floor
    payments = [
        row.creditor_payment_cents
        for row in r.schedule
        if row.creditor_payment_cents > 0
    ]
    assert all(p >= 5000 for p in payments[6:])

    _is_result_valid(r, client, offer, rules, True)
