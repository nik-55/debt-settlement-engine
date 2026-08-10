import math
import datetime


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


def get_cadence_date_range(
    first_payment_date: datetime.date, num_of_months: int
) -> list[datetime.date]:
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
