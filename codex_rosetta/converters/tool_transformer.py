from __future__ import annotations

import copy
from typing import Any

from codex_rosetta.models.common import (
    BUILTIN_TOOL_TYPES,
    ROSETTA_TOOL_PREFIX,
    ConversionContext,
    is_simulated_function,
    make_simulated_function_name,
)


class ToolTransformer:
    """Convert tool definitions between Responses API and Chat Completions formats."""

    def __init__(self, builtin_registry: Any = None) -> None:
        self._registry = builtin_registry

    def convert_tools(
        self, responses_tools: list[dict[str, Any]], context: ConversionContext
    ) -> list[dict[str, Any]]:
        """Convert Responses API tool definitions to Chat Completions format.

        - Function tools: flatten structure (name/parameters/description from nested `function` key)
        - Built-in tools: simulate as function tools with __rosetta_ prefix
        """
        if not responses_tools:
            return []

        chat_tools: list[dict[str, Any]] = []

        for tool in responses_tools:
            tool_type = tool.get("type", "function")
            converted = self._convert_tool(tool, tool_type, context)
            if converted is not None:
                chat_tools.append(converted)

        return chat_tools

    def _convert_tool(
        self, tool: dict[str, Any], tool_type: str, context: ConversionContext
    ) -> dict[str, Any] | None:
        if tool_type == "function":
            return self._convert_function_tool(tool)

        elif tool_type in BUILTIN_TOOL_TYPES:
            return self._convert_builtin_tool(tool, tool_type, context)

        elif tool_type == "custom":
            return self._convert_custom_tool(tool)

        # Unknown tool type — try to pass through
        return None

    def _convert_function_tool(self, tool: dict[str, Any]) -> dict[str, Any]:
        """Responses function tool -> Chat Completions function tool.

        Responses: {type: "function", name: "...", parameters: {...}, description: "...", strict: true}
        ChatCC:    {type: "function", function: {name: "...", parameters: {...}, description: "...", strict: true}}
        """
        func_def: dict[str, Any] = {}

        if "name" in tool:
            func_def["name"] = tool["name"]
        if "parameters" in tool:
            func_def["parameters"] = tool["parameters"]
        if "description" in tool:
            func_def["description"] = tool["description"]
        if "strict" in tool:
            func_def["strict"] = tool["strict"]

        return {"type": "function", "function": func_def}

    def _convert_builtin_tool(
        self, tool: dict[str, Any], tool_type: str, context: ConversionContext
    ) -> dict[str, Any]:
        """Convert a built-in tool to a simulated function tool."""
        sim_name = make_simulated_function_name(tool_type)
        context.register_builtin_tool(sim_name, tool_type)

        func_def = self._get_builtin_function_definition(tool_type, tool)
        return {"type": "function", "function": func_def}

    def _get_builtin_function_definition(
        self, tool_type: str, tool: dict[str, Any]
    ) -> dict[str, Any]:
        """Generate function definition for a simulated built-in tool."""
        definitions = {
            "web_search": {
                "name": make_simulated_function_name("web_search"),
                "description": "Search the web for information. Use this to find up-to-date information on any topic. Call this when you need to look something up online.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "The search query string",
                        },
                        "search_context_size": {
                            "type": "string",
                            "enum": ["low", "medium", "high"],
                            "description": "Amount of context window for search results",
                        },
                        "filters": {
                            "type": "object",
                            "properties": {
                                "allowed_domains": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                    "description": "Allowed domains for the search",
                                },
                            },
                        },
                        "user_location": {
                            "type": "object",
                            "properties": {
                                "city": {"type": "string"},
                                "country": {"type": "string"},
                                "region": {"type": "string"},
                                "timezone": {"type": "string"},
                            },
                        },
                    },
                    "required": ["query"],
                },
            },
            "web_search_2025_08_26": {
                "name": make_simulated_function_name("web_search_2025_08_26"),
                "description": "Search the web for information. Use this to find up-to-date information on any topic. Call this when you need to look something up online.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "The search query string",
                        },
                        "search_context_size": {
                            "type": "string",
                            "enum": ["low", "medium", "high"],
                            "description": "Amount of context window for search results",
                        },
                        "filters": {
                            "type": "object",
                            "properties": {
                                "allowed_domains": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                    "description": "Allowed domains for the search",
                                },
                            },
                        },
                        "user_location": {
                            "type": "object",
                            "properties": {
                                "city": {"type": "string"},
                                "country": {"type": "string"},
                                "region": {"type": "string"},
                                "timezone": {"type": "string"},
                            },
                        },
                    },
                    "required": ["query"],
                },
            },
            "file_search": {
                "name": make_simulated_function_name("file_search"),
                "description": "Search through files and documents. Simulates the built-in file_search tool.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "The search query"},
                        "max_num_results": {
                            "type": "integer",
                            "description": "Maximum number of results",
                            "default": 10,
                        },
                    },
                    "required": ["query"],
                },
            },
            "computer_use_preview": {
                "name": make_simulated_function_name("computer_use_preview"),
                "description": "Use a computer interface (click, type, scroll, screenshot). Simulates the built-in computer_use tool.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "action": {
                            "type": "object",
                            "description": "The computer action to perform",
                            "properties": {
                                "type": {
                                    "type": "string",
                                    "enum": ["click", "double_click", "drag", "type", "scroll", "screenshot", "wait", "move"],
                                },
                                "x": {"type": "integer"},
                                "y": {"type": "integer"},
                                "text": {"type": "string"},
                                "button": {"type": "string", "enum": ["left", "right", "middle"]},
                                "direction": {"type": "string", "enum": ["up", "down"]},
                            },
                            "required": ["type"],
                        },
                    },
                    "required": ["action"],
                },
            },
            "computer": {
                "name": make_simulated_function_name("computer"),
                "description": "Use a computer interface. Simulates the built-in computer tool.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "action": {
                            "type": "object",
                            "description": "The computer action to perform",
                            "properties": {
                                "type": {"type": "string"},
                            },
                            "required": ["type"],
                        },
                    },
                    "required": ["action"],
                },
            },
            "code_interpreter": {
                "name": make_simulated_function_name("code_interpreter"),
                "description": "Execute code in an interpreter. Simulates the built-in code_interpreter tool.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "code": {"type": "string", "description": "The code to execute"},
                        "language": {"type": "string", "description": "Programming language"},
                    },
                    "required": ["code"],
                },
            },
            "image_generation": {
                "name": make_simulated_function_name("image_generation"),
                "description": "Generate or edit images. Simulates the built-in image_generation tool.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "prompt": {"type": "string", "description": "Description of the image to generate"},
                        "size": {
                            "type": "string",
                            "enum": ["1024x1024", "1024x1536", "1536x1024", "auto"],
                            "default": "auto",
                        },
                        "quality": {
                            "type": "string",
                            "enum": ["low", "medium", "high", "auto"],
                            "default": "auto",
                        },
                    },
                    "required": ["prompt"],
                },
            },
        }

        if tool_type in definitions:
            return copy.deepcopy(definitions[tool_type])

        # Generic fallback
        return {
            "name": make_simulated_function_name(tool_type),
            "description": f"Simulates the built-in {tool_type} tool.",
            "parameters": {
                "type": "object",
                "properties": {
                    "input": {"type": "string", "description": f"Input for {tool_type}"},
                },
            },
        }

    def _convert_custom_tool(self, tool: dict[str, Any]) -> dict[str, Any]:
        """Convert a custom tool to Chat Completions format."""
        custom = tool.get("custom", tool)
        return {
            "type": "custom",
            "custom": {
                "name": custom.get("name", ""),
                "description": custom.get("description", ""),
                "format": custom.get("format", {"type": "text"}),
            },
        }

    def convert_tool_choice(
        self, tool_choice: Any, context: ConversionContext
    ) -> Any:
        """Convert tool_choice between formats.

        Responses: {"type": "function", "name": "..."}
        ChatCC:    {"type": "function", "function": {"name": "..."}}
        """
        if tool_choice is None:
            return None
        if isinstance(tool_choice, str):
            return tool_choice

        if isinstance(tool_choice, dict):
            tc_type = tool_choice.get("type", "")

            if tc_type == "function":
                name = tool_choice.get("name", "")
                # Check if this maps to a simulated built-in tool
                sim_name = context.original_tool_types.get(name, name) if is_simulated_function(name) else name
                return {
                    "type": "function",
                    "function": {"name": name},
                }

            elif tc_type == "custom":
                custom = tool_choice.get("custom", {})
                return {
                    "type": "custom",
                    "custom": {"name": custom.get("name", "")},
                }

        return tool_choice
