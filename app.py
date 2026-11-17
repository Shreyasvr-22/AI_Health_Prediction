from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, flash, redirect, render_template, request, url_for

from services.groq_service import SUPPORTED_LANGUAGES, generate_health_remarks
from validators import validate_patient_form

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("FLASK_SECRET_KEY", "local-development-key-change-me")
app.config["DATABASE"] = os.getenv("DATABASE_PATH", str(BASE_DIR / "instance" / "health_records.db"))
app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024

Path(app.config["DATABASE"]).parent.mkdir(parents=True, exist_ok=True)


@contextmanager
def get_db():
    """Yield a SQLite connection and always close it after the operation."""
    connection = sqlite3.connect(app.config["DATABASE"])
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def init_db() -> None:
    """Create the contacts table when the application starts."""
    with get_db() as db:
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS contacts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                full_name TEXT NOT NULL,
                date_of_birth TEXT NOT NULL,
                email TEXT NOT NULL,
                glucose REAL NOT NULL,
                haemoglobin REAL NOT NULL,
                cholesterol REAL NOT NULL,
                remarks TEXT NOT NULL DEFAULT '',
                remarks_language TEXT NOT NULL DEFAULT 'en',
                ai_status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        columns = {row["name"] for row in db.execute("PRAGMA table_info(contacts)").fetchall()}
        if "remarks_language" not in columns:
            db.execute(
                "ALTER TABLE contacts ADD COLUMN remarks_language TEXT NOT NULL DEFAULT 'en'"
            )
        db.commit()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def get_patient(patient_id: int):
    with get_db() as db:
        return db.execute("SELECT * FROM contacts WHERE id = ?", (patient_id,)).fetchone()


def form_values(source) -> dict:
    return {
        "full_name": source.get("full_name", "").strip(),
        "date_of_birth": source.get("dob", source.get("date_of_birth", "")).strip(),
        "email": source.get("email", "").strip(),
        "glucose": source.get("glucose", "").strip(),
        "haemoglobin": source.get("haemoglobin", "").strip(),
        "cholesterol": source.get("cholesterol", "").strip(),
    }


@app.template_filter("display_date")
def display_date(value: str) -> str:
    try:
        return date.fromisoformat(value).strftime("%d/%m/%Y")
    except (ValueError, TypeError):
        return value or "—"


@app.template_filter("number")
def display_number(value) -> str:
    try:
        number = float(value)
        return str(int(number)) if number.is_integer() else f"{number:g}"
    except (ValueError, TypeError, AttributeError):
        return str(value)


@app.route("/")
def index():
    search = request.args.get("q", "").strip()
    with get_db() as db:
        if search:
            patients = db.execute(
                """SELECT * FROM contacts
                   WHERE full_name LIKE ? OR email LIKE ?
                   ORDER BY id DESC""",
                (f"%{search}%", f"%{search}%"),
            ).fetchall()
        else:
            patients = db.execute("SELECT * FROM contacts ORDER BY id DESC").fetchall()
        total = db.execute("SELECT COUNT(*) FROM contacts").fetchone()[0]
        ai_ready = db.execute("SELECT COUNT(*) FROM contacts WHERE ai_status = 'generated'").fetchone()[0]
        needs_attention = db.execute("SELECT COUNT(*) FROM contacts WHERE ai_status != 'generated'").fetchone()[0]
    return render_template(
        "index.html", patients=patients, search=search, total=total,
        ai_ready=ai_ready, needs_attention=needs_attention,
    )


