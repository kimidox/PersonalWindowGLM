from __future__ import annotations

from typing import Any, Optional

from .BaseChatModel import BaseChatModel


class GLMChatModel(BaseChatModel):
    """
    GLM 实现：
    与当前项目的 Qwen tool schema 相同（均为 type/function 嵌套）。
    不同模型的 tool_calls 解析逻辑已统一在 BaseChatModel。
    """

    def __init__(self, model_name: str | None = None, **kwargs: Any) -> None:
        super().__init__(model_name=model_name, **kwargs)

    def request_llm_with_tools(self, messages: list[dict], tools: list[dict]) -> Optional[dict[str, str]]:
        response = self.get_client().chat.completions.create(
            model=self.model_name,
            messages=messages,
            functions=tools,
            function_call="auto",
            temperature=self.temperature,
            extra_body=self.extra_body,
        )
        msg = response.choices[0].message
        return self.extract_function_call(msg)

    def complete_with_tools(self, messages: list[dict], tools: list[dict]) -> Any:
        response = self.get_client().chat.completions.create(
            model=self.model_name,
            messages=messages,
            functions=tools,
            function_call="auto",
            temperature=self.temperature,
            extra_body=self.extra_body,
        )
        return response.choices[0].message

    def build_tools(self) -> list[dict]:
        return self.build_functions()

    def build_functions(self):
        """Register OpenAI function_call interfaces for local automation."""
        return [
            {"name": "return_to_desktop", "description": "Return to the desktop",
             "parameters": {"type": "object", "properties": {}, "required": []}},
            {
                "name": "click",
                "description": "Click at grid cell from screenshot overlay (gx, gy); cell center maps to screen pixels",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "x": {
                            "type": "integer",
                            "description": "Grid column index gx (0=left), must match screenshot grid labels",
                            "minimum": 0
                        },
                        "y": {
                            "type": "integer",
                            "description": "Grid row index gy (0=top), must match screenshot grid labels",
                            "minimum": 0
                        },
                        "button": {"type": "string"}
                    },
                    "required": ["x", "y"]
                },
            },
            {
                "name": "double_click",
                "description": "Double click at grid cell (gx, gy) from screenshot overlay",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "x": {
                            "type": "integer",
                            "description": "Grid column index gx (0=left)",
                            "minimum": 0
                        },
                        "y": {
                            "type": "integer",
                            "description": "Grid row index gy (0=top)",
                            "minimum": 0
                        },
                        "button": {"type": "string"}
                    },
                    "required": ["x", "y"]
                },
            },
            {
                "name": "right_click",
                "description": "Right click at grid cell (gx, gy) from screenshot overlay",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "x": {
                            "type": "integer",
                            "description": "Grid column index gx (0=left)",
                            "minimum": 0
                        },
                        "y": {
                            "type": "integer",
                            "description": "Grid row index gy (0=top)",
                            "minimum": 0
                        },
                    },
                    "required": ["x", "y"]
                },
            },
            {
                "name": "move_to",
                "description": "Move mouse to grid cell center (gx, gy) from screenshot overlay",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "x": {
                            "type": "integer",
                            "description": "Grid column index gx (0=left)",
                            "minimum": 0
                        },
                        "y": {
                            "type": "integer",
                            "description": "Grid row index gy (0=top)",
                            "minimum": 0
                        },
                    }, "required": ["x", "y"]},
            },
            {
                "name": "type_text",
                "description": "Type text",
                "parameters": {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]},
            },
            {
                "name": "press_key",
                "description": "Press a single key",
                "parameters": {"type": "object", "properties": {"key": {"type": "string"}}, "required": ["key"]},
            },
            {
                "name": "hotkey",
                "description": "Press a combination of keys",
                "parameters": {"type": "object", "properties": {"key": {"type": "string"}}, "required": ["key"]},
            },
            {
                "name": "scroll",
                "description": "Scroll; optional gx, gy to scroll at that grid cell center",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "clicks": {"type": "integer"},
                        "x": {
                            "type": "integer",
                            "description": "Optional grid column gx if scrolling at a cell",
                            "minimum": 0
                        },
                        "y": {
                            "type": "integer",
                            "description": "Optional grid row gy if scrolling at a cell",
                            "minimum": 0
                        },
                    },
                    "required": ["clicks"]
                },
            },
            {
                "name": "open_app",
                "description": "Open an application by path",
                "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]},
            },
            {
                "name": "wait",
                "description": "Wait for a number of seconds",
                "parameters": {"type": "object", "properties": {"seconds": {"type": "integer"}},
                               "required": ["seconds"]},
            },
            {
                "name": "screenshot",
                "description": "Take a screenshot and return the path",
                "parameters": {"type": "object", "properties": {}},
            },
            {
                "name": "over",
                "description": "Mark the current task as successfully completed and terminate the current execution flow. This function should only be called when all objectives have been fulfilled and no further actions are required.",
                "parameters": {"type": "object", "properties": {}},
            }
        ]