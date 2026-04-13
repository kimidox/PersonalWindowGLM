from __future__ import annotations

import json
import re
import sys
from html import escape

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QFont, QTextCursor
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

import config
from executor import Executor
from llm import get_chat_model
from memory import SqliteMemory
from skill_agent import SkillAgent
from skill_agent_preferences import load_disabled_skill_ids, save_disabled_skill_ids




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


def _llm_request_params_text() -> str:
    m = get_chat_model()
    try:
        body = m.extra_body if isinstance(m.extra_body, dict) else dict(m.extra_body or {})
    except (TypeError, ValueError):
        body = m.extra_body
    body_s = json.dumps(body, ensure_ascii=False, indent=2) if isinstance(body, dict) else repr(body)
    key = m.api_key or ""
    key_disp = "（未设置）" if not key else f"{key[:4]}…{key[-2:]}" if len(key) > 8 else "（已设置）"
    parts = [
        f"model_name: {m.model_name}",
        f"temperature: {m.temperature}",
        f"base_url: {m.base_url}",
        f"api_key: {key_disp}",
        f"extra_body:\n{body_s}",
        f"SKILL_AGENT_MAX_STEPS（Agent 循环上限）: {config.SKILL_AGENT_MAX_STEPS}",
    ]
    return "\n".join(parts)


class SkillAgentSettingsDialog(QDialog):
    """会话设置：模型信息、LLM 请求参数摘要、Skill 启用/禁用（禁用后不可加载到会话）。"""

    def __init__(self, parent: QWidget | None, skill_agent: SkillAgent) -> None:
        super().__init__(parent)
        self.setWindowTitle("会话与模型设置")
        self.setModal(True)
        self.resize(560, 520)
        self._skill_agent = skill_agent
        self._disabled: set[str] = set(load_disabled_skill_ids())
        self._skill_checks: list[tuple[str, QCheckBox]] = []

        root = QVBoxLayout(self)
        root.setSpacing(10)

        lm = QLabel("当前大模型")
        f = lm.font()
        f.setBold(True)
        lm.setFont(f)
        root.addWidget(lm)
        self._model_label = QLabel()
        self._model_label.setWordWrap(True)
        self._model_label.setTextFormat(Qt.TextFormat.RichText)
        root.addWidget(self._model_label)

        lp = QLabel("LLM 请求参数（与当前配置一致，只读）")
        fp = lp.font()
        fp.setBold(True)
        lp.setFont(fp)
        root.addWidget(lp)
        self._params_edit = QTextEdit()
        self._params_edit.setReadOnly(True)
        self._params_edit.setFont(QFont("Consolas", 9))
        self._params_edit.setMinimumHeight(140)
        self._params_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        root.addWidget(self._params_edit)

        ls = QLabel(
            "Skill 列表：勾选「启用」表示可用；取消勾选即禁用，禁用后不出现在系统列表中，且无法 select_skill 加载。"
        )
        ls.setWordWrap(True)
        fs = ls.font()
        fs.setBold(True)
        ls.setFont(fs)
        root.addWidget(ls)

        self._skills_scroll = QScrollArea()
        self._skills_scroll.setWidgetResizable(True)
        self._skills_scroll.setMinimumHeight(200)
        self._skills_inner = QWidget()
        self._skills_layout = QVBoxLayout(self._skills_inner)
        self._skills_layout.setContentsMargins(4, 4, 4, 4)
        self._skills_layout.setSpacing(6)
        self._skills_scroll.setWidget(self._skills_inner)
        root.addWidget(self._skills_scroll, stretch=1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

        self._repopulate_skill_rows()
        self._refresh_llm_block()

    def _refresh_llm_block(self) -> None:
        m = get_chat_model()
        self._model_label.setText(f"<span style='font-family:Consolas,monospace'>{escape(m.model_name or '')}</span>")
        self._params_edit.setPlainText(_llm_request_params_text())

    def _repopulate_skill_rows(self) -> None:
        self._skill_checks.clear()
        self._skills_inner = QWidget()
        self._skills_layout = QVBoxLayout(self._skills_inner)
        self._skills_layout.setContentsMargins(4, 4, 4, 4)
        self._skills_layout.setSpacing(6)
        # setWidget 会接管并销毁滚动区里原来的 widget，不可再对旧指针 deleteLater
        self._skills_scroll.setWidget(self._skills_inner)

        skills = sorted(
            self._skill_agent.registry.list_skills(),
            key=lambda s: (s.skill_id or "").lower(),
        )
        for s in skills:
            sid = (s.skill_id or "").strip()
            if not sid:
                continue
            cb = QCheckBox("启用")
            cb.setChecked(sid not in self._disabled)
            cb.stateChanged.connect(lambda _st, _sid=sid, _cb=cb: self._on_skill_toggled(_sid, _cb))
            row = QHBoxLayout()
            row.addWidget(cb)
            name_lab = QLabel(f"{sid} · {s.name or ''}")
            name_lab.setWordWrap(True)
            row.addWidget(name_lab, stretch=1)
            self._skills_layout.addLayout(row)
            self._skill_checks.append((sid, cb))
        self._skills_layout.addStretch(1)

    def _on_skill_toggled(self, skill_id: str, cb: QCheckBox) -> None:
        if cb.isChecked():
            self._disabled.discard(skill_id)
        else:
            self._disabled.add(skill_id)
        save_disabled_skill_ids(self._disabled)

    def showEvent(self, event) -> None:  # type: ignore[override]
        super().showEvent(event)
        self._skill_agent.reload_skills()
        self._disabled = set(load_disabled_skill_ids())
        self._repopulate_skill_rows()
        self._refresh_llm_block()


class SkillAgentMainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.work_dir = config.WORKER_DIR
        self.executor = Executor(self.work_dir)
        self._memory = SqliteMemory(username=config.DEFAULT_SKILL_AGENT_USER)
        self.skill_agent = SkillAgent(
            self.work_dir,
            executor=self.executor,
            memory=self._memory,
            username=config.DEFAULT_SKILL_AGENT_USER,
        )
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

        chat_header = QHBoxLayout()
        chat_header.addStretch(1)
        self.settings_btn = QPushButton("设置")
        self.settings_btn.setFont(QFont("Microsoft YaHei", 9))
        self.settings_btn.setFixedHeight(28)
        self.settings_btn.setToolTip("模型、LLM 参数与 Skill 启用状态")
        self.settings_btn.clicked.connect(self._open_settings)
        chat_header.addWidget(self.settings_btn, alignment=Qt.AlignmentFlag.AlignRight)

        chat_wrap = QVBoxLayout()
        chat_wrap.setSpacing(4)
        chat_wrap.addLayout(chat_header)
        chat_wrap.addWidget(self.chat_view, stretch=1)
        chat_container = QWidget()
        chat_container.setLayout(chat_wrap)
        layout.addWidget(chat_container, stretch=1)

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

    def _open_settings(self) -> None:
        SkillAgentSettingsDialog(self, self.skill_agent).exec()

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