@app.route("/patients/new", methods=["GET", "POST"])
def create_patient():
    values = form_values(request.form) if request.method == "POST" else {}
    if request.method == "POST":
        cleaned, errors = validate_patient_form(values)
        if errors:
            for error in errors:
                flash(error, "error")
            return render_template("patient_form.html", mode="create", values=values), 400

        # Save the valid contact even if the external AI service is unavailable.
        ai_result = generate_health_remarks(cleaned)
        remarks = ai_result["remarks"]
        status = "generated" if ai_result["success"] else "pending"
        timestamp = utc_now()
        with get_db() as db:
            cursor = db.execute(
                """INSERT INTO contacts
                   (full_name, date_of_birth, email, glucose, haemoglobin, cholesterol,
                    remarks, ai_status, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    cleaned["full_name"], cleaned["date_of_birth"].isoformat(), cleaned["email"],
                    cleaned["glucose"], cleaned["haemoglobin"], cleaned["cholesterol"],
                    remarks, status, timestamp, timestamp,
                ),
            )
            patient_id = cursor.lastrowid
            db.commit()

        if ai_result["success"]:
            flash("Patient record saved and AI remarks generated successfully.", "success")
        else:
            flash("Patient record saved. AI remarks could not be generated; check your Groq settings and retry from the record list.", "warning")
        return redirect(url_for("patient_detail", patient_id=patient_id))

    return render_template("patient_form.html", mode="create", values=values)


@app.route("/patients/<int:patient_id>")
def patient_detail(patient_id: int):
    patient = get_patient(patient_id)
    if patient is None:
        flash("The requested patient record was not found.", "error")
        return redirect(url_for("index"))
    return render_template("patient_detail.html", patient=patient)


@app.route("/patients/<int:patient_id>/edit", methods=["GET", "POST"])
def edit_patient(patient_id: int):
    patient = get_patient(patient_id)
    if patient is None:
        flash("The requested patient record was not found.", "error")
        return redirect(url_for("index"))

    if request.method == "POST":
        values = form_values(request.form)
        cleaned, errors = validate_patient_form(values)
        if errors:
            for error in errors:
                flash(error, "error")
            return render_template("patient_form.html", mode="edit", values=values, patient=patient), 400

        blood_values_changed = any(
            float(cleaned[field]) != float(patient[field])
            for field in ("glucose", "haemoglobin", "cholesterol")
        )
        remarks = patient["remarks"]
        ai_status = patient["ai_status"]
        if blood_values_changed:
            ai_result = generate_health_remarks(
                cleaned, language=patient["remarks_language"]
            )
            remarks = ai_result["remarks"]
            ai_status = "generated" if ai_result["success"] else "pending"

        with get_db() as db:
            db.execute(
                """UPDATE contacts SET full_name=?, date_of_birth=?, email=?, glucose=?,
                   haemoglobin=?, cholesterol=?, remarks=?, ai_status=?, updated_at=? WHERE id=?""",
                (
                    cleaned["full_name"], cleaned["date_of_birth"].isoformat(), cleaned["email"],
                    cleaned["glucose"], cleaned["haemoglobin"], cleaned["cholesterol"],
                    remarks, ai_status, utc_now(), patient_id,
                ),
            )
            db.commit()
        flash("Patient record updated successfully.", "success")
        return redirect(url_for("patient_detail", patient_id=patient_id))

    values = {
        "full_name": patient["full_name"],
        "date_of_birth": date.fromisoformat(patient["date_of_birth"]).strftime("%d/%m/%Y"),
        "email": patient["email"],
        "glucose": patient["glucose"],
        "haemoglobin": patient["haemoglobin"],
        "cholesterol": patient["cholesterol"],
    }
    return render_template("patient_form.html", mode="edit", values=values, patient=patient)


@app.post("/patients/<int:patient_id>/delete")
def delete_patient(patient_id: int):
    with get_db() as db:
        result = db.execute("DELETE FROM contacts WHERE id = ?", (patient_id,))
        db.commit()
    if result.rowcount:
        flash("Patient record deleted successfully.", "success")
    else:
        flash("The patient record was not found.", "error")
    return redirect(url_for("index"))


@app.post("/patients/<int:patient_id>/regenerate")
def regenerate_remarks(patient_id: int):
    patient = get_patient(patient_id)
    if patient is None:
        flash("The requested patient record was not found.", "error")
        return redirect(url_for("index"))
    language = request.form.get("language", "en")
    if language not in SUPPORTED_LANGUAGES:
        language = "en"
    ai_result = generate_health_remarks(dict(patient), language=language)
    with get_db() as db:
        db.execute(
            """UPDATE contacts
               SET remarks=?, ai_status=?, remarks_language=?, updated_at=?
               WHERE id=?""",
            (
                ai_result["remarks"],
                "generated" if ai_result["success"] else "pending",
                language,
                utc_now(),
                patient_id,
            ),
        )
        db.commit()
    if ai_result["success"]:
        flash("AI remarks regenerated successfully.", "success")
    else:
        flash("Groq could not generate remarks. Check your API key, model name and internet connection.", "warning")
    return redirect(url_for("patient_detail", patient_id=patient_id))


@app.errorhandler(404)
def not_found(_error):
    return render_template("404.html"), 404


@app.errorhandler(413)
def too_large(_error):
    flash("The submitted request is too large.", "error")
    return redirect(url_for("index")), 413


init_db()

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.getenv("PORT", "5000")), debug=os.getenv("FLASK_DEBUG", "false").lower() == "true")
