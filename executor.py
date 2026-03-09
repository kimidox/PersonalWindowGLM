import os
import time
import pyautogui
import subprocess
from PIL import Image
from io import BytesIO
import base64



pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.5
def translate_x_y_to_screen_coord(x: int, y: int) -> tuple:
    """
    将归一化坐标 (x, y)（范围 0-999）转换为当前屏幕的实际像素坐标
    使用 pyautogui 获取屏幕分辨率，兼容 Windows/macOS/Linux

    Args:
        x: 归一化x坐标，范围0-999
        y: 归一化y坐标，范围0-999

    Returns:
        tuple: (实际屏幕x像素, 实际屏幕y像素)

    Raises:
        ValueError: 当x或y超出0-999范围时抛出
    """
    # 1. 输入参数校验
    if not (0 <= x <= 999) or not (0 <= y <= 999):
        raise ValueError(f"x和y必须在0-999之间，当前输入：x={x}, y={y}")

    # 2. 获取屏幕分辨率（核心：pyautogui 原生方法）
    screen_width, screen_height = pyautogui.size()
    print(f"当前屏幕分辨率：{screen_width} × {screen_height}")  # 可选：打印分辨率

    # 3. 按比例转换坐标（四舍五入为整数像素）
    screen_x = round(x * screen_width / 999)
    screen_y = round(y * screen_height / 999)

    # 4. 边界防护：确保坐标不超出屏幕范围
    screen_x = max(0, min(screen_x, screen_width))
    screen_y = max(0, min(screen_y, screen_height))

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
            keys = action.get("keys", [])
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
