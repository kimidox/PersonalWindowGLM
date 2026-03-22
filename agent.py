import json
import re
import base64
from pathlib import Path

import pyautogui
from openai import OpenAI
from openai.types.chat import ChatCompletionMessage

from executor import Executor
import config






SYSTEM_PROMPT = """你是一个Windows桌面自动化助手。你已经收到屏幕截图，请直接分析内容并调用指定的函数完成操作。必须使用提供的functions列表中的函数"""

CLIENT = None


def get_llm_client():
    global CLIENT
    if CLIENT is None:
        CLIENT = OpenAI(
            api_key=config.OPENAI_API_KEY,
            base_url=config.OPENAI_BASE_URL
        )
    return CLIENT


def build_functions():
    """Register OpenAI function_call interfaces for local automation."""
    return [
        {"name": "return_to_desktop", "description": "Return to the desktop", "parameters": {"type": "object", "properties": {}, "required": []}},
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
            "parameters": {"type": "object", "properties": {"seconds": {"type": "integer"}}, "required": ["seconds"]},
        },
        {
            "name": "screenshot",
            "description": "Take a screenshot and return the path",
            "parameters": {"type": "object", "properties": {}} ,
        },
        {
            "name": "over",
            "description":"task over",
            "parameters": {"type": "object", "properties": {}} ,
        }
    ]
def build_functions_openai():
    """Register OpenAI function_call interfaces for local automation (fully compatible with OpenAI spec)."""
    return [
        {
            "name": "return_to_desktop",
            "description": "Return to the desktop",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
                "additionalProperties": False
            }
        },
        {
            "name": "click",
            "description": "Click at coordinates",
            "parameters": {
                "type": "object",
                "properties": {
                    "x": {
                        "type": "number",  # 修改为 number 以支持 0.0-1.0 的浮点数
                        "description": "Horizontal coordinate (normalized), value range: 0.0-1.0",
                        "minimum": 0.0,
                        "maximum": 1.0
                    },
                    "y": {
                        "type": "number",  # 修改为 number 以支持 0.0-1.0 的浮点数
                        "description": "Vertical coordinate (normalized), value range: 0.0-1.0",
                        "minimum": 0.0,
                        "maximum": 1.0
                    },
                    "button": {
                        "type": "string",
                        "description": "Mouse button to click (left, right, middle)",
                        "enum": ["left", "right", "middle"]  # 添加枚举值增强规范性
                    }
                },
                "required": ["x", "y"],
                "additionalProperties": False  # 禁止额外参数，符合 OpenAI 最佳实践
            },
        },
        {
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
                        "description": "Mouse button to double click (left, right, middle)",
                        "enum": ["left", "right", "middle"]
                    }
                },
                "required": ["x", "y"],
                "additionalProperties": False
            },
        },
        {
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
                    },
                },
                "required": ["x", "y"],
                "additionalProperties": False
            },
        },
        {
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
                    },
                },
                "required": ["x", "y"],
                "additionalProperties": False
            },
        },
        {
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
                "required": ["text"],
                "additionalProperties": False
            },
        },
        {
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
                "required": ["key"],
                "additionalProperties": False
            },
        },
        {
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
                "required": ["key"],
                "additionalProperties": False
            },
        },
        {
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
                    },
                },
                "required": ["clicks"],
                "additionalProperties": False
            },
        },
        {
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
                "required": ["path"],
                "additionalProperties": False
            },
        },
        {
            "name": "wait",
            "description": "Wait for a specified number of seconds",
            "parameters": {
                "type": "object",
                "properties": {
                    "seconds": {
                        "type": "number",  # 修改为 number 支持小数秒
                        "description": "Number of seconds to wait (supports decimal values)",
                        "minimum": 0.1  # 设置最小等待时间
                    }
                },
                "required": ["seconds"],
                "additionalProperties": False
            },
        },
        {
            "name": "screenshot",
            "description": "Take a screenshot of the entire screen and return the file path",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
                "additionalProperties": False
            },
        },
        {
            "name": "over",
            "description": "Mark the current task as completed",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
                "additionalProperties": False
            }
        }
    ]
