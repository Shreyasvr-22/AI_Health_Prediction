from __future__ import annotations

import os
import sqlite3
import sys
import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app as app_module
from services import groq_service


class GroqLanguageTests(unittest.TestCase):
    def generate_with_language(self, language, patient=None):
        client = Mock()
        client.chat.completions.create.return_value = SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content="Generated test remarks.")
                )
            ]
        )
        with patch.object(groq_service, "Groq", return_value=client):
            with patch.dict(
                os.environ,
                {
                    "GROQ_API_KEY": "test-key",
                    "GROQ_MODEL": "openai/gpt-oss-20b",
                },
            ):
                result = groq_service.generate_health_remarks(
                    patient
                    or {"glucose": 95, "haemoglobin": 13.2, "cholesterol": 180},
                    language=language,
                )
        prompt = client.chat.completions.create.call_args.kwargs["messages"][1]["content"]
        return result, prompt

    def test_supported_languages_are_requested_in_prompt(self):
        for language, language_name in groq_service.SUPPORTED_LANGUAGES.items():
            with self.subTest(language=language):
                result, prompt = self.generate_with_language(language)
                self.assertTrue(result["success"])
                self.assertIn(
                    f"Write the complete response only in {language_name}.", prompt
                )
                self.assertIn(
                    "Do not include alternate translations, bilingual text, or multiple versions",
                    prompt,
                )
                format_section = prompt.split("STRICT RESPONSE FORMAT:", 1)[1]
                headings = groq_service.LANGUAGE_HEADINGS[language]
                self.assertIn(headings["title"], format_section)
                for number, key in enumerate(
                    ("glucose", "haemoglobin", "cholesterol", "overall", "next_step"),
                    start=1,
                ):
                    self.assertIn(f"{number}. {headings[key]}:", format_section)
                self.assertIn(headings["interpretation_note"], format_section)
                self.assertIn("Translate the heading and the entire note", format_section)
                self.assertIn("do not repeat the note elsewhere", format_section)

    def test_limitations_are_consolidated_in_the_final_note(self):
        _, prompt = self.generate_with_language("en")
        format_section = " ".join(
            prompt.split("STRICT RESPONSE FORMAT:", 1)[1].split()
        )

        self.assertIn("measurement", format_section)
        self.assertIn("fasting status and test timing", format_section)
        self.assertIn("age, sex, and laboratory", format_section)
        self.assertIn("test type, age at testing", format_section)
        self.assertIn("not a medical diagnosis or medical advice", format_section)
        self.assertIn(
            "Put all limitations and medical warnings together in the single",
            format_section,
        )

    def test_unsupported_language_falls_back_to_english(self):
        result, prompt = self.generate_with_language("xx")
        self.assertTrue(result["success"])
        self.assertIn("Write the complete response only in English.", prompt)

    def test_prompt_includes_calculated_age_but_not_raw_dob(self):
        dob = "2000-01-01"
        result, prompt = self.generate_with_language(
            "en",
            {
                "date_of_birth": dob,
                "glucose": 95,
                "haemoglobin": 13.2,
                "cholesterol": 180,
            },
        )

        self.assertTrue(result["success"])
        self.assertIn(
            f"Current age derived from DOB: {groq_service.calculate_patient_age(dob)}",
            prompt,
        )
        self.assertNotIn(dob, prompt)


class PatientAgeTests(unittest.TestCase):
    def test_accepts_date_datetime_and_supported_string_formats(self):
        dob = date(2000, 1, 1)
        expected_age = groq_service.calculate_patient_age(dob)

        for value in (
            dob,
            datetime(2000, 1, 1, 12, 30),
            "2000-01-01",
            "01/01/2000",
            "01.01.2000",
        ):
            with self.subTest(value=value):
                self.assertEqual(groq_service.calculate_patient_age(value), expected_age)

    def test_calculates_age_before_and_on_birthday(self):
        today = date.today()
        dob = date(today.year - 20, 12, 31)
        expected_age = 19 if (today.month, today.day) < (12, 31) else 20
        self.assertEqual(groq_service.calculate_patient_age(dob), expected_age)

    def test_invalid_and_future_dates_are_not_available(self):
        future_dob = date(date.today().year + 1, 1, 1)
        self.assertEqual(groq_service.calculate_patient_age("not a date"), "not available")
        self.assertEqual(groq_service.calculate_patient_age(future_dob), "not available")


