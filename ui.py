import sys
import os
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                               QHBoxLayout, QLineEdit, QPushButton, QTextEdit,
                               QLabel, QMessageBox, QScrollArea)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QFont, QTextCursor
from agent import Agent


class WorkerThread(QThread):
    log_signal = Signal(str, str)
    finished_signal = Signal(str)
    
    def __init__(self, agent: Agent, task: str):
        super().__init__()
        self.agent = agent
        self.task = task
        
    def run(self):
        result = self.agent.run(self.task, self.log_callback)
        self.finished_signal.emit(result)
    
    def log_callback(self, message: str, msg_type: str = "info"):
        self.log_signal.emit(message, msg_type)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.work_dir = os.path.dirname(os.path.abspath(__file__))
        self.agent = Agent(self.work_dir)
        self.worker_thread = None
        self.init_ui()
        
    def init_ui(self):
        self.setWindowTitle("Window GLM - 智能自动化助手")
        self.setGeometry(100, 100, 800, 600)
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QVBoxLayout(central_widget)
        
        title_label = QLabel("Window GLM - 智能自动化助手")
        title_label.setFont(QFont("Microsoft YaHei", 14, QFont.Bold))
        title_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(title_label)
        
        input_layout = QHBoxLayout()
        self.input_edit = QLineEdit()
        self.input_edit.setPlaceholderText("请输入任务描述，例如：帮我打开桌面上的QQ...")
        self.input_edit.setFont(QFont("Microsoft YaHei", 10))
        self.input_edit.returnPressed.connect(self.on_send_clicked)
        
        self.send_btn = QPushButton("发送")
        self.send_btn.setFont(QFont("Microsoft YaHei", 10))
        self.send_btn.clicked.connect(self.on_send_clicked)
        
        input_layout.addWidget(self.input_edit, 4)
        input_layout.addWidget(self.send_btn, 1)
        main_layout.addLayout(input_layout)
        
        self.log_display = QTextEdit()
        self.log_display.setFont(QFont("Consolas", 9))
        self.log_display.setReadOnly(True)
        main_layout.addWidget(self.log_display)
        
        control_layout = QHBoxLayout()
        self.clear_btn = QPushButton("清空日志")
        self.clear_btn.setFont(QFont("Microsoft YaHei", 9))
        self.clear_btn.clicked.connect(self.clear_log)
        
        self.stop_btn = QPushButton("停止")
        self.stop_btn.setFont(QFont("Microsoft YaHei", 9))
        self.stop_btn.clicked.connect(self.stop_task)
        self.stop_btn.setEnabled(False)
        
        control_layout.addWidget(self.clear_btn)
        control_layout.addStretch()
        control_layout.addWidget(self.stop_btn)
        main_layout.addLayout(control_layout)
        
    def on_send_clicked(self):
        task = self.input_edit.text().strip()
        if not task:
            QMessageBox.warning(self, "警告", "请输入任务描述")
            return
            
        if self.worker_thread and self.worker_thread.isRunning():
            QMessageBox.warning(self, "警告", "任务正在执行中")
            return
            
        self.log_display.clear()
        self.log(f"开始执行任务: {task}\n", "info")
        
        self.send_btn.setEnabled(False)
        self.input_edit.setEnabled(False)
        self.stop_btn.setEnabled(True)
        
        self.worker_thread = WorkerThread(self.agent, task)
        self.worker_thread.log_signal.connect(self.on_log_received)
        self.worker_thread.finished_signal.connect(self.on_task_finished)
        self.worker_thread.start()
        
    def on_log_received(self, message: str, msg_type: str):
        self.log(message, msg_type)
        
    def on_task_finished(self, result: str):
        self.log(f"\n任务完成: {result}\n", "info")
        
        self.send_btn.setEnabled(True)
        self.input_edit.setEnabled(True)
        self.stop_btn.setEnabled(False)
        
    def log(self, message: str, msg_type: str = "info"):
        color = "black"
        if msg_type == "error":
            color = "red"
        elif msg_type == "response":
            color = "blue"
        elif msg_type == "plan":
            color = "green"
        elif msg_type == "execute":
            color = "purple"
        
        self.log_display.moveCursor(QTextCursor.End)
        self.log_display.insertHtml(f'<span style="color: {color};">{message}</span><br>')
        self.log_display.moveCursor(QTextCursor.End)
        
    def clear_log(self):
        self.log_display.clear()
        
    def stop_task(self):
        if self.worker_thread and self.worker_thread.isRunning():
            self.worker_thread.terminate()
            self.log("\n任务已停止\n", "error")
            self.send_btn.setEnabled(True)
            self.input_edit.setEnabled(True)
            self.stop_btn.setEnabled(False)


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
