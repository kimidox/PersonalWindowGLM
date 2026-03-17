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





SYSTEM_PROMPT = SYSTEM_PROMPT = """你是一个Windows桌面自动化助手。你已经收到屏幕截图，请直接分析内容并返回操作指令。

## 可用操作命令：
1. 返回桌面 - 按Win+D返回Windows桌面,输出示例:''
2. 点击(x, y) - 在指定坐标点击左键,输出示例:'{"action": "点击", "x": 18, "y":967, "plan": "找到图标并点击。", "need_screenshot": true}'
3. 双击(x, y) - 在指定坐标双击左键,输出示例:'{"action": "双击", "x": 18, "y":967, "plan": "找到图标并双击。", "need_screenshot": true}'
4. 右键点击(x, y) - 在指定坐标点击右键,输出示例:'{"action": "右击", "x": 18, "y":967, "plan": "找到图标并右击。", "need_screenshot": true}'
5. 输入(text) - 输入文本,输出示例:'{"action": "输入", "text": "Hello World", "plan": "输入文本。", "need_screenshot": true}'
6. 按键(key) - 按下单个按键（enter, esc, tab等）,输出示例:'{"action": "按键", "key": "enter", "plan": "按下单个按键", "need_screenshot": true}'
7. 快捷键(*keys) - 按下组合键（ctrl+c, alt+tab等）,输出示例:'{"action": "快捷键", "key": "wind+d", "plan": "按下组合件", "need_screenshot": true}'
8. 滚动(clicks) - 滚动鼠标滚轮,输出示例:'{"action": "滚动", "x": 18, "y":967, "clicks":"0","plan": "按下组合件", "need_screenshot": true}'
9. 等待(seconds) - 等待指定秒数
10. 打开应用(path) - 打开指定路径的应用程序
11 .完成(mission_success) - 任务完成
## 核心坐标规则（必须严格执行，优先级最高）：
1. 屏幕坐标系：左上角(0,0),右下角坐标(999,999)，右下角为当前屏幕分辨率的像素坐标
2. 坐标计算逻辑：
   - 第一步：识别目标图标/按钮的**完整像素区域**（如左上角x1,y1，右下角x2,y2）
   - 第二步：计算正中心坐标：x = (x1 + x2) / 2，y = (y1 + y2) / 2
   - 第三步：将x、y取整数（四舍五入）作为最终点击坐标
3. 禁止行为：
   - 禁止返回目标的左上角、右上角、左下角、右下角坐标
   - 禁止返回边缘、角落坐标
   - 禁止直接使用识别到的初始坐标（必须经过中心计算）
4. 验证要求：返回坐标前，必须确认该坐标位于目标图标/按钮的几何正中心，无任何偏移

## 输出格式（必须严格遵守）：
直接返回JSON，无任何额外文字、注释、前缀：
{"action": "操作类型", "x": 数值, "y": 数值, "text": "文本内容", "key": "按键名", "keys": ["键1", "键2"], "clicks": 数值, "seconds": 数值, "path": "路径", "plan": "执行计划文本","need_screenshot":true}


## 输出校验
1. 必须返回JSON格式
2. 必须包含action键
3. 点击、双击、右键点击操作必须包含x、y键
4. 必须包含plan键（除非action为等待或打开应用）
5. 必须包含need_screenshot键（除非action为等待或打开应用）
6. 必须包含text键（除非action为点击、双击、右键点击、输入、按键、快捷键、滚动、等待、打开应用）
7. 必须包含key键（除非action为点击、双击、右键点击、按键、快捷键、滚动、等待、打开应用）

## 执行逻辑：
1. 先执行目标任务是否需要在桌面
   如果需要->先执行返回桌面
        当前页面不是桌面 → 先执行返回桌面
        当前页面是桌面 → 找到目标图标，执行任务
   如果不需要->开始执行任务
2. 执行完操作后，判断当前操作是否已完成
   当前操作完成→ 截屏，分析图片，继续下一步
   当前操作未完成 → 截屏，分析图片，继续尝试执行操作
3. 所以操作执行完成后，根据最后一步截屏判断任务是否完成
   任务完成-> 返回完成
   任务未完成-> 截屏，分析图片，继续尝试执行操作
4. 界面不确定 → 先返回桌面,重新进行思考计划

## 强制约束：
- 只输出标准JSON，无多余内容
- 坐标必须为目标图标正中心（必须经过x=(x1+x2)/2、y=(y1+y2)/2计算）
- 错误示例（禁止返回）：目标图标区域(100,200)-(200,300)，返回(100,200)（左上角）
- 正确示例（必须返回）：目标图标区域(100,200)-(200,300)，返回(150,250)（正中心）
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
        temperature=0,
        extra_body={"enable_thinking": False}

    )
    precheck_resp=response.choices[0].message.content
    actions = extract_json(precheck_resp)
    return actions


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
        pre_actions = analyze_with_image(llm_client, f"任务: {task}",image_path=current_screenshot)
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
