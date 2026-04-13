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
    QTabWidget,
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
    """绑定发起请求时的 conversation 与聊天控件，避免切换标签后日志串页。"""

    log_signal = Signal(str, str, QTextEdit)
    finished_signal = Signal(str)

    def __init__(
        self,
        agent: SkillAgent,
        query: str,
        *,
        conversation_id: str,
        target_chat: QTextEdit,
    ) -> None:
        super().__init__()
        self.agent = agent
        self.query = query
        self.conversation_id = conversation_id
        self.target_chat = target_chat

    def run(self) -> None:
        self.agent.set_conversation_id(self.conversation_id)
        result = self.agent.run(self.query, self._log_callback)
        self.finished_signal.emit(result)

    def _log_callback(self, message: str, msg_type: str = "info") -> None:
        self.log_signal.emit(message, msg_type, self.target_chat)


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


CHAT_DOCUMENT_STYLESHEET = (
    "body { margin: 0; } p { margin-top: 4px; margin-bottom: 4px; } "
    "ul { margin: 4px 0; padding-left: 22px; } h1,h2,h3 { margin: 8px 0 4px; }"
)


def _tab_title_for_conversation(conversation_id: str) -> str:
    c = (conversation_id or "").strip()
    if len(c) >= 10:
        return f"会话 · {c[:8]}"
    return f"会话 · {c or '?'}"


def _apply_chat_view_style(chat: QTextEdit) -> None:
    chat.setReadOnly(True)
    chat.setFont(QFont("Microsoft YaHei", 10))
    chat.setAcceptRichText(True)
    chat.setPlaceholderText("对话记录将显示在这里…")
    chat.setStyleSheet(
        "QTextEdit { background-color: #fafafa; border: 1px solid #e0e0e0; border-radius: 8px; }"
    )
    chat.setMinimumHeight(200)
    chat.document().setDefaultStyleSheet(CHAT_DOCUMENT_STYLESHEET)


