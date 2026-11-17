from __future__ import annotations

import os
from datetime import date, datetime

from groq import Groq
from groq import APIConnectionError, APIStatusError, RateLimitError


def calculate_patient_age(dob_value: date | datetime | str | None) -> int | str:
    """Calculate age from a date value or supported DOB string format."""
    try:
        if isinstance(dob_value, datetime):
            dob = dob_value.date()
        elif isinstance(dob_value, date):
            dob = dob_value
        else:
            raw = str(dob_value).strip()
            dob = None
            for date_format in ("%Y-%m-%d", "%d/%m/%Y", "%d.%m.%Y"):
                try:
                    dob = datetime.strptime(raw, date_format).date()
                    break
                except ValueError:
                    continue
            if dob is None:
                return "not available"

        today = date.today()
        if dob > today:
            return "not available"

        age = today.year - dob.year
        if (today.month, today.day) < (dob.month, dob.day):
            age -= 1
        return age
    except (TypeError, ValueError):
        return "not available"


DEFAULT_MODEL = "openai/gpt-oss-20b"
SUPPORTED_LANGUAGES = {"en": "English", "hi": "Hindi", "kn": "Kannada"}
LANGUAGE_INSTRUCTIONS = {
    "en": "Use clear, simple English.",
    "hi": "Use natural Hindi in Devanagari script.",
    "kn": "Use natural Kannada in Kannada script.",
}
LANGUAGE_HEADINGS = {
    "en": {
        "title": "AI-generated educational risk remarks:",
        "glucose": "Glucose",
        "haemoglobin": "Haemoglobin",
        "cholesterol": "Cholesterol",
        "overall": "Overall observation",
        "next_step": "Recommended next step",
        "interpretation_note": "Important interpretation note:",
    },
    "hi": {
        "title": "कृत्रिम बुद्धिमत्ता द्वारा निर्मित शैक्षिक स्वास्थ्य जोखिम संबंधी टिप्पणियाँ:",
        "glucose": "ग्लूकोज़",
        "haemoglobin": "हीमोग्लोबिन",
        "cholesterol": "कोलेस्ट्रॉल",
        "overall": "समग्र अवलोकन",
        "next_step": "अगला सुझाया गया कदम",
        "interpretation_note": "महत्वपूर्ण व्याख्या संबंधी टिप्पणी:",
    },
    "kn": {
        "title": "ಕೃತಕ ಬುದ್ಧಿಮತ್ತೆಯಿಂದ ರಚಿಸಲಾದ ಶೈಕ್ಷಣಿಕ ಆರೋಗ್ಯ ಅಪಾಯದ ಟಿಪ್ಪಣಿಗಳು:",
        "glucose": "ಗ್ಲೂಕೋಸ್",
        "haemoglobin": "ಹೀಮೋಗ್ಲೋಬಿನ್",
        "cholesterol": "ಕೊಲೆಸ್ಟರಾಲ್",
        "overall": "ಒಟ್ಟಾರೆ ಅವಲೋಕನ",
        "next_step": "ಮುಂದಿನ ಶಿಫಾರಸು",
        "interpretation_note": "ಪ್ರಮುಖ ವ್ಯಾಖ್ಯಾನ ಸೂಚನೆ:",
    },
}


