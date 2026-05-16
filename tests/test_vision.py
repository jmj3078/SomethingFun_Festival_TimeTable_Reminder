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


# ---------------------------------------------------------------------------
# Unit tests — no Claude API calls
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


def _make_mock_client(responses: list):
    """Helper: returns a patched Anthropic client whose messages.create yields responses in order."""
    with patch("vision.anthropic.Anthropic") as mock_anthropic:
        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client
        if len(responses) == 1:
            mock_client.messages.create.return_value = responses[0]
        else:
            mock_client.messages.create.side_effect = responses
        yield mock_client


def _make_message(text: str):
    msg = MagicMock()
    msg.content = [MagicMock(text=text)]
    return msg


def test_parse_with_mocked_claude_success():
    fixture_json = load_fixture_json()

    with patch("vision.anthropic.Anthropic") as mock_anthropic:
        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client
        mock_client.messages.create.return_value = _make_message(fixture_json)

        result = parse_timetable_image([(b"fake_image_bytes", "image/jpeg")])

    assert isinstance(result, ParsedTimetable)
    assert len(result.performances) == 4


def test_parse_with_multiple_images_sends_all_to_claude():
    fixture_json = load_fixture_json()

    with patch("vision.anthropic.Anthropic") as mock_anthropic:
        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client
        mock_client.messages.create.return_value = _make_message(fixture_json)

        parse_timetable_image([
            (b"image_bytes_1", "image/jpeg"),
            (b"image_bytes_2", "image/png"),
        ])

    call_args = mock_client.messages.create.call_args
    content = call_args.kwargs["messages"][0]["content"]
    image_blocks = [c for c in content if c["type"] == "image"]
    assert len(image_blocks) == 2
    assert image_blocks[0]["source"]["media_type"] == "image/jpeg"
    assert image_blocks[1]["source"]["media_type"] == "image/png"


def test_parse_with_markdown_fences_stripped():
    fixture_json = load_fixture_json()

    with patch("vision.anthropic.Anthropic") as mock_anthropic:
        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client
        mock_client.messages.create.return_value = _make_message(f"```json\n{fixture_json}\n```")

        result = parse_timetable_image([(b"fake_image_bytes", "image/jpeg")])

    assert isinstance(result, ParsedTimetable)


def test_parse_raises_vision_parse_error_on_bad_response():
    with patch("vision.anthropic.Anthropic") as mock_anthropic:
        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client
        mock_client.messages.create.return_value = _make_message("This is not JSON at all.")

        with pytest.raises(VisionParseError) as exc_info:
            parse_timetable_image([(b"fake_image_bytes", "image/jpeg")])

    assert "This is not JSON at all." in exc_info.value.raw_response


def test_parse_succeeds_on_second_attempt_after_repair():
    fixture_json = load_fixture_json()

    with patch("vision.anthropic.Anthropic") as mock_anthropic:
        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client
        mock_client.messages.create.side_effect = [
            _make_message("not json"),
            _make_message(fixture_json),
        ]

        result = parse_timetable_image([(b"fake_image_bytes", "image/jpeg")])

    assert isinstance(result, ParsedTimetable)
    assert mock_client.messages.create.call_count == 2


# ---------------------------------------------------------------------------
# Integration test — requires ANTHROPIC_API_KEY and a real image file
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_parse_real_image():
    image_path = FIXTURES / "sample_timetable.jpg"
    if not image_path.exists():
        pytest.skip("No sample_timetable.jpg fixture found")
    if not os.getenv("ANTHROPIC_API_KEY"):
        pytest.skip("ANTHROPIC_API_KEY not set")

    image_bytes = image_path.read_bytes()
    result = parse_timetable_image([(image_bytes, "image/jpeg")])

    assert isinstance(result, ParsedTimetable)
    assert len(result.performances) > 0
    print(f"\nParsed {len(result.performances)} performances from real image")
    if result.parse_warnings:
        print(f"Warnings: {result.parse_warnings}")
