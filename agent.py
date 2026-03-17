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





SYSTEM_PROMPT = SYSTEM_PROMPT = """你是一个Windows桌面自动化助手。你已经收到屏幕截图，请直接分析内容并返回操作指令。

## 可用操作命令：
1.  返回桌面     → {"action":"快捷键","key":"win+d","plan":"返回桌面","need_screenshot":true}
2.  点击(x,y)    → {"action":"点击","x":整数,"y":整数,"plan":"...","need_screenshot":true}
3.  双击(x,y)    → {"action":"双击","x":整数,"y":整数,"plan":"...","need_screenshot":true}
4.  右击(x,y)    → {"action":"右击","x":整数,"y":整数,"plan":"...","need_screenshot":true}
5.  输入(text)   → {"action":"输入","text":"...","plan":"...","need_screenshot":true}
6.  按键(key)    → {"action":"按键","key":"enter/esc/tab",...,"plan":"...","need_screenshot":true}
7.  快捷键(key)  → {"action":"快捷键","key":"ctrl+c","plan":"...","need_screenshot":true}
8.  滚动         → {"action":"滚动","x":整数,"y":整数,"clicks":整数,"plan":"...","need_screenshot":true}
9.  等待(s)      → {"action":"等待","seconds":整数}
10. 打开应用(path)→ {"action":"打开应用","path":"路径字符串"}
11. 完成         → {"action":"完成","mission_success":true,"plan":"任务完成","need_screenshot":true}

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
4. 验证要求：返回坐标前，必须确认该坐标位于目标图标/按钮的几何正中心，无任何偏移，返回坐标是否包含x和y

## 输出格式（必须严格遵守）：
只输出JSON，无任何其他内容。
必须包含：
- action
- 点击/双击/右击必须有 x、y（整数）
- plan（除等待、打开应用外）
- need_screenshot（除等待、打开应用外）

## 最终强制校验（输出前必须过一遍）
1. 是合法JSON
2. 点击/双击/右击必须有 x 和 y
3. x、y 都是整数，无逗号嵌套
4. 坐标是图标中心
5. 无多余内容

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
- 最终输出之前一定要校验输出格式是否符合要求
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
    precheck_resp=request_llm(client=client,messages=messages)

    actions = get_actions(client, messages, precheck_resp)

    return actions


def get_actions(client, messages, precheck_resp):
    max_retries = 5  # 最大重试次数
    retry_count = 0  # 已重试次数
    actions = None  # 初始化返回结果

    while retry_count < max_retries:
        try:
            # 第一次使用precheck_resp，后续重试使用retry_resp
            if retry_count == 0:
                current_resp = precheck_resp
            else:
                current_resp = request_llm(client=client, messages=messages)

            # 尝试解析JSON，无异常则跳出循环
            actions = extract_json(current_resp)
            break  # 解析成功，终止重试

        except Exception as e:
            retry_count += 1
            # 打印异常信息（可选，便于调试）
            print(f"第 {retry_count} 次解析JSON失败，异常：{e}")
            # 如果已达到最大重试次数，抛出最终异常或返回默认值
            if retry_count >= max_retries:
                raise Exception(f"重试{max_retries}次后仍解析失败，最终异常：{e}")

    return actions

def request_llm(client,messages):
    response = client.chat.completions.create(
        model=config.MODEL_NAME,
        messages=messages,
        temperature=0,
        extra_body={"enable_thinking": False}

    )
    resp = response.choices[0].message.content
    return resp

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
