import ctypes
import os
import sys
import time
from ctypes import wintypes

import pyautogui
import subprocess
from PIL import Image
from io import BytesIO
import base64



pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.5


def get_primary_monitor_info() -> dict:
    """
    兼容所有Windows版本的显示器信息获取（替换GetDpiForMonitor）
    返回：{"width": 物理宽度, "height": 物理高度, "scale_x": X轴缩放, "scale_y": Y轴缩放}
    """
    user32 = ctypes.windll.user32
    gdi32 = ctypes.windll.gdi32

    # 方案1：让进程感知DPI（基础兼容）
    try:
        # Windows 10/11 高DPI感知
        user32.SetProcessDpiAwarenessContext(2)  # DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2
    except:
        # 兼容旧系统
        user32.SetProcessDPIAware()

    # 获取主显示器物理分辨率
    screen_width = user32.GetSystemMetrics(0)  # SM_CXSCREEN
    screen_height = user32.GetSystemMetrics(1)  # SM_CYSCREEN

    # 方案2：通过GetDeviceCaps获取DPI（替代GetDpiForMonitor）
    hdc = user32.GetDC(None)  # 获取屏幕DC
    dpi_x = gdi32.GetDeviceCaps(hdc, 88)  # LOGPIXELSX = 88
    dpi_y = gdi32.GetDeviceCaps(hdc, 90)  # LOGPIXELSY = 90
    user32.ReleaseDC(None, hdc)  # 释放DC

    # 计算DPI缩放因子（96是Windows默认DPI）
    scale_x = dpi_x / 96.0
    scale_y = dpi_y / 96.0

    return {
        "width": screen_width,
        "height": screen_height,
        "scale_x": scale_x,
        "scale_y": scale_y
    }


def translate_x_y_to_screen_coord(norm_x: float, norm_y: float) -> tuple:
    """
    将归一化坐标（0.0~1.0）转换为实际屏幕的像素坐标
    :param norm_x: 归一化水平坐标（0.0 ≤ norm_x ≤ 1.0）
    :param norm_y: 归一化垂直坐标（0.0 ≤ norm_y ≤ 1.0）
    :return: 实际屏幕像素坐标 (screen_x, screen_y)
    :raises TypeError: 输入非浮点/整数类型时触发
    :raises ValueError: 输入超出0.0~1.0范围时触发
    """
    # 步骤1：输入校验（适配归一化坐标的浮点特性）
    if not isinstance(norm_x, (int, float)) or not isinstance(norm_y, (int, float)):
        raise TypeError("归一化坐标x和y必须为数字类型（整数/浮点数）")
    if not (0.0 <= norm_x <= 1.0) or not (0.0 <= norm_y <= 1.0):
        raise ValueError("归一化坐标必须在0.0~1.0范围内")

    # 步骤2：获取屏幕信息
    info = get_primary_monitor_info()
    screen_width = info["width"]
    screen_height = info["height"]

    # 步骤3：计算实际屏幕像素坐标（核心修改：基于屏幕尺寸直接缩放）
    # 归一化坐标 × 屏幕实际尺寸 = 像素坐标
    screen_x = round(norm_x * screen_width)
    screen_y = round(norm_y * screen_height)

    # 步骤4：边界保护（确保坐标在屏幕有效范围内）
    screen_x = max(0, min(screen_x, screen_width - 1))
    screen_y = max(0, min(screen_y, screen_height - 1))

    print(f"转换后的屏幕像素坐标：x={screen_x}, y={screen_y}, 原始归一化坐标：({norm_x}, {norm_y})")
    return (screen_x, screen_y)

