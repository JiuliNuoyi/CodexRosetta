import secrets
import time

_PREFIXES = {
    "response": "resp",
    "message": "msg",
    "function_call": "fc",
    "function_call_output": "fco",
    "web_search": "ws",
    "file_search": "fs",
    "computer_call": "cu",
    "code_interpreter": "ci",
    "reasoning": "rs",
    "image_generation": "ig",
    "custom_tool_call": "ctc",
    "mcp_call": "mcp",
}


def generate_id(item_type: str = "response") -> str:
    prefix = _PREFIXES.get(item_type, item_type)
    return f"{prefix}_{secrets.token_hex(12)}"


def generate_response_id() -> str:
    return generate_id("response")


def generate_item_id(item_type: str) -> str:
    return generate_id(item_type)


def unix_timestamp() -> float:
    return time.time()
