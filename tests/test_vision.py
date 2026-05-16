import json
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from models import ParsedTimetable, PerformanceSlot
from vision import VisionParseError, _build_repair_prompt, parse_timetable_image

FIXTURES = Path(__file__).parent / "fixtures"


def load_fixture_json() -> str:
    return (FIXTURES / "sample_response.json").read_text()


def _make_response(text: str) -> MagicMock:
    resp = MagicMock()
    resp.text = text
    return resp


# ---------------------------------------------------------------------------
# Unit tests — no Gemini API calls
# ---------------------------------------------------------------------------

def test_fixture_parses_to_valid_schema():
    data = json.loads(load_fixture_json())
    result = ParsedTimetable.model_validate(data)
    assert result.festival_name == "Summer Beats Festival 2026"
    assert len(result.performances) == 4
    assert result.performances[0].artist == "Billie Eilish"
    assert result.performances[0].start_time == "20:00"


def test_fixture_performance_fields():
    data = json.loads(load_fixture_json())
    result = ParsedTimetable.model_validate(data)
    billie = result.performances[0]
    assert billie.stage == "Main Stage"
    assert billie.end_time == "21:30"
    assert billie.date == "2026-08-15"


def test_repair_prompt_contains_bad_json():
    bad = '{"invalid": true'
    prompt = _build_repair_prompt(bad)
    assert bad in prompt
    assert "festival_name" in prompt


def test_parse_with_mocked_gemini_success():
    fixture_json = load_fixture_json()

    with patch("vision.genai.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.models.generate_content.return_value = _make_response(fixture_json)

        result = parse_timetable_image([(b"fake_image_bytes", "image/jpeg")])

    assert isinstance(result, ParsedTimetable)
    assert len(result.performances) == 4


def test_parse_with_multiple_images_sends_all_to_gemini():
    fixture_json = load_fixture_json()

    with patch("vision.genai.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.models.generate_content.return_value = _make_response(fixture_json)

        parse_timetable_image([
            (b"image_bytes_1", "image/jpeg"),
            (b"image_bytes_2", "image/png"),
        ])

    call_args = mock_client.models.generate_content.call_args
    contents = call_args.kwargs["contents"]
    # 이미지 2장 + 텍스트 프롬프트 1개 = 3개
    assert len(contents) == 3


def test_parse_with_markdown_fences_stripped():
    fixture_json = load_fixture_json()

    with patch("vision.genai.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.models.generate_content.return_value = _make_response(
            f"```json\n{fixture_json}\n```"
        )

        result = parse_timetable_image([(b"fake_image_bytes", "image/jpeg")])

    assert isinstance(result, ParsedTimetable)


def test_parse_raises_vision_parse_error_on_bad_response():
    with patch("vision.genai.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.models.generate_content.return_value = _make_response(
            "This is not JSON at all."
        )

        with pytest.raises(VisionParseError) as exc_info:
            parse_timetable_image([(b"fake_image_bytes", "image/jpeg")])

    assert "This is not JSON at all." in exc_info.value.raw_response


def test_parse_succeeds_on_second_attempt_after_repair():
    fixture_json = load_fixture_json()

    with patch("vision.genai.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.models.generate_content.side_effect = [
            _make_response("not json"),
            _make_response(fixture_json),
        ]

        result = parse_timetable_image([(b"fake_image_bytes", "image/jpeg")])

    assert isinstance(result, ParsedTimetable)
    assert mock_client.models.generate_content.call_count == 2


# ---------------------------------------------------------------------------
# Integration test — requires GEMINI_API_KEY and a real image file
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_parse_real_image():
    image_path = FIXTURES / "sample_timetable.jpg"
    if not image_path.exists():
        pytest.skip("No sample_timetable.jpg fixture found")
    if not os.getenv("GEMINI_API_KEY"):
        pytest.skip("GEMINI_API_KEY not set")

    image_bytes = image_path.read_bytes()
    result = parse_timetable_image([(image_bytes, "image/jpeg")])

    assert isinstance(result, ParsedTimetable)
    assert len(result.performances) > 0
    print(f"\nParsed {len(result.performances)} performances from real image")
    if result.parse_warnings:
        print(f"Warnings: {result.parse_warnings}")