class Executor:
    def __init__(self, work_dir: str):
        self.work_dir = work_dir
        self.screenshot_dir = os.path.join(work_dir, "screenshots")
        os.makedirs(self.screenshot_dir, exist_ok=True)
        self.screenshot_count = 0

    def screenshot(self) -> str:
        self.screenshot_count += 1
        filename = f"screenshot_{self.screenshot_count}.png"
        filepath = os.path.join(self.screenshot_dir, filename)
        
        img = pyautogui.screenshot()
        img.save(filepath)
        return filepath

    def click(self, x: int, y: int, button: str = "left") -> str:
        pyautogui.click(x, y, button=button)
        return f"Clicked at ({x}, {y}) with {button} button"

    def double_click(self, x: int, y: int, button: str = "left") -> str:
        pyautogui.doubleClick(x, y, button=button)
        return f"Double-clicked at ({x}, {y}) with {button} button"

    def right_click(self, x: int, y: int) -> str:
        return self.click(x, y, button="right")

    def move_to(self, x: int, y: int) -> str:
        pyautogui.moveTo(x, y)
        return f"Moved to ({x}, {y})"

    def type_text(self, text: str) -> str:
        pyautogui.write(text, interval=0.05)
        return f"Typed text: {text}"

    def press_key(self, key: str) -> str:
        pyautogui.press(key)
        return f"Pressed key: {key}"

    def hotkey(self, *keys) -> str:
        pyautogui.hotkey(*keys)
        return f"Pressed hotkey: {'+'.join(keys)}"

    def scroll(self, clicks: int, x: int = None, y: int = None) -> str:
        if x is not None and y is not None:
            pyautogui.scroll(clicks, x, y)
        else:
            pyautogui.scroll(clicks)
        return f"Scrolled {clicks} clicks"

    def get_screen_size(self) -> tuple:
        return pyautogui.size()

    def return_to_desktop(self) -> str:
        pyautogui.hotkey("win", "d")
        return "Returned to desktop"

    def execute_action(self, action: dict) -> str:
        action_type = action.get("action", "").lower()
        
        if action_type == "click":
            x = action.get("x")
            y = action.get("y")
            real_x,real_y=translate_x_y_to_screen_coord(x,y)
            if x is not None and y is not None:
                return self.click(real_x, real_y)
                
        elif action_type == "double_click" or action_type == "双击":
            x = action.get("x")
            y = action.get("y")
            real_x,real_y=translate_x_y_to_screen_coord(x,y)
            if x is not None and y is not None:
                return self.double_click(real_x, real_y)
                
        elif action_type == "right_click" or action_type == "右键点击":
            x = action.get("x")
            y = action.get("y")
            real_x,real_y=translate_x_y_to_screen_coord(x,y)
            if x is not None and y is not None:
                return self.right_click(real_x, real_y)
                
        elif action_type == "type" or action_type == "输入":
            text = action.get("text", "")
            return self.type_text(text)
            
        elif action_type == "press" or action_type == "按键":
            key = action.get("key", "")
            return self.press_key(key)
            
        elif action_type == "hotkey" or action_type == "快捷键":
            keys = action.get("key").split("+")
            if keys:
                return self.hotkey(*keys)
                
        elif action_type == "scroll" or action_type == "滚动":
            clicks = action.get("clicks", 0)
            x = action.get("x")
            y = action.get("y")
            real_x,real_y=translate_x_y_to_screen_coord(x,y)
            return self.scroll(clicks, real_x, real_y)
            
        elif action_type == "screenshot" or action_type == "截屏":
            filepath = self.screenshot()
            return f"Screenshot saved: {filepath}"
            
        elif action_type == "wait" or action_type == "等待":
            seconds = action.get("seconds", 1)
            time.sleep(seconds)
            return f"Waited {seconds} seconds"
            
        elif action_type == "open_app" or action_type == "打开应用":
            app_path = action.get("path", "")
            if app_path:
                try:
                    subprocess.Popen(app_path)
                    return f"Opened application: {app_path}"
                except Exception as e:
                    return f"Failed to open application: {e}"
        
        elif action_type == "return_to_desktop" or action_type == "返回桌面":
            return self.return_to_desktop()
        elif action_type == "over" or action_type == "完成":
            return "任务完成"
        
        return f"Unknown action: {action}"
