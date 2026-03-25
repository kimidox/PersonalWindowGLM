import json
import re
import base64
from pathlib import Path

import pyautogui
from openai import OpenAI
from openai.types.chat import ChatCompletionMessage

from executor import Executor
import config
from llm import get_chat_model






SYSTEM_PROMPT = """你是一个Windows桌面自动化助手。你已经收到屏幕截图，请直接分析内容并调用指定的函数完成操作。必须使用提供的functions列表中的函数
# 行为逻辑链路
1.如果是刚收到任务内容和截屏，请先分析图片和任务内容，计划下一步指令来完成任务。
2.如果是收到上一步指令执行结果和新的截屏，请思考思考任务是否完成，如果没有完成请继续思考下一步指令来完成任务。
3.如果你执行完指令，且任务任务已经完成，请发送获取最新截屏的指令，得到最新的截屏后再次思考是否符合最初的任务要求，如果确认已经完成，就发送任务完成指令；如果你认为任务没有完成，请执行2-3步。
"""

class Agent:
    def __init__(self, work_dir: str):
        self.work_dir = work_dir
        self.executor = Executor(work_dir)
        self.conversation_history = []
        self.iteration = 0
        self.max_iterations = config.MAX_ITERATIONS

    
    def run(self, task: str, log_callback=None) -> str:
        model = get_chat_model()

        # Step 1: Preliminary model pass to decide if a screenshot is needed
        current_screenshot = self.executor.screenshot()
        pre_actions = model.analyze_with_image(
            system_prompt=SYSTEM_PROMPT,
            user_prompt=f"任务: {task}",
            image_path=current_screenshot,
            executor=self.executor,
            log_callback=log_callback,
        )
        log_callback(str(pre_actions), "response")
        return "完成"
