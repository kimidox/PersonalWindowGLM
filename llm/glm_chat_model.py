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
    def extract_function_call(self, message: Any) -> Optional[dict[str, str]]:
        """
        尝试从模型输出中提取工具调用信息。
        返回格式：{"name": ..., "arguments": "...json..."} 或 None
        """

        tool_calls = getattr(message, "tool_calls", None)
        if not tool_calls:
            return None

        first = tool_calls[0]
        func = getattr(first, "function", None)
        if func is None:
            return None

        name = getattr(func, "name", None)
        arguments = getattr(func, "arguments", None) or "{}"
        if not name:
            return None

        return {"name": str(name), "arguments": str(arguments)}

    def build_tools(self) -> list[dict]:
        return self.build_functions()

    def build_functions(self):
        """Register OpenAI function_call interfaces for local automation."""
        return [
            {"name": "return_to_desktop", "description": "Return to the desktop",
             "parameters": {"type": "object", "properties": {}, "required": []}},
            {
                "name": "click",
                "description": "Click at coordinates",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "x": {
                            "type": "integer",
                            "description": "Horizontal coordinate (normalized), value range: 0.0-1.0",
                            "minimum": 0.0,
                            "maximum": 1.0
                        },
                        "y": {
                            "type": "integer",
                            "description": "Vertical coordinate (normalized), value range: 0.0-1.0",
                            "minimum": 0.0,
                            "maximum": 1.0
                        },
                        "button": {"type": "string"}
                    },
                    "required": ["x", "y"]
                },
            },
            {
                "name": "double_click",
                "description": "Double click at coordinates",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "x": {
                            "type": "integer",
                            "description": "Horizontal coordinate (normalized), value range: 0.0-1.0",
                            "minimum": 0.0,
                            "maximum": 1.0
                        },
                        "y": {
                            "type": "integer",
                            "description": "Vertical coordinate (normalized), value range: 0.0-1.0",
                            "minimum": 0.0,
                            "maximum": 1.0
                        },
                        "button": {"type": "string"}
                    },
                    "required": ["x", "y"]
                },
            },
            {
                "name": "right_click",
                "description": "Right click at coordinates",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "x": {
                            "type": "integer",
                            "description": "Horizontal coordinate (normalized), value range: 0.0-1.0",
                            "minimum": 0.0,
                            "maximum": 1.0
                        },
                        "y": {
                            "type": "integer",
                            "description": "Vertical coordinate (normalized), value range: 0.0-1.0",
                            "minimum": 0.0,
                            "maximum": 1.0
                        },
                    },
                    "required": ["x", "y"]
                },
            },
            {
                "name": "move_to",
                "description": "Move mouse to coordinates",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "x": {
                            "type": "integer",
                            "description": "Horizontal coordinate (normalized), value range: 0.0-1.0",
                            "minimum": 0.0,
                            "maximum": 1.0
                        },
                        "y": {
                            "type": "integer",
                            "description": "Vertical coordinate (normalized), value range: 0.0-1.0",
                            "minimum": 0.0,
                            "maximum": 1.0
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
                "description": "Scroll",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "clicks": {"type": "integer"},
                        "x": {
                            "type": "integer",
                            "description": "Horizontal coordinate (normalized), value range: 0.0-1.0",
                            "minimum": 0.0,
                            "maximum": 1.0
                        },
                        "y": {
                            "type": "integer",
                            "description": "Vertical coordinate (normalized), value range: 0.0-1.0",
                            "minimum": 0.0,
                            "maximum": 1.0
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