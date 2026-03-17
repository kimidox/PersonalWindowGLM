import json
import re
import base64
from pathlib import Path

import pyautogui
from openai import OpenAI
from executor import Executor
import config


def extract_json(text: str) -> list | None:
    """Extract JSON objects that contain an "action" or a "plan" key from text.

    This helper is used to decode the model's responses which may include
    actionable instructions ("action") and/or an accompanying high-level plan
    ("plan").
    """
    results = []
    # 优化正则表达式，确保能匹配独立的JSON对象
    patterns = [
        r'```json\s*(\{[\s\S]*?\})\s*```',  # 匹配带json标记的代码块
        r'```\s*(\{[\s\S]*?\})\s*```',  # 匹配不带json标记的代码块
        r'(\{[\s\S]*?"action"[\s\S]*?\})',  # 匹配包含action的JSON对象
        r'(\{[\s\S]*?"plan"[\s\S]*?\})',  # 匹配包含plan的JSON对象
    ]

    # 先去除文本两端的空白字符，避免干扰匹配
    text = text.strip()

    for pattern in patterns:
        matches = re.finditer(pattern, text, re.DOTALL)
        for match in matches:
            try:
                # 获取匹配到的JSON字符串
                json_str = match.group(1).strip()
                # 解析JSON字符串
                obj = json.loads(json_str)
                # 验证是否是字典且包含指定key
                if isinstance(obj, dict) and ("action" in obj or "plan" in obj):
                    # 避免重复添加相同的JSON对象
                    if obj not in results:
                        results.append(obj)
            except (json.JSONDecodeError, IndexError):
                # 解析失败时跳过该匹配项，继续处理下一个
                continue

    # 如果没有匹配到结果，检查文本本身是否就是一个合法的JSON对象
    if not results:
        try:
            obj = json.loads(text)
            if isinstance(obj, dict) and ("action" in obj or "plan" in obj):
                results.append(obj)
        except json.JSONDecodeError:
            pass
    if not results:
        raise Exception("解析异常，需重新生成指令json")

    return results





SYSTEM_PROMPT = SYSTEM_PROMPT = """你是一个Windows桌面自动化助手。你已经收到屏幕截图，请直接分析内容并返回操作指令。"""

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
                    "x": {"type": "integer"},
                    "y": {"type": "integer"},
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
                "properties": {"x": {"type": "integer"}, "y": {"type": "integer"}, "button": {"type": "string"}},
                "required": ["x", "y"]
            },
        },
        {
            "name": "right_click",
            "description": "Right click at coordinates",
            "parameters": {
                "type": "object",
                "properties": {"x": {"type": "integer"}, "y": {"type": "integer"}},
                "required": ["x", "y"]
            },
        },
        {
            "name": "move_to",
            "description": "Move mouse to coordinates",
            "parameters": {"type": "object", "properties": {"x": {"type": "integer"}, "y": {"type": "integer"}}, "required": ["x", "y"]},
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
                    "x": {"type": "integer"},
                    "y": {"type": "integer"}
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


def request_llm_with_functions(client: OpenAI, messages: list, functions: list)->dict:
    """调用 llm 支持 function_call 的路径，返回原始 resp 的字典形式"""
    response = client.chat.completions.create(
        model=config.MODEL_NAME,
        messages=messages,
        functions=functions,
        function_call="auto",
        temperature=0,
        extra_body={"enable_thinking": False}
    )
    resp = response.choices[0].message
    if isinstance(resp, dict) and resp.get("function_call"):
        return {"function_call": resp["function_call"]}
    else:
        return {"content": resp.get("content")}

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
    functions = build_functions()
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
            current_messages.append({"role": "function", "name": fname, "content": str(result)})
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
        
    def add_to_history(self, role: str, content):
        self.conversation_history.append({"role": role, "content": content})
        if len(self.conversation_history) > 20:
            self.conversation_history = self.conversation_history[-20:]
    
    def run(self, task: str, log_callback=None) -> str:
        self.iteration = 0
        
        llm_client = get_llm_client()
        
        # Step 1: Preliminary model pass to decide if a screenshot is needed
        current_screenshot = self.executor.screenshot()
        pre_actions = analyze_with_image(llm_client, f"任务: {task}",image_path=current_screenshot,log_callback=log_callback)
        log_callback(str(pre_actions), "response")
        return "完成"
