from __future__ import annotations

from typing import Any

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
                    "description": "Click at coordinates",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "x": {
                                "type": "number",
                                "description": "Horizontal coordinate (normalized), value range: 0.0-1.0",
                                "minimum": 0.0,
                                "maximum": 1.0
                            },
                            "y": {
                                "type": "number",
                                "description": "Vertical coordinate (normalized), value range: 0.0-1.0",
                                "minimum": 0.0,
                                "maximum": 1.0
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
                    "description": "Double click at coordinates",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "x": {
                                "type": "number",
                                "description": "Horizontal coordinate (normalized), value range: 0.0-1.0",
                                "minimum": 0.0,
                                "maximum": 1.0
                            },
                            "y": {
                                "type": "number",
                                "description": "Vertical coordinate (normalized), value range: 0.0-1.0",
                                "minimum": 0.0,
                                "maximum": 1.0
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
                    "description": "Right click at coordinates",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "x": {
                                "type": "number",
                                "description": "Horizontal coordinate (normalized), value range: 0.0-1.0",
                                "minimum": 0.0,
                                "maximum": 1.0
                            },
                            "y": {
                                "type": "number",
                                "description": "Vertical coordinate (normalized), value range: 0.0-1.0",
                                "minimum": 0.0,
                                "maximum": 1.0
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
                    "description": "Move mouse to coordinates",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "x": {
                                "type": "number",
                                "description": "Horizontal coordinate (normalized), value range: 0.0-1.0",
                                "minimum": 0.0,
                                "maximum": 1.0
                            },
                            "y": {
                                "type": "number",
                                "description": "Vertical coordinate (normalized), value range: 0.0-1.0",
                                "minimum": 0.0,
                                "maximum": 1.0
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
                    "description": "Scroll mouse wheel at specified coordinates",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "clicks": {
                                "type": "integer",
                                "description": "Number of scroll clicks (positive = up, negative = down)"
                            },
                            "x": {
                                "type": "number",
                                "description": "Horizontal coordinate (normalized), value range: 0.0-1.0",
                                "minimum": 0.0,
                                "maximum": 1.0
                            },
                            "y": {
                                "type": "number",
                                "description": "Vertical coordinate (normalized), value range: 0.0-1.0",
                                "minimum": 0.0,
                                "maximum": 1.0
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