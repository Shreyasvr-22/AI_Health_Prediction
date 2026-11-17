from __future__ import annotations

import calendar
import math
import re
from datetime import date

EMAIL_PATTERN = re.compile(r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?)+$")
DOB_PATTERN = re.compile(r"(\d{1,2})([/.])(\d{1,2})\2(\d{4})")


def validate_dob(value: str | None) -> tuple[date | None, str | None]:
    """Return a parsed DOB or a specific date validation error."""
    raw = (value or "").strip()
    match = DOB_PATTERN.fullmatch(raw)
    if not match:
        return None, "Enter date in DD/MM/YYYY format."

    day, month, year = map(int, (match.group(1), match.group(3), match.group(4)))
    if not 1 <= month <= 12:
        return None, "Enter a valid month between 01 and 12."
    if year < 1:
        return None, "Enter a valid year."

    days_in_month = calendar.monthrange(year, month)[1]
    if not 1 <= day <= days_in_month:
        month_name = calendar.month_name[month]
        return None, (
            f"Invalid date: {month_name} has only {days_in_month} days. "
            "Please enter a valid date."
        )

    dob = date(year, month, day)
    if dob > date.today():
        return None, "Date of birth cannot be in the future."
    return dob, None


def parse_date(value: str) -> date:
    """Accept the requested dd/mm/yyyy and the table's dd.mm.yyyy notation."""
    dob, error = validate_dob(value)
    if error is not None:
        raise ValueError(error)
    if dob is None:
        raise ValueError("Enter date in DD/MM/YYYY format.")
    return dob


def validate_patient_form(values: dict):
    """Return (cleaned_values, errors); cleaned values are ready for storage."""
    errors: list[str] = []
    cleaned = {}

    full_name = (values.get("full_name") or "").strip()
    if not full_name:
        errors.append("Full name is required.")
    elif len(full_name) > 100:
        errors.append("Full name must be 100 characters or fewer.")
    else:
        cleaned["full_name"] = full_name

    email = (values.get("email") or "").strip()
    if not email or not EMAIL_PATTERN.fullmatch(email):
        errors.append("Enter a valid email address, for example name@example.com.")
    else:
        cleaned["email"] = email

    dob, dob_error = validate_dob(values.get("date_of_birth", ""))
    if dob_error:
        errors.append(dob_error)
    elif dob is not None:
        cleaned["date_of_birth"] = dob

    for field, label in (
        ("glucose", "Glucose"),
        ("haemoglobin", "Haemoglobin"),
        ("cholesterol", "Cholesterol"),
    ):
        raw = (values.get(field) or "").strip()
        try:
            number = float(raw)
            if not math.isfinite(number) or number <= 0:
                raise ValueError
            if number > 1_000_000:
                errors.append(f"{label} value is too large. Check the entered number.")
            else:
                cleaned[field] = number
        except (TypeError, ValueError):
            errors.append(f"{label} must be a positive numeric value.")

    return cleaned, errors
