from __future__ import annotations

import os
import re
import sys
from html import escape

from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QFont, QTextCursor
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

import config
from executor import Executor
from skill_agent import SkillAgent


class SkillAgentWorkerThread(QThread):
    log_signal = Signal(str, str)
    finished_signal = Signal(str)

    def __init__(self, agent: SkillAgent, query: str) -> None:
        super().__init__()
        self.agent = agent
        self.query = query

    def run(self) -> None:
        result = self.agent.run(self.query, self._log_callback)
        self.finished_signal.emit(result)

    def _log_callback(self, message: str, msg_type: str = "info") -> None:
        self.log_signal.emit(message, msg_type)


def _normalize_newlines(text: str) -> str:
    if not text:
        return text
    t = text.replace("\r\n", "\n")
    t = t.replace("\\r\\n", "\n").replace("\\n", "\n")
    return t


def _markdown_fragment_html(markdown: str) -> str:
    """将 Markdown 转为可嵌入 QTextEdit 的 HTML 片段（避免整页 <!DOCTYPE> 结构）。"""
    md = _normalize_newlines(markdown)
    tmp = QTextEdit()
    tmp.setMarkdown(md)
    raw = tmp.toHtml()
    m = re.search(r"<body[^>]*>(.*)</body>", raw, re.DOTALL | re.IGNORECASE)
    inner = m.group(1).strip() if m else ""
    if not inner:
        return f"<p>{escape(md).replace(chr(10), '<br/>')}</p>"
    return (
        f'<div style="font-size:10pt;font-family:\'Microsoft YaHei\',\'Segoe UI\',sans-serif;'
        f'color:#263238;">{inner}</div>'
    )


def _plain_block_html(text: str) -> str:
    t = _normalize_newlines(text)
    return f"<p>{escape(t).replace(chr(10), '<br/>')}</p>"


class SkillAgentMainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.work_dir = config.WORKER_DIR
        self.executor = Executor(self.work_dir)
        self.skill_agent = SkillAgent(self.work_dir, executor=self.executor)
        self.worker_thread: SkillAgentWorkerThread | None = None
        self._init_ui()

    def _init_ui(self) -> None:
        self.setWindowTitle("SkillAgent")
        self.setGeometry(120, 120, 780, 620)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        self.chat_view = QTextEdit()
        self.chat_view.setReadOnly(True)
        self.chat_view.setFont(QFont("Microsoft YaHei", 10))
        self.chat_view.setAcceptRichText(True)
        self.chat_view.setPlaceholderText("对话记录将显示在这里…")
        self.chat_view.setStyleSheet(
            "QTextEdit { background-color: #fafafa; border: 1px solid #e0e0e0; border-radius: 8px; }"
        )
        self.chat_view.setMinimumHeight(280)
        layout.addWidget(self.chat_view, stretch=1)

        row = QHBoxLayout()
        self.input_edit = QLineEdit()
        self.input_edit.setPlaceholderText("输入业务问题后发送…")
        self.input_edit.setFont(QFont("Microsoft YaHei", 10))
        self.input_edit.setMinimumHeight(36)
        self.input_edit.returnPressed.connect(self._on_send)
        self.send_btn = QPushButton("发送")
        self.send_btn.setFont(QFont("Microsoft YaHei", 10))
        self.send_btn.setMinimumHeight(36)
        self.send_btn.setMinimumWidth(88)
        self.send_btn.clicked.connect(self._on_send)
        row.addWidget(self.input_edit, stretch=1)
        row.addWidget(self.send_btn)
        layout.addLayout(row)

        doc = self.chat_view.document()
        doc.setDefaultStyleSheet(
            "body { margin: 0; } p { margin-top: 4px; margin-bottom: 4px; } "
            "ul { margin: 4px 0; padding-left: 22px; } h1,h2,h3 { margin: 8px 0 4px; }"
        )

    def _scroll_to_end(self) -> None:
        bar = self.chat_view.verticalScrollBar()
        bar.setValue(bar.maximum())
        self.chat_view.moveCursor(QTextCursor.End)

    def _insert_row(self, inner_html: str, *, align: str) -> None:
        al = "right" if align == "right" else "left"
        self.chat_view.moveCursor(QTextCursor.End)
        self.chat_view.insertHtml(
            f'<table width="100%" cellspacing="0" cellpadding="0" style="margin:0 0 14px 0;">'
            f'<tr><td align="{al}">{inner_html}</td></tr></table>'
        )
        self._scroll_to_end()

    def _append_user(self, text: str) -> None:
        body = _plain_block_html(text)
        bubble = (
            f'<div style="display:inline-block;max-width:88%;text-align:left;'
            f"background-color:#e3f2fd;border-radius:12px;padding:10px 14px;"
            f'border:1px solid #bbdefb;">'
            f'<div style="font-size:11px;color:#0d47a1;font-weight:600;margin-bottom:6px;">用户</div>'
            f'<div style="color:#263238;">{body}</div></div>'
        )
        self._insert_row(bubble, align="right")

    def _append_assistant_card(self, body_html: str, *, subtitle: str = "助手") -> None:
        bubble = (
            f'<div style="display:inline-block;max-width:92%;text-align:left;'
            f"background-color:#f1f8e9;border-radius:12px;padding:10px 14px;"
            f'border:1px solid #c5e1a5;">'
            f'<div style="font-size:11px;color:#1b5e20;font-weight:600;margin-bottom:6px;">'
            f"{escape(subtitle)}</div>"
            f'<div style="color:#263238;">{body_html}</div></div>'
        )
        self._insert_row(bubble, align="left")

    def _append_tool_line(self, text: str) -> None:
        safe = escape(_normalize_newlines(text))
        inner = (
            f'<div style="display:inline-block;max-width:92%;text-align:left;'
            f"background-color:#eceff1;border-radius:8px;padding:8px 12px;"
            f'border:1px solid #cfd8dc;">'
            f'<span style="font-size:11px;font-weight:600;color:#37474f;">工具</span>'
            f'<span style="font-size:11px;color:#546e7a;"> · {safe}</span></div>'
        )
        self._insert_row(inner, align="left")

    def _append_assistant_markdown(self, markdown: str) -> None:
        frag = _markdown_fragment_html(markdown)
        self._append_assistant_card(frag, subtitle="助手")

    def _append_doc_markdown(self, markdown: str) -> None:
        frag = _markdown_fragment_html(markdown)
        self._append_assistant_card(frag, subtitle="Skill 文档")

    def _on_send(self) -> None:
        text = self.input_edit.text().strip()
        if not text:
            QMessageBox.warning(self, "提示", "请输入内容")
            return
        if self.worker_thread and self.worker_thread.isRunning():
            QMessageBox.warning(self, "提示", "上一轮流式仍在执行，请稍候")
            return

        self._append_user(text)
        self.input_edit.clear()

        self.send_btn.setEnabled(False)
        self.input_edit.setEnabled(False)

        self.worker_thread = SkillAgentWorkerThread(self.skill_agent, text)
        self.worker_thread.log_signal.connect(self._on_log)
        self.worker_thread.finished_signal.connect(self._on_finished)
        self.worker_thread.start()

    def _on_log(self, message: str, msg_type: str) -> None:
        show_tool_ui = config.SKILL_AGENT_UI_SHOW_TOOL_CALLS
        if msg_type == "tool":
            if show_tool_ui:
                self._append_tool_line(message)
        elif msg_type == "doc":
            if show_tool_ui:
                self._append_doc_markdown(message)
        elif msg_type in ("assistant", "response"):
            self._append_assistant_markdown(message)

    def _on_finished(self, _result: str) -> None:
        self.send_btn.setEnabled(True)
        self.input_edit.setEnabled(True)

    def closeEvent(self, event) -> None:  # type: ignore[override]
        if self.worker_thread and self.worker_thread.isRunning():
            self.worker_thread.terminate()
            self.worker_thread.wait(2000)
        super().closeEvent(event)


def main() -> None:
    app = QApplication(sys.argv)
    w = SkillAgentMainWindow()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
