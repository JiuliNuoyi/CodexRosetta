from __future__ import annotations

from typing import Any


class ContentTransformer:
    """Convert content parts between Responses API and Chat Completions formats."""

    # Responses input content types -> Chat Completions content types
    INPUT_TYPE_MAP = {
        "input_text": "text",
        "input_image": "image_url",
        "input_file": "file",
    }

    # Reverse map for Chat Completions -> Responses output
    OUTPUT_TYPE_MAP = {
        "text": "output_text",
    }

    def responses_input_to_chat_content(
        self, content: str | list[dict[str, Any]] | None
    ) -> str | list[dict[str, Any]] | None:
        """Convert Responses API content to Chat Completions content format."""
        if content is None:
            return None
        if isinstance(content, str):
            return content
        if not isinstance(content, list):
            return content

        parts: list[dict[str, Any]] = []
        for part in content:
            converted = self._convert_input_part(part)
            if converted is not None:
                parts.append(converted)

        if not parts:
            return None
        if len(parts) == 1 and parts[0].get("type") == "text":
            return parts[0].get("text", "")
        return parts

    def _convert_input_part(self, part: dict[str, Any]) -> dict[str, Any] | None:
        part_type = part.get("type", "")

        if part_type == "input_text":
            return {"type": "text", "text": part.get("text", "")}

        elif part_type == "input_image":
            image_url = part.get("image_url", "")
            detail = part.get("detail", "auto")
            return {
                "type": "image_url",
                "image_url": {"url": image_url, "detail": detail},
            }

        elif part_type == "input_file":
            file_id = part.get("file_id")
            file_data = part.get("file_data")
            file_url = part.get("file_url")
            filename = part.get("filename", "file")

            if file_url:
                return {"type": "text", "text": f"[File: {filename}]({file_url})"}
            elif file_data:
                return {
                    "type": "image_url",
                    "image_url": {"url": f"data:application/octet-stream;base64,{file_data}"},
                }
            elif file_id:
                return {"type": "text", "text": f"[File ID: {file_id}]"}
            return None

        elif part_type == "text":
            return part

        elif part_type == "image_url":
            return part

        elif part_type == "output_text":
            return {"type": "text", "text": part.get("text", "")}

        else:
            return part

    def chat_content_to_responses_output(
        self, content: str | list[dict[str, Any]] | None
    ) -> list[dict[str, Any]]:
        """Convert Chat Completions content to Responses API output content parts."""
        if content is None:
            return []
        if isinstance(content, str):
            return [{"type": "output_text", "text": content, "annotations": []}]
        if not isinstance(content, list):
            return []

        parts: list[dict[str, Any]] = []
        for part in content:
            converted = self._convert_output_part(part)
            if converted is not None:
                parts.append(converted)
        return parts

    def _convert_output_part(self, part: dict[str, Any]) -> dict[str, Any] | None:
        part_type = part.get("type", "")

        if part_type == "text":
            return {"type": "output_text", "text": part.get("text", ""), "annotations": []}
        elif part_type == "output_text":
            return part
        elif part_type == "refusal":
            return part
        else:
            return part

    def refusal_to_responses(self, refusal: str | None) -> dict[str, Any] | None:
        """Convert Chat Completions refusal to Responses API refusal content part."""
        if not refusal:
            return None
        return {"type": "refusal", "refusal": refusal}

    def flatten_output_content(self, content: str | list[dict[str, Any]] | None) -> str:
        """Flatten Responses API output content to a plain string for tool results."""
        if content is None:
            return ""
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            texts = []
            for part in content:
                if isinstance(part, str):
                    texts.append(part)
                elif isinstance(part, dict):
                    if part.get("type") == "output_text":
                        texts.append(part.get("text", ""))
                    elif part.get("type") == "text":
                        texts.append(part.get("text", ""))
                    elif "text" in part:
                        texts.append(part["text"])
            return "\n".join(texts)
        return str(content)