def generate_health_remarks(patient: dict, language: str = "en") -> dict:
    """Generate a short, non-diagnostic explanation using the Groq chat API.

    Returns a dictionary with success and remarks. Never raises provider errors
    into the web route so a valid contact can still be saved if AI is unavailable.
    """
    language = language if language in SUPPORTED_LANGUAGES else "en"
    language_name = SUPPORTED_LANGUAGES[language]
    language_headings = LANGUAGE_HEADINGS[language]
    patient_age = calculate_patient_age(patient.get("date_of_birth"))

    api_key = os.getenv("GROQ_API_KEY", "").strip()
    if not api_key:
        return {
            "success": False,
            "remarks": "AI remarks are pending. Add GROQ_API_KEY to your local .env file and select Regenerate AI Remarks.",
        }

    model = os.getenv("GROQ_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL
    client = Groq(api_key=api_key, timeout=25.0, max_retries=1)

    def format_value(value):
        return f"{float(value):.2f}".rstrip("0").rstrip(".")

    prompt = f"""
You are an educational health-information assistant for a patient blood-test management application.
Review the supplied information and generate five clear, point-wise educational observations.

OUTPUT LANGUAGE:
Write the complete response only in {language_name}. {LANGUAGE_INSTRUCTIONS[language]}
Do not include alternate translations, bilingual text, or multiple versions.
Do not add language labels to the response.
Keep point numbers, numerical readings, and standard units such as mg/dL and g/dL unchanged.

PATIENT INFORMATION:
- Current age derived from DOB: {patient_age}
- Sex: Not provided
- Fasting status: Not provided
- Date of blood collection: Not provided

BLOOD TEST VALUES:
- Glucose: {format_value(patient.get('glucose'))} mg/dL
- Haemoglobin: {format_value(patient.get('haemoglobin'))} g/dL
- Cholesterol: {format_value(patient.get('cholesterol'))} mg/dL

IMPORTANT UNIT AND TEST ASSUMPTIONS:
The original assessment does not specify measurement units. For this demonstration only, assume glucose is mg/dL, haemoglobin is g/dL, and cholesterol is total cholesterol in mg/dL. The cholesterol test type is not confirmed. Never silently convert units or invent test details. State these limitations only in the final interpretation note.

INTERPRETATION RULES:
1. Glucose:
   - State the entered value and give a concise preliminary interpretation under the assumed unit.
   - Do not assume fasting or non-fasting status. Fasting context belongs only in the final note, and must never be used to dismiss an extreme result.
2. Haemoglobin:
   - State the entered value. Do not assume sex or make unsupported normal/abnormal claims.
3. Cholesterol:
   - Treat the value as total cholesterol under the demonstration assumption; do not confuse it with LDL or HDL.
   - Cholesterol interpretation differs for people aged 19 or younger versus adults. Do not apply adult cutoffs to someone aged 19 or younger, and do not invent age-specific thresholds.
4. Use the calculated age only as context. If age is not available, do not guess it or make age-specific claims.
5. Identify particularly unusual values accurately and cautiously in the relevant result point or overall observation. Do not invent thresholds or laboratory reference ranges.
6. Never silently convert units or infer a cause. Do not diagnose, estimate disease probabilities, or recommend medication or treatment.
7. If a result may need prompt attention, state that plainly and make the practical recommendation in point 5. Do not present a potentially critical result as routine or minor.
8. Do not ask for or infer identifying patient information.

STRICT RESPONSE FORMAT:
Generate exactly one response in the selected language. Do not include a second-language copy.

{language_headings["title"]}

1. {language_headings["glucose"]}:
   State the entered glucose value and give a concise,
   preliminary interpretation under the assumed unit.
   Do not assume fasting or non-fasting status.

2. {language_headings["haemoglobin"]}:
   State the entered haemoglobin value.
   Give a cautious interpretation only when supported.
   Do not assume the patient's sex.

3. {language_headings["cholesterol"]}:
   State the entered cholesterol value.
   Interpret it as total cholesterol under the demonstration
   assumption. Do not confuse it with LDL or HDL.

4. {language_headings["overall"]}:
   Summarise the main findings in simple language.
   Highlight any particularly unusual values.

5. {language_headings["next_step"]}:
   Give one short, practical recommendation to review
   unusual results with a qualified healthcare professional.

{language_headings["interpretation_note"]}

After point 5, add one separate paragraph under this heading.
Translate the heading and the entire note into the selected
language. In one concise paragraph, explain that measurement
units are assumptions for this demonstration; glucose
interpretation depends on fasting status and test timing;
haemoglobin interpretation varies with age, sex, and laboratory
reference ranges; cholesterol interpretation depends on test
type, age at testing, and laboratory reference range; and the
results should be checked against the original laboratory
report. State that these AI remarks are educational information,
not a medical diagnosis or medical advice.

FORMATTING RULES:
- Put every numbered point on a separate line.
- Leave one blank line between each point.
- Use short, simple sentences and keep all five points concise.
- Keep each result point focused on its reading. Do not repeat
  missing-information warnings under the individual results.
- Do not repeatedly mention fasting status, sex, or laboratory
  reference ranges outside the final note.
- Put all limitations and medical warnings together in the single
  final note; do not repeat the note elsewhere.
- Do not make unsupported normal/abnormal claims or diagnose disease.
- Do not combine the numbered points into one paragraph or use a markdown table.
- Do not mix languages.
""".strip()

    try:
        completion = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You provide cautious, non-diagnostic health education. Follow the user instructions exactly."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
            max_completion_tokens=1024,
            reasoning_effort="low",
            reasoning_format="hidden",
        )
        content = completion.choices[0].message.content if completion.choices else ""
        content = (content or "").strip()
        if not content:
            raise ValueError("Groq returned an empty response.")
        return {"success": True, "remarks": content}
    except (APIConnectionError, APIStatusError, RateLimitError, ValueError) as exc:
        # Keep the diagnostic detail in the server console, not in the public UI.
        print(f"Groq API request failed: {type(exc).__name__}: {exc}")
        return {
            "success": False,
            "remarks": "AI remarks are currently unavailable. Check the Groq API key, model and internet connection, then select Regenerate AI Remarks.",
        }
    except Exception as exc:  # Defensive handling for unexpected SDK/runtime errors.
        print(f"Unexpected Groq integration error: {type(exc).__name__}: {exc}")
        return {
            "success": False,
            "remarks": "AI remarks are currently unavailable. Please retry after checking the Groq configuration.",
        }
