import pytest

from codex_rosetta.converters.content_transformer import ContentTransformer


@pytest.fixture
def ct():
    return ContentTransformer()


class TestResponsesInputToChatContent:
    def test_string_passthrough(self, ct):
        assert ct.responses_input_to_chat_content("hello") == "hello"

    def test_none(self, ct):
        assert ct.responses_input_to_chat_content(None) is None

    def test_input_text(self, ct):
        result = ct.responses_input_to_chat_content(
            [{"type": "input_text", "text": "hello"}]
        )
        assert result == "hello"  # single text part simplified to string

    def test_input_image(self, ct):
        result = ct.responses_input_to_chat_content(
            [{"type": "input_image", "image_url": "https://img.png", "detail": "high"}]
        )
        assert result == [
            {"type": "image_url", "image_url": {"url": "https://img.png", "detail": "high"}}
        ]

    def test_input_image_default_detail(self, ct):
        result = ct.responses_input_to_chat_content(
            [{"type": "input_image", "image_url": "https://img.png"}]
        )
        assert result[0]["image_url"]["detail"] == "auto"

    def test_input_file_with_url(self, ct):
        result = ct.responses_input_to_chat_content(
            [{"type": "input_file", "file_url": "https://doc.pdf", "filename": "doc.pdf"}]
        )
        # Single text part is simplified to string
        assert isinstance(result, str)
        assert "doc.pdf" in result

    def test_mixed_content(self, ct):
        result = ct.responses_input_to_chat_content([
            {"type": "input_text", "text": "describe this"},
            {"type": "input_image", "image_url": "https://img.png"},
        ])
        assert len(result) == 2
        assert result[0]["type"] == "text"
        assert result[1]["type"] == "image_url"

    def test_output_text_passthrough(self, ct):
        result = ct.responses_input_to_chat_content(
            [{"type": "output_text", "text": "assistant text"}]
        )
        assert result == "assistant text"

    def test_empty_list(self, ct):
        result = ct.responses_input_to_chat_content([])
        assert result is None


class TestChatContentToResponsesOutput:
    def test_string(self, ct):
        result = ct.chat_content_to_responses_output("hello world")
        assert result == [{"type": "output_text", "text": "hello world", "annotations": []}]

    def test_none(self, ct):
        assert ct.chat_content_to_responses_output(None) == []

    def test_text_part(self, ct):
        result = ct.chat_content_to_responses_output(
            [{"type": "text", "text": "hello"}]
        )
        assert result == [{"type": "output_text", "text": "hello", "annotations": []}]

    def test_empty_list(self, ct):
        assert ct.chat_content_to_responses_output([]) == []


class TestRefusal:
    def test_refusal_to_responses(self, ct):
        result = ct.refusal_to_responses("I cannot help with that")
        assert result == {"type": "refusal", "refusal": "I cannot help with that"}

    def test_none_refusal(self, ct):
        assert ct.refusal_to_responses(None) is None

    def test_empty_refusal(self, ct):
        assert ct.refusal_to_responses("") is None


class TestFlattenOutputContent:
    def test_string(self, ct):
        assert ct.flatten_output_content("hello") == "hello"

    def test_none(self, ct):
        assert ct.flatten_output_content(None) == ""

    def test_list_of_output_text(self, ct):
        result = ct.flatten_output_content([
            {"type": "output_text", "text": "line1"},
            {"type": "output_text", "text": "line2"},
        ])
        assert result == "line1\nline2"

    def test_list_of_text(self, ct):
        result = ct.flatten_output_content([
            {"type": "text", "text": "hello"},
        ])
        assert result == "hello"

    def test_mixed_strings_and_dicts(self, ct):
        result = ct.flatten_output_content(["plain text", {"type": "output_text", "text": "structured"}])
        assert "plain text" in result
        assert "structured" in result