class PatientLanguagePersistenceTests(unittest.TestCase):
    def setUp(self):
        self.original_database = app_module.app.config["DATABASE"]
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.addCleanup(
            app_module.app.config.update, {"DATABASE": self.original_database}
        )
        self.database_path = Path(self.temp_dir.name) / "legacy.db"
        app_module.app.config["DATABASE"] = str(self.database_path)
        with sqlite3.connect(self.database_path) as db:
            db.execute(
                """
                CREATE TABLE contacts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    full_name TEXT NOT NULL,
                    date_of_birth TEXT NOT NULL,
                    email TEXT NOT NULL,
                    glucose REAL NOT NULL,
                    haemoglobin REAL NOT NULL,
                    cholesterol REAL NOT NULL,
                    remarks TEXT NOT NULL DEFAULT '',
                    ai_status TEXT NOT NULL DEFAULT 'pending',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            db.execute(
                """
                INSERT INTO contacts
                    (full_name, date_of_birth, email, glucose, haemoglobin,
                     cholesterol, remarks, ai_status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "Sample Patient",
                    "2000-01-01",
                    "sample@example.com",
                    95,
                    13.2,
                    180,
                    "Existing remarks",
                    "generated",
                    "2026-01-01",
                    "2026-01-01",
                ),
            )
        db.close()
        app_module.init_db()
        self.client = app_module.app.test_client()

    def test_migration_preserves_existing_record_and_defaults_to_english(self):
        patient = app_module.get_patient(1)
        self.assertEqual(patient["full_name"], "Sample Patient")
        self.assertEqual(patient["remarks"], "Existing remarks")
        self.assertEqual(patient["remarks_language"], "en")

    def test_regeneration_persists_selected_language(self):
        with patch.object(
            app_module,
            "generate_health_remarks",
            return_value={"success": True, "remarks": "Hindi remarks"},
        ) as generate:
            response = self.client.post(
                "/patients/1/regenerate", data={"language": "hi"}
            )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(generate.call_args.kwargs["language"], "hi")
        self.assertEqual(app_module.get_patient(1)["remarks_language"], "hi")
        detail = self.client.get("/patients/1").get_data(as_text=True)
        self.assertIn('<option value="hi" selected>', detail)

    def test_unsupported_language_falls_back_to_english(self):
        with patch.object(
            app_module,
            "generate_health_remarks",
            return_value={"success": True, "remarks": "English remarks"},
        ) as generate:
            response = self.client.post(
                "/patients/1/regenerate", data={"language": "xx"}
            )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(generate.call_args.kwargs["language"], "en")
        self.assertEqual(app_module.get_patient(1)["remarks_language"], "en")

    def test_edit_regeneration_uses_saved_language(self):
        with app_module.get_db() as db:
            db.execute("UPDATE contacts SET remarks_language='kn' WHERE id=1")

        with patch.object(
            app_module,
            "generate_health_remarks",
            return_value={"success": True, "remarks": "Kannada remarks"},
        ) as generate:
            response = self.client.post(
                "/patients/1/edit",
                data={
                    "full_name": "Sample Patient",
                    "dob": "01/01/2000",
                    "email": "sample@example.com",
                    "glucose": "96",
                    "haemoglobin": "13.2",
                    "cholesterol": "180",
                },
            )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(generate.call_args.kwargs["language"], "kn")
        self.assertEqual(app_module.get_patient(1)["remarks_language"], "kn")


if __name__ == "__main__":
    unittest.main()
