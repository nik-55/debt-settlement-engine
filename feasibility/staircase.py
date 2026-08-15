from itertools import combinations

from feasibility.models import CreditorRules

# For max_segements = 4, max_tokens = 2, min_cents = 100
# (i) [100, 100, 101, 101, 200]: This is ballon as we tried to kept it always at minimum and bumped all remaining at last value
# (ii) [100, 100, 101, 101, 201]: This is ballon as we tried to kept it always at minimum and bumped all remaining at last value
# Staircase (i): [100, 100, 102, 150, 150]: Is this staircase?
# Staircase (ii): [100, 100, 101, 151, 151]: Is this staircase?


def get_min_required_pay_vec(k: int, rules: CreditorRules) -> list[int]:
    minimum_payment_tiers = sorted(rules.min_payment_tiers, key=lambda x: (x[0], x[1]))

    min_required_pay_vec = []
    remaining_token_pays = rules.max_token_pays
    active_tier_index = -1
    prev_min_required_pay = 0

    for i in range(k):
        while len(minimum_payment_tiers) > (
            active_tier_index + 1
        ) and minimum_payment_tiers[active_tier_index + 1][0] <= (i + 1):
            active_tier_index += 1

        min_required_pay = max(rules.min_payment_cents, prev_min_required_pay)

        if active_tier_index != -1:
            min_required_pay = max(
                min_required_pay, minimum_payment_tiers[active_tier_index][1]
            )

        if min_required_pay == rules.min_payment_cents:
            if remaining_token_pays == 0:
                min_required_pay = min_required_pay + 1
            else:
                remaining_token_pays -= 1

        min_required_pay_vec.append(min_required_pay)
        prev_min_required_pay = min_required_pay

    return min_required_pay_vec


def possible_combination_of_splits(k: int, max_segments: int) -> list[list[int]]:
    runs = []

    for num_blocks in range(1, min(k, max_segments) + 1):
        num_cuts = num_blocks - 1
        possibe_cuts = list(combinations(range(1, k), num_cuts))
        # For max_segements = 12, k = 5, num_blocks = 3
        # num_cuts = 2
        # [(1, 2), (1, 3), (1, 4), (2, 3), (2, 4), (3, 4)]
        # (2, 4): This is one combination to cut an array of len 5 at index 2 and 4 to produce 3 blocks
        # blocks = array of block len
        # blocks = [1, 4]: block of len 1 followed by block of len 4
        # blocks = [1, 2, 1, 1]: block of len 1, block of len 2, block of len 1, block of len 1
        # runs for num_cuts = 2:  [[2, 3], [3, 2], [4, 1]] --> Basically all possible combination

        for cut_positions in possibe_cuts:
            blocks = []

            prev_cut_position = 0
            for position_to_cut in cut_positions:
                blocks.append(position_to_cut - prev_cut_position)
                prev_cut_position = position_to_cut

            blocks.append(k - prev_cut_position)

            if k > 1 and blocks[-1] < 2:
                continue

            runs.append(blocks)

    return runs


def build_pay_vec_from_run(
    run: list[int],
    min_required_pay_vec: list[int],
    total_offer: int,
) -> list[int]:
    num_blocks = len(run)

    block_ends_index = []
    len_till_now = 0
    for block_len in run:
        len_till_now += block_len
        block_ends_index.append(len_till_now - 1)

    unique_values_per_block = []
    prev_block_value = 0
    for i in range(num_blocks - 1):
        block_value = max(
            prev_block_value + 1, min_required_pay_vec[block_ends_index[i]]
        )
        unique_values_per_block.append(block_value)
        prev_block_value = block_value

    leftover_cents = total_offer - sum(
        run[i] * unique_values_per_block[i] for i in range(num_blocks - 1)
    )
    last_block_len = run[-1]

    if leftover_cents % last_block_len:
        is_fixed = False

        for i in range(num_blocks - 2, -1, -1):
            ceiling = (
                unique_values_per_block[i + 1] - 1
                if (i + 1) < len(unique_values_per_block)
                else None
            )

            for delta_cents in range(1, last_block_len):
                modified_value = unique_values_per_block[i] + delta_cents

                if ceiling is not None and modified_value > ceiling:
                    break

                if (leftover_cents - delta_cents * run[i]) % last_block_len == 0:
                    unique_values_per_block[i] = modified_value
                    is_fixed = True
                    leftover_cents -= delta_cents * run[i]
                    break

            if is_fixed:
                break

        if not is_fixed:
            return []

    last_block_value = leftover_cents // last_block_len

    if (
        len(unique_values_per_block) >= 1
        and last_block_value <= unique_values_per_block[-1]
    ):
        return []

    if last_block_value < min_required_pay_vec[block_ends_index[-1]]:
        return []

    unique_values_per_block.append(last_block_value)

    creditor_payments = []

    for i in range(num_blocks):
        creditor_payments += [unique_values_per_block[i]] * run[i]

    return creditor_payments


def staircase_payments(
    k: int,
    total_offer: int,
    rules: CreditorRules,
):
    from feasibility.algo import validate_payments

    min_required_pay_vec = get_min_required_pay_vec(k, rules)

    if sum(min_required_pay_vec) > total_offer:
        return []

    runs = possible_combination_of_splits(k, rules.max_segments)
    best = None

    for run in runs:
        payment_vector = build_pay_vec_from_run(run, min_required_pay_vec, total_offer)

        if not payment_vector:
            continue

        if not validate_payments(
            creditor_payments=payment_vector,
            min_payment_cents=rules.min_payment_cents,
            max_token_pays=rules.max_token_pays,
            min_payment_tiers=rules.min_payment_tiers,
            pay_shape="staircase",
            max_segments=rules.max_segments,
            total_offer=total_offer,
        ):
            continue

        best = min(payment_vector, best) if best is not None else payment_vector

    return best or []
