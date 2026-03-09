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

    return results if results else None





SYSTEM_PROMPT = """你是一个Windows桌面自动化助手。你已经收到了屏幕截图，请直接分析截图内容并返回操作指令。

## 可用的操作命令：
1. **返回桌面** - 按Win+D返回Windows桌面
2. **点击(x, y)** - 在指定坐标点击左键
3. **双击(x, y)** - 在指定坐标双击左键
4. **右键点击(x, y)** - 在指定坐标点击右键
5. **输入(text)** - 输入文本
6. **按键(key)** - 按下单个按键（如enter, esc, tab等）
7. **快捷键(*keys)** - 按下组合键（如ctrl+c, alt+tab等）
8. **滚动(clicks)** - 滚动鼠标滚轮
9. **等待(seconds)** - 等待指定秒数
10. **打开应用(path)** - 打开指定路径的应用程序

## 输出格式要求：
直接返回JSON格式的操作指令，不要有其他文字：
{"action": "操作类型", "x": 数值, "y": 数值, "text": "文本内容", "key": "按键名", "keys": ["键1", "键2"], "clicks": 数值, "seconds": 数值, "path": "路径", "plan": "执行计划文本"}

## 分析步骤：
1. 仔细分析收到的截图内容
2. 判断当前是否在桌面、是否有所需的应用
3. 如果不在桌面，先返回桌面
4. 如果找不到目标，先返回桌面
5. 找到目标后执行相应操作

## 重要规则：
- 屏幕坐标从左上角(0,0)开始,到右下角（999,999)结束
- 点击、右键点击、双击操作需要命中在点击目标的正中心
- 如果任务完成，返回"完成: 任务已完成"
- 不要返回截屏操作，截图已经提供给你分析
- 如果不确定当前界面，先返回桌面
- 直接返回JSON，不要有任何前缀文字
"""

CLIENT = None


def get_llm_client():
    global CLIENT
    if CLIENT is None:
        CLIENT = OpenAI(
            api_key=config.OPENAI_API_KEY,
            base_url=config.OPENAI_BASE_URL
        )
    return CLIENT


def encode_image(image_path: str) -> str:
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")


def analyze_with_image(client: OpenAI, user_prompt: str, image_path: str | None = None, conversation_history: list | None = None) -> list:
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
    
    response = client.chat.completions.create(
        model=config.MODEL_NAME,
        messages=messages,
        temperature=0.7
    )
    precheck_resp=response.choices[0].message.content
    pre_actions = extract_json(precheck_resp)
    return pre_actions


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
        pre_actions = analyze_with_image(llm_client, f"任务: {task}")
        log_callback(str(pre_actions), "response")
        plan_text = None
        need_screenshot = False
        plan_emitted = False
        if pre_actions:
            log_callback(pre_actions, "response")
            if pre_actions and isinstance(pre_actions, list):
                for act in pre_actions:
                    if isinstance(act, dict):
                        if "plan" in act and isinstance(act["plan"], str):
                            plan_text = act["plan"]
                        if "need_screenshot" in act:
                            need_screenshot = bool(act["need_screenshot"])
            if plan_text and log_callback:
                log_callback(plan_text, "plan")
                plan_emitted = True
        else:
            plan_text = None

        current_screenshot = self.executor.screenshot() if need_screenshot else None
        
        while self.iteration < self.max_iterations:
            self.iteration += 1
            
            if log_callback:
                log_callback(f"第 {self.iteration} 次迭代...", "info")
            
            resp_actions = analyze_with_image(
                llm_client,
                f"任务: {task}",
                current_screenshot
            )
            log_callback(str(resp_actions),"response")
            if len(resp_actions)==1 and resp_actions[0]["action"]=="完成":
                return str(resp_actions[0])

            
            action=resp_actions
            
            if action and isinstance(action, list):
                try:
                    results = []
                    for act in action:
                        if isinstance(act, dict):
                            if "plan" in act and isinstance(act["plan"], str) and not plan_emitted:
                                plan_text = act["plan"]
                                if plan_text and log_callback:
                                    log_callback(plan_text, "plan")
                                    plan_emitted = True
                            if "action" in act:
                                result = self.executor.execute_action(act)
                                results.append(result)
                                if log_callback:
                                    log_callback(f"执行操作: {result}", "execute")
                    # Take a new screenshot after attempting actions
                    current_screenshot = self.executor.screenshot()
                except Exception as e:
                    if log_callback:
                        log_callback(f"执行错误: {e}", "error")
                    
        return "达到最大迭代次数，任务未能完成"