def build_functions_qwen():
    """严格适配本地 Qwen 服务端的工具调用格式（type + function 嵌套）"""
    return [
        {
            "type": "function",  # 必需：类型必须是 "function"
            "function": {       # 必需：嵌套的 function 对象（服务端要求的核心）
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

def request_llm_with_functions(client: OpenAI, messages: list, functions: list)->dict:
    """调用 llm 支持 function_call 的路径，返回原始 resp 的字典形式"""
    response = client.chat.completions.create(
        model=config.MODEL_NAME,
        messages=messages,
        tools=functions,
        tool_choice="auto",
        temperature=0,
        extra_body={"enable_thinking": False}
    )
    resp = response.choices[0].message
    # 解析function_call,不同的大模型返回的字段可能不一样

    if config.MODEL_NAME=="glm-5":
        if isinstance(resp, ChatCompletionMessage):
            if hasattr(resp,"tool_calls"):
                function_call={"name":resp.tool_calls[0].function.name,"arguments":resp.tool_calls[0].function.arguments}
    if config.MODEL_NAME.startswith("qwen3.5"):
        if isinstance(resp, ChatCompletionMessage):
            if hasattr(resp,"tool_calls"):
                function_call = {"name": resp.tool_calls[0].function.name,
                                 "arguments": resp.tool_calls[0].function.arguments}
    else:
        if isinstance(resp, ChatCompletionMessage):
            if hasattr(resp,"tool_calls"):
                function_call = {"name": resp.tool_calls[0].function.name,
                                 "arguments": resp.tool_calls[0].function.arguments}
    return {"function_call": function_call}

def execute_function_call(fname: str, args: dict, executor: Executor)->str:
    action = {"action": fname}
    if args:
        action.update(args)
    return executor.execute_action(action)

def encode_image(image_path: str) -> str:
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")


def analyze_with_image(client: OpenAI, user_prompt: str, image_path: str | None = None, conversation_history: list | None = None, executor: Executor | None = None,log_callback=None) -> str:
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    
    if conversation_history:
        for msg in conversation_history:
            messages.append(msg)
    
    user_content = []
    if user_prompt:
        user_content.append({"type": "text", "text": user_prompt})
    
    if image_path:
        base64_image = encode_image(image_path)
        user_content.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/png;base64,{base64_image}"}
        })
    
    if user_content:
        messages.append({"role": "user", "content": user_content})

    # 使用 function_call 模式进行自动化动作执行，同时保留 pre-check/plan 的信息流
    functions = build_functions_qwen()
    # 逐步通过函数调用与模型对话，执行本地动作
    current_messages = list(messages)
    if executor is None:
        executor = Executor(".")

    while True:
        resp = request_llm_with_functions(client, current_messages, functions)
        # 模型返回了 function_call
        if isinstance(resp, dict) and resp.get("function_call"):
            fc = resp["function_call"]
            fname = fc.get("name")
            arg_str = fc.get("arguments") or "{}"
            try:
                args = json.loads(arg_str)
            except Exception as e:
                args = {}
            # 执行本地函数
            log_callback(str({fname: {"args":args}}), "response")
            result = execute_function_call(fname, args, executor)
            log_callback(str({fname:{"result":result}}), "response")
            if result=="任务完成":
                log_callback("任务完成", "response")
                return "任务完成"
            current_messages.append({"role": "tool", "name": fname, "content": str(result)})
            current_screenshot = executor.screenshot()

            current_messages.append({"role": "user", "content": [{"type": "image_url", "image_url": {"url": f"data:image/png;base64,{encode_image(current_screenshot)}"}}]})
            continue
        else:
            raise  Exception("未知的响应类型")
    log_callback("任务异常", "response")
    return "任务异常"




class Agent:
    def __init__(self, work_dir: str):
        self.work_dir = work_dir
        self.executor = Executor(work_dir)
        self.conversation_history = []
        self.iteration = 0
        self.max_iterations = config.MAX_ITERATIONS

    
    def run(self, task: str, log_callback=None) -> str:
        
        llm_client = get_llm_client()
        
        # Step 1: Preliminary model pass to decide if a screenshot is needed
        current_screenshot = self.executor.screenshot()
        pre_actions = analyze_with_image(llm_client, f"任务: {task}",image_path=current_screenshot,log_callback=log_callback)
        log_callback(str(pre_actions), "response")
        return "完成"
