# AI Health Prediction

A Python Flask web application for the Gokul Infocare **Task 2 – AI Growth Python Skills** assessment. It stores patient/contact details and blood-test values in SQLite, validates form input, and uses the Groq API to create short educational remarks.

> **Important:** This is an assessment demonstration, not a medical device. AI remarks are not diagnoses or medical advice. The task does not state units, fasting status, clinical history, or laboratory reference ranges. The application uses clearly identified demonstration unit assumptions, which must be checked against the original lab report.

## Features

- Create, read, update and delete patient records.
- SQLite persistent storage. Duplicate records are allowed because the task does not request duplicate prevention.
- Validation for required fields, email format, real calendar dates, future dates, and positive numeric blood-test values.
- Accepts `DD/MM/YYYY` as requested in the brief and also accepts the dot-separated dates printed in the supplied test table (for example, `28.01.1960`). Values/dates are not silently changed.
- Groq API integration using the Groq Python SDK.
- AI remarks can be generated in English, Hindi, or Kannada, with the selected language saved per patient. Existing SQLite databases are upgraded non-destructively and default to English.
- AI remarks are saved with the record. If Groq is not configured or is temporarily unavailable, the valid patient record is still saved and AI remarks can be regenerated later.
- Search by patient name or email.
- Clear status and validation messages.

## Technology

- Python 3.10+
- Flask
- SQLite (Python standard library)
- Groq Python SDK
- HTML, CSS and JavaScript

## 1. Download and open

Extract the ZIP folder and open `AI_Health_Prediction` in Visual Studio Code.

## 2. Create a virtual environment

Windows PowerShell:

```powershell
py -3 -m venv .venv
.venv\Scripts\Activate.ps1
```

Windows Command Prompt:

```bat
py -3 -m venv .venv
.venv\Scripts\activate.bat
```

macOS/Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

## 3. Install packages

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## 4. Configure your Groq API key

1. Copy `.env.example` and rename the copy to `.env`.
2. Open `.env` and replace the placeholder with your own Groq API key.
3. Keep `.env` private. It is excluded from Git by `.gitignore`.
4. Do not paste your key into `app.py`, screenshots, video recordings, README, or GitHub.

Example local `.env` file:

```dotenv
GROQ_API_KEY=your_real_key_goes_here
GROQ_MODEL=openai/gpt-oss-20b
FLASK_SECRET_KEY=replace_with_a_long_random_secret
FLASK_DEBUG=false
```

The model can be changed using `GROQ_MODEL` without changing Python code. Check the current model catalogue at https://console.groq.com/docs/models.

### Deploy to Render

Create a Render Web Service connected to this GitHub repository. Use:

- **Build command:** `pip install -r requirements.txt`
- **Start command:** `gunicorn --bind 0.0.0.0:$PORT app:app`

Add these environment variables in the Render dashboard:

| Variable | Value |
| --- | --- |
| `GROQ_API_KEY` | Your Groq API key; mark it as a secret. |
| `GROQ_MODEL` | `openai/gpt-oss-20b` |
| `FLASK_SECRET_KEY` | A long, randomly generated secret. |
| `FLASK_DEBUG` | `false` |

Render supplies `PORT` automatically; do not set it manually. Never upload the local `.env` file. SQLite storage on a web service's local filesystem may not survive restarts or redeploys. To persist records, attach a persistent disk mounted at `/var/data` and set `DATABASE_PATH` to `/var/data/health_records.db`.

## 5. Run the application

```bash
python app.py
```

Open this address in your browser:

```text
http://127.0.0.1:5000
```

The SQLite database is created automatically at `instance/health_records.db` the first time the application starts. The `instance` folder is excluded from Git because it contains local patient records.

## 6. Enter the Task 2 data

Use **Add Patient** and enter the ten rows from `data/task2_test_records.csv` one at a time. The CSV is a reference copy of the task data; it is not automatically imported. Keep all names, dates, email addresses and numeric values exactly as supplied.

Expected validation outcomes:

| Test | Expected outcome | Reason |
|---:|---|---|
| 1 | Accepted | Email and date are valid; values are numeric. |
| 2 | Rejected | `hunter@gmail` has no complete domain suffix. |
| 3 | Accepted | Supplied fields pass basic format validation. |
| 4 | Rejected | 31 November is not a real calendar date. |
| 5 | Accepted | Supplied fields pass basic format validation. |
| 6 | Accepted | Duplicate of Test 1; duplicate records are not blocked. |
| 7 | Accepted | Supplied fields pass basic format validation. |
| 8 | Rejected | DOB is in the future (19/10/2030) and email has no `@` symbol. |
| 9 | Accepted | Supplied fields pass basic format validation. |
| 10 | Accepted | Supplied fields pass basic format validation. |

Expected result after the ten attempts: seven records saved (tests 1, 3, 5, 6, 7, 9 and 10), and three test attempts rejected (2, 4 and 8). The duplicate row 6 remains because the assessment does not instruct the candidate to enforce uniqueness.

