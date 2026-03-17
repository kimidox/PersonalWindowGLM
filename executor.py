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


def translate_x_y_to_screen_coord(x: int, y: int) -> tuple:
    """
    将千分比坐标(x, y)（0-999）映射到实际屏幕像素坐标。
    基准坐标为 1920x1200 的逻辑坐标，考虑实际主显示器分辨率和 DPI 缩放。

    参数:
        x: 水平方向千分比 (0-999)
        y: 垂直方向千分比 (0-999)

    返回:
        tuple: (屏幕像素X坐标, 屏幕像素Y坐标)
    """
    # 校验输入范围
    if not (0 <= x <= 999) or not (0 <= y <= 999):
        raise ValueError(f"x和y必须是0-999之间的整数，当前输入：x={x}, y={y}")

    info = get_primary_monitor_info()
    screen_width = info["width"]
    screen_height = info["height"]
    base_w, base_h = 1920, 1200

    # 步骤1：将千分比转换为基准逻辑坐标（1920x1200）的绝对坐标
    base_x = (x / 999) * base_w
    base_y = (y / 999) * base_h

    # 步骤2：计算缩放比例（考虑DPI缩放）
    # scale_w = (screen_width / base_w) * info.get("scale_x", 1.0)
    # scale_h = (screen_height / base_h) * info.get("scale_y", 1.0)

    scale_w = (screen_width / base_w) * 1.0
    scale_h = (screen_height / base_h) * 1.0

    # 步骤3：转换为实际屏幕像素坐标
    screen_x = round(base_x * scale_w)
    screen_y = round(base_y * scale_h)

    # 边界保护（确保坐标在屏幕范围内）
    screen_x = max(0, min(screen_x, screen_width - 1))
    screen_y = max(0, min(screen_y, screen_height - 1))

    print(f"转换后的坐标：x={screen_x}, y={screen_y} (原千分比 x={x}, y={y})")
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
        
        return f"Unknown action: {action}"
