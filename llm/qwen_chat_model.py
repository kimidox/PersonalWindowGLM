from __future__ import annotations

from typing import Any, Optional

from .BaseChatModel import BaseChatModel


class QwenChatModel(BaseChatModel):
    """
    Qwen 系列实现：
    目前该项目使用 OpenAI 兼容的 tool/function call 参数格式，
    所以主要差异落在：
    - model 名称
    - 工具 schema
    """

    def __init__(self, model_name: str | None = None, **kwargs: Any) -> None:
        super().__init__(model_name=model_name, **kwargs)

    def build_tools(self) -> list[dict]:
        return self.build_functions_qwen()

    def build_functions_qwen(self):
        """严格适配本地 Qwen 服务端的工具调用格式（type + function 嵌套）"""
        return [
            {
                "type": "function",  # 必需：类型必须是 "function"
                "function": {  # 必需：嵌套的 function 对象（服务端要求的核心）
                    "name": "return_to_desktop",
                    "description": "Return to the desktop",
                    "parameters": {
                        "type": "object",
                        "properties": {},
                        "required": []
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "click",
                    "description": "Click at grid cell (gx, gy) shown on screenshot overlay; maps to cell center in screen pixels",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "x": {
                                "type": "number",
                                "description": "Grid column index gx (0=left), non-negative integer",
                                "minimum": 0
                            },
                            "y": {
                                "type": "number",
                                "description": "Grid row index gy (0=top), non-negative integer",
                                "minimum": 0
                            },
                            "button": {
                                "type": "string",
                                "enum": ["left", "right", "middle"],
                                "description": "Mouse button to click (left, right, middle)"
                            }
                        },
                        "required": ["x", "y"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "double_click",
                    "description": "Double click at grid cell (gx, gy) from screenshot overlay",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "x": {
                                "type": "number",
                                "description": "Grid column index gx (0=left)",
                                "minimum": 0
                            },
                            "y": {
                                "type": "number",
                                "description": "Grid row index gy (0=top)",
                                "minimum": 0
                            },
                            "button": {
                                "type": "string",
                                "enum": ["left", "right", "middle"],
                                "description": "Mouse button to double click (left, right, middle)"
                            }
                        },
                        "required": ["x", "y"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "right_click",
                    "description": "Right click at grid cell (gx, gy) from screenshot overlay",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "x": {
                                "type": "number",
                                "description": "Grid column index gx (0=left)",
                                "minimum": 0
                            },
                            "y": {
                                "type": "number",
                                "description": "Grid row index gy (0=top)",
                                "minimum": 0
                            }
                        },
                        "required": ["x", "y"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "move_to",
                    "description": "Move mouse to grid cell center (gx, gy) from screenshot overlay",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "x": {
                                "type": "number",
                                "description": "Grid column index gx (0=left)",
                                "minimum": 0
                            },
                            "y": {
                                "type": "number",
                                "description": "Grid row index gy (0=top)",
                                "minimum": 0
                            }
                        },
                        "required": ["x", "y"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "type_text",
                    "description": "Type text input to the active window",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "text": {
                                "type": "string",
                                "description": "Text content to type"
                            }
                        },
                        "required": ["text"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "press_key",
                    "description": "Press and release a single keyboard key",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "key": {
                                "type": "string",
                                "description": "Name of the key to press (e.g., 'enter', 'tab', 'a', '1')"
                            }
                        },
                        "required": ["key"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "hotkey",
                    "description": "Press a combination of keyboard keys (e.g., 'ctrl+c', 'alt+f4')",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "key": {
                                "type": "string",
                                "description": "Key combination (e.g., 'ctrl+c', 'alt+f4')"
                            }
                        },
                        "required": ["key"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "scroll",
                    "description": "Scroll mouse wheel; optional gx, gy to scroll at that grid cell",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "clicks": {
                                "type": "integer",
                                "description": "Number of scroll clicks (positive = up, negative = down)"
                            },
                            "x": {
                                "type": "number",
                                "description": "Optional grid column gx",
                                "minimum": 0
                            },
                            "y": {
                                "type": "number",
                                "description": "Optional grid row gy",
                                "minimum": 0
                            }
                        },
                        "required": ["clicks"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "open_app",
                    "description": "Open an application by its file path",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {
                                "type": "string",
                                "description": "Full file path to the application executable (e.g., 'C:\\Program Files\\Notepad++\\notepad++.exe')"
                            }
                        },
                        "required": ["path"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "wait",
                    "description": "Wait for a specified number of seconds",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "seconds": {
                                "type": "number",
                                "description": "Number of seconds to wait (supports decimal values)",
                                "minimum": 0.1
                            }
                        },
                        "required": ["seconds"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "screenshot",
                    "description": "Take a screenshot of the entire screen and return the file path",
                    "parameters": {
                        "type": "object",
                        "properties": {}
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "over",
                    "description": "Mark the current task as completed",
                    "parameters": {
                        "type": "object",
                        "properties": {}
                    }
                }
            }
        ]
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
    def request_llm_with_tools(self, messages: list[dict], tools: list[dict]) -> Optional[dict[str, str]]:
        response = self.get_client().chat.completions.create(
            model=self.model_name,
            messages=messages,
            tools=tools,
            tool_choice="auto",
            temperature=self.temperature,
            extra_body=self.extra_body,
        )
        msg = response.choices[0].message
        return self.extract_function_call(msg)