**Date entry note:** The PDF says to use `dd/mm/yyyy` in the application, while its table prints dates with dots. The app accepts both notations and stores the same calendar date. For the invalid date test, enter `31.11.2001` exactly as shown or `31/11/2001`; both are rejected as impossible dates.

## 7. Required demonstration actions

1. Add the supplied records and show the validation messages for test 2, test 4 and test 8.
2. Open **Patient Records** and show all successfully created records.
3. Open any one record, choose Edit, and change its email to `gokul@infocare.com`.
4. Return to the list and confirm the email has been updated (open the record to show the email).
5. Delete any one record.
6. Show the updated list after deletion.
7. Open `app.py`, `validators.py` and `services/groq_service.py` and explain the routes, validation and Groq request.

## 8. How the code is organised

```text
AI_Health_Prediction/
├── app.py                       # Flask routes, CRUD and SQLite operations
├── validators.py                # Email, DOB and numeric validation
├── services/
│   ├── __init__.py
│   └── groq_service.py           # Calls Groq and handles API errors
├── templates/                   # Jinja HTML pages
├── static/
│   ├── css/style.css             # Responsive UI styles
│   └── js/app.js                 # Delete confirmations and small UI actions
├── data/
│   └── task2_test_records.csv    # Exact assessment test data for reference
├── instance/                    # Created automatically; local SQLite database
├── .env.example                  # Safe environment-variable template
├── .gitignore                    # Excludes secrets and local database
└── requirements.txt              # Python dependencies
```

### Application flow

1. The browser submits the patient form to a Flask route.
2. `validators.py` checks the entered values before database writes.
3. `app.py` calls `generate_health_remarks()` in `services/groq_service.py` for valid data, using the patient's selected remarks language.
4. The Groq SDK sends the three numerical blood-test results, selected remarks language, and locally calculated age to the model; the patient's name, raw DOB and email are not sent to Groq.
5. The returned remark, selected language, and patient details are stored in SQLite. If the API call fails, the patient record is still stored with a pending AI status and can be retried.
6. Edit and delete routes update the SQLite database using parameterised SQL queries.

## 9. GitHub checklist

Before pushing the project:

- Confirm `.env` is not in the Git staging area.
- Confirm no API key is present in Python files, README, screenshots or video.
- Do not upload the `instance/` folder or the SQLite database.
- Upload `.env.example` only; it contains placeholders, not secrets.
- After pushing, inspect the GitHub file list and search the repository for `gsk_` or other key fragments.

Suggested commands:

```bash
git init
git add .
git status
git commit -m "Build AI Health Prediction Flask application"
git branch -M main
git remote add origin YOUR_GITHUB_REPOSITORY_URL
git push -u origin main
```

## 10. Troubleshooting

**`ModuleNotFoundError`** – Activate the virtual environment and run `pip install -r requirements.txt`.

**AI remarks pending** – Check that `.env` exists in the project root, `GROQ_API_KEY` is correct, the key is active, the computer has internet access and `GROQ_MODEL` is currently available. Then open the patient record and click **Regenerate AI remarks**. Never share the key in chat or GitHub.

**Port already in use** – Close the other process using port 5000 or run with a different `PORT`, for example `PORT=5001` (PowerShell: `$env:PORT=5001`).

**Database reset for a fresh demonstration** – Stop the Flask server, delete `instance/health_records.db`, and restart `python app.py`. This permanently removes local records.

## 11. Suggested interview explanation

- **Why Flask?** It is a lightweight Python web framework and is suitable for a small CRUD application.
- **Why SQLite?** It is persistent, file-based and does not require a separate database server.
- **What is CRUD?** Create inserts a record, Read fetches records, Update changes an existing row, and Delete removes a row.
- **Where is validation performed?** In `validators.py`, on the server, before a database insert or update.
- **How is the AI connected?** `groq_service.py` creates a Groq client using `GROQ_API_KEY` from the environment and calls `client.chat.completions.create()`.
- **What if the AI API fails?** The valid contact is still saved, its AI status is pending, and the user can regenerate the remarks later.
- **Why are invalid rows rejected?** The email and date validation rules prevent malformed data and impossible/future dates from entering the patient table.
- **Why is Test 6 accepted?** The requirement asks to create the supplied entries and does not ask for duplicate prevention.

## 12. Video outline

1. Introduce the application and briefly name its stack.
2. Show a valid patient entry and generated AI remarks.
3. Attempt tests 2, 4 and 8 and explain the validation messages.
4. Show the patient list and explain that the duplicate row is accepted.
5. Edit one record's email to `gokul@infocare.com`.
6. Delete one record and show the refreshed list.
7. Explain the key parts of `app.py`, `validators.py` and `services/groq_service.py`.
8. End by showing that the API key is stored in `.env` and excluded from GitHub (do not reveal the key on screen).
