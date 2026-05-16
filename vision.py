import json

from google import genai
from google.genai import types

import config
from models import ParsedTimetable

_SYSTEM_PROMPT = """You are a precise data extractor for music festival timetables.
You will receive one or more images that together form a single festival timetable.
Extract ALL performance information exactly as shown across all images.
Return ONLY valid JSON matching the schema provided. No prose, no markdown fences, no backticks.
If information is missing or ambiguous, include it in parse_warnings.
Never guess or invent data not visible in the images."""

_USER_PROMPT = """Extract the festival timetable from the image(s) above.
If multiple images are provided, they all belong to the same festival — merge all performances into a single list.

Return JSON with this exact structure:
{
  "festival_name": string or null,
  "dates": [list of date strings as shown, e.g. "August 15" or "2026-08-15"],
  "timezone": string or null (e.g. "KST", "PST", "UTC+9" — only if visible in the images),
  "performances": [
    {
      "artist": "exact artist name from image",
      "stage": "exact stage name from image",
      "start_time": "HH:MM in 24-hour format",
      "end_time": "HH:MM in 24-hour format or null",
      "date": "date string for this performance or null if single-day event"
    }
  ],
  "parse_warnings": ["list any ambiguities, missing fields, or low-confidence reads"]
}

Rules:
- Convert all times to 24-hour format (e.g. 2:30 PM -> "14:30")
- If a stage appears in multiple columns, each column is a separate stage
- Preserve artist names exactly as written (accents, capitalisation, special characters)
- If two artists share a slot (b2b), create a separate entry for each with identical times
- Do not duplicate performances that appear in more than one image
- List parse_warnings for: missing end times, ambiguous dates, unreadable text regions"""


class VisionParseError(Exception):
    def __init__(self, message: str, raw_response: str = ""):
        self.raw_response = raw_response
        super().__init__(message)


def parse_timetable_image(images: list[tuple[bytes, str]]) -> ParsedTimetable:
    """
    Send one or more images to Gemini Vision and return merged timetable data.
    images: list of (image_bytes, mime_type) tuples
    """
    client = genai.Client(api_key=config.GEMINI_API_KEY)

    raw_response = ""
    for attempt in range(2):
        prompt = _USER_PROMPT if attempt == 0 else _build_repair_prompt(raw_response)

        parts: list = [
            types.Part.from_bytes(data=image_bytes, mime_type=mime_type)
            for image_bytes, mime_type in images
        ]
        parts.append(prompt)

        response = client.models.generate_content(
            model=config.GEMINI_MODEL,
            contents=parts,
            config=types.GenerateContentConfig(
                temperature=0,
                max_output_tokens=4096,
                system_instruction=_SYSTEM_PROMPT,
            ),
        )
        raw_response = response.text.strip()

        # Strip accidental markdown fences
        if raw_response.startswith("```"):
            raw_response = raw_response.split("```")[1]
            if raw_response.startswith("json"):
                raw_response = raw_response[4:]
            raw_response = raw_response.strip()

        try:
            data = json.loads(raw_response)
            return ParsedTimetable.model_validate(data)
        except Exception:
            continue  # try repair prompt on second attempt

    raise VisionParseError(
        "Could not parse timetable after 2 attempts. The images may be unclear or the format unsupported.",
        raw_response=raw_response,
    )


def _build_repair_prompt(bad_json: str) -> str:
    return f"""Your previous response was not valid JSON or did not match the required schema.

Previous response:
{bad_json}

Please fix the JSON and return ONLY the corrected JSON object with no additional text.
The required structure is:
{{
  "festival_name": string or null,
  "dates": [],
  "timezone": string or null,
  "performances": [{{"artist": "", "stage": "", "start_time": "", "end_time": null, "date": null}}],
  "parse_warnings": []
}}"""