class ChatSessionTab(QWidget):
    """单个会话标签页：绑定 conversation_id 与聊天记录控件。"""

    def __init__(self, conversation_id: str) -> None:
        super().__init__()
        self.conversation_id = (conversation_id or "").strip()
        self.chat_view = QTextEdit()
        _apply_chat_view_style(self.chat_view)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addWidget(self.chat_view)


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

        chat_header = QHBoxLayout()
        chat_header.addStretch(1)
        self.new_conversation_btn = QPushButton("新增会话")
        self.new_conversation_btn.setFont(QFont("Microsoft YaHei", 9))
        self.new_conversation_btn.setFixedHeight(28)
        self.new_conversation_btn.setToolTip("新建一个会话标签页（新的 conversation_id）")
        self.new_conversation_btn.clicked.connect(self._on_new_conversation)
        chat_header.addWidget(self.new_conversation_btn, alignment=Qt.AlignmentFlag.AlignRight)
        self.settings_btn = QPushButton("设置")
        self.settings_btn.setFont(QFont("Microsoft YaHei", 9))
        self.settings_btn.setFixedHeight(28)
        self.settings_btn.setToolTip("模型、LLM 参数与 Skill 启用状态")
        self.settings_btn.clicked.connect(self._open_settings)
        chat_header.addWidget(self.settings_btn, alignment=Qt.AlignmentFlag.AlignRight)

        self.chat_tabs = QTabWidget()
        self.chat_tabs.setDocumentMode(True)
        self.chat_tabs.setTabsClosable(True)
        self.chat_tabs.setMovable(True)
        self.chat_tabs.tabCloseRequested.connect(self._on_tab_close_requested)
        self.chat_tabs.currentChanged.connect(self._on_current_tab_changed)
        self.chat_tabs.setMinimumHeight(280)

        first = ChatSessionTab(self.skill_agent.conversation_id)
        self.chat_tabs.addTab(first, _tab_title_for_conversation(first.conversation_id))
        self.chat_tabs.setTabToolTip(0, first.conversation_id)

        chat_wrap = QVBoxLayout()
        chat_wrap.setSpacing(4)
        chat_wrap.addLayout(chat_header)
        chat_wrap.addWidget(self.chat_tabs, stretch=1)
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

    def _active_session_tab(self) -> ChatSessionTab | None:
        w = self.chat_tabs.currentWidget()
        return w if isinstance(w, ChatSessionTab) else None

    def _active_chat_view(self) -> QTextEdit | None:
        t = self._active_session_tab()
        return t.chat_view if t else None

    def _on_current_tab_changed(self, _index: int) -> None:
        tab = self._active_session_tab()
        if tab is not None:
            self.skill_agent.set_conversation_id(tab.conversation_id)

    def _on_tab_close_requested(self, index: int) -> None:
        if self.chat_tabs.count() <= 1:
            QMessageBox.information(self, "提示", "至少保留一个会话标签页。")
            return
        page = self.chat_tabs.widget(index)
        if not isinstance(page, ChatSessionTab):
            return
        if self.worker_thread and self.worker_thread.isRunning():
            if page.conversation_id == self.worker_thread.conversation_id:
                QMessageBox.warning(self, "提示", "该会话正在执行中，请结束后再关闭标签。")
                return
        self._memory.clear_conversation(page.conversation_id)
        self.chat_tabs.removeTab(index)
        page.deleteLater()

    def _scroll_to_end(self, chat_view: QTextEdit) -> None:
        bar = chat_view.verticalScrollBar()
        bar.setValue(bar.maximum())
        chat_view.moveCursor(QTextCursor.End)

    def _insert_row(self, chat_view: QTextEdit, inner_html: str, *, align: str) -> None:
        al = "right" if align == "right" else "left"
        chat_view.moveCursor(QTextCursor.End)
        chat_view.insertHtml(
            f'<table width="100%" cellspacing="0" cellpadding="0" style="margin:0 0 14px 0;">'
            f'<tr><td align="{al}">{inner_html}</td></tr></table>'
        )
        self._scroll_to_end(chat_view)

    def _open_settings(self) -> None:
        SkillAgentSettingsDialog(self, self.skill_agent).exec()

    def _on_new_conversation(self) -> None:
        if self.worker_thread and self.worker_thread.isRunning():
            QMessageBox.warning(self, "提示", "当前仍有对话在执行，请结束后再新建会话。")
            return
        self.skill_agent.start_new_conversation()
        cid = self.skill_agent.conversation_id
        tab = ChatSessionTab(cid)
        idx = self.chat_tabs.addTab(tab, _tab_title_for_conversation(cid))
        self.chat_tabs.setTabToolTip(idx, cid)
        self.chat_tabs.setCurrentIndex(idx)
        hint = _plain_block_html(
            f"已新建会话标签页，后续消息将写入本页对应的 conversation。\nconversation_id：{cid}"
        )
        self._append_assistant_card(tab.chat_view, hint, subtitle="系统")

    def _append_user(self, chat_view: QTextEdit, text: str) -> None:
        body = _plain_block_html(text)
        bubble = (
            f'<div style="display:inline-block;max-width:88%;text-align:left;'
            f"background-color:#e3f2fd;border-radius:12px;padding:10px 14px;"
            f'border:1px solid #bbdefb;">'
            f'<div style="font-size:11px;color:#0d47a1;font-weight:600;margin-bottom:6px;">用户</div>'
            f'<div style="color:#263238;">{body}</div></div>'
        )
        self._insert_row(chat_view, bubble, align="right")

    def _append_assistant_card(
        self, chat_view: QTextEdit, body_html: str, *, subtitle: str = "助手"
    ) -> None:
        bubble = (
            f'<div style="display:inline-block;max-width:92%;text-align:left;'
            f"background-color:#f1f8e9;border-radius:12px;padding:10px 14px;"
            f'border:1px solid #c5e1a5;">'
            f'<div style="font-size:11px;color:#1b5e20;font-weight:600;margin-bottom:6px;">'
            f"{escape(subtitle)}</div>"
            f'<div style="color:#263238;">{body_html}</div></div>'
        )
        self._insert_row(chat_view, bubble, align="left")

    def _append_tool_line(self, chat_view: QTextEdit, text: str) -> None:
        safe = escape(_normalize_newlines(text))
        inner = (
            f'<div style="display:inline-block;max-width:92%;text-align:left;'
            f"background-color:#eceff1;border-radius:8px;padding:8px 12px;"
            f'border:1px solid #cfd8dc;">'
            f'<span style="font-size:11px;font-weight:600;color:#37474f;">工具</span>'
            f'<span style="font-size:11px;color:#546e7a;"> · {safe}</span></div>'
        )
        self._insert_row(chat_view, inner, align="left")

    def _append_assistant_markdown(self, chat_view: QTextEdit, markdown: str) -> None:
        frag = _markdown_fragment_html(markdown)
        self._append_assistant_card(chat_view, frag, subtitle="助手")

    def _append_doc_markdown(self, chat_view: QTextEdit, markdown: str) -> None:
        frag = _markdown_fragment_html(markdown)
        self._append_assistant_card(chat_view, frag, subtitle="Skill 文档")

    def _on_send(self) -> None:
        text = self.input_edit.text().strip()
        if not text:
            QMessageBox.warning(self, "提示", "请输入内容")
            return
        if self.worker_thread and self.worker_thread.isRunning():
            QMessageBox.warning(self, "提示", "上一轮流式仍在执行，请稍候")
            return
        tab = self._active_session_tab()
        chat = self._active_chat_view()
        if tab is None or chat is None:
            QMessageBox.warning(self, "提示", "没有可用的会话标签页")
            return

        self.skill_agent.set_conversation_id(tab.conversation_id)
        self._append_user(chat, text)
        self.input_edit.clear()

        self.send_btn.setEnabled(False)
        self.input_edit.setEnabled(False)

        self.worker_thread = SkillAgentWorkerThread(
            self.skill_agent,
            text,
            conversation_id=tab.conversation_id,
            target_chat=chat,
        )
        self.worker_thread.log_signal.connect(self._on_log)
        self.worker_thread.finished_signal.connect(self._on_finished)
        self.worker_thread.start()

    def _on_log(self, message: str, msg_type: str, target_chat: QTextEdit) -> None:
        show_tool_ui = config.SKILL_AGENT_UI_SHOW_TOOL_CALLS
        if msg_type == "tool":
            if show_tool_ui:
                self._append_tool_line(target_chat, message)
        elif msg_type == "doc":
            if show_tool_ui:
                self._append_doc_markdown(target_chat, message)
        elif msg_type in ("assistant", "response"):
            self._append_assistant_markdown(target_chat, message)

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
