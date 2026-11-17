import sys
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from validators import parse_date, validate_patient_form


class PatientValidationTests(unittest.TestCase):
    def patient(self, **overrides):
        values = {
            "full_name": "Robyn Pears",
            "date_of_birth": "28.01.1960",
            "email": "robyn@gmail.com",
            "glucose": "232",
            "haemoglobin": "13.5",
            "cholesterol": "180",
        }
        values.update(overrides)
        return values

    def test_valid_row_accepts_dot_date(self):
        cleaned, errors = validate_patient_form(self.patient())
        self.assertEqual(errors, [])
        self.assertEqual(cleaned["date_of_birth"], date(1960, 1, 28))

    def test_valid_row_accepts_slash_date(self):
        cleaned, errors = validate_patient_form(self.patient(date_of_birth="28/01/1960"))
        self.assertEqual(errors, [])
        self.assertEqual(cleaned["date_of_birth"], date(1960, 1, 28))

    def test_invalid_email_is_rejected(self):
        _, errors = validate_patient_form(self.patient(email="hunter@gmail"))
        self.assertTrue(any("valid email" in error for error in errors))

    def test_impossible_date_is_rejected(self):
        _, errors = validate_patient_form(self.patient(date_of_birth="31/11/2001"))
        self.assertIn(
            "Invalid date: November has only 30 days. Please enter a valid date.",
            errors,
        )

    def test_impossible_day_reports_month_length(self):
        _, errors = validate_patient_form(self.patient(date_of_birth="31/04/2000"))
        self.assertIn(
            "Invalid date: April has only 30 days. Please enter a valid date.",
            errors,
        )

    def test_leap_day_is_valid_only_in_leap_years(self):
        _, leap_year_errors = validate_patient_form(
            self.patient(date_of_birth="29/02/2024")
        )
        _, non_leap_year_errors = validate_patient_form(
            self.patient(date_of_birth="29/02/2025")
        )

        self.assertEqual(leap_year_errors, [])
        self.assertIn(
            "Invalid date: February has only 28 days. Please enter a valid date.",
            non_leap_year_errors,
        )

    def test_valid_date_and_dot_separated_invalid_date(self):
        _, valid_errors = validate_patient_form(
            self.patient(date_of_birth="28/01/2004")
        )
        _, dot_date_errors = validate_patient_form(
            self.patient(date_of_birth="31.11.2001")
        )

        self.assertEqual(valid_errors, [])
        self.assertIn(
            "Invalid date: November has only 30 days. Please enter a valid date.",
            dot_date_errors,
        )

    def test_future_date_is_rejected(self):
        future_year = date.today().year + 4
        _, errors = validate_patient_form(self.patient(date_of_birth=f"19/10/{future_year}"))
        self.assertTrue(any("future" in error for error in errors))

    def test_non_numeric_value_is_rejected(self):
        _, errors = validate_patient_form(self.patient(glucose="abc"))
        self.assertTrue(any("Glucose must be" in error for error in errors))

    def test_duplicate_data_is_not_rejected_by_validator(self):
        _, errors = validate_patient_form(self.patient())
        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
