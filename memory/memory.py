from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class Memory(ABC):
    """SkillAgent 侧记忆机制的抽象接口：会话消息与可选的会话状态（如已加载 Skill）。

    具体持久化（内存字典、SQLite 等）由子类实现；SkillAgent 可通过依赖注入使用。
    """

    @abstractmethod
    def append_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """追加一条对话消息（role 如 system / user / assistant / tool）。"""

    @abstractmethod
    def get_messages(
        self,
        conversation_id: str,
        *,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """按时间顺序返回消息列表；每条建议含 role、content、可选 metadata、created_at 等。"""

    @abstractmethod
    def clear_conversation(self, conversation_id: str) -> None:
        """清空某会话下的消息与关联状态。"""

    @abstractmethod
    def set_active_skills(self, conversation_id: str, skill_ids: list[str]) -> None:
        """记录当前会话已加载的 Skill id 列表（与 SkillAgent 中 active_skill_ids 对应）。"""

    @abstractmethod
    def get_active_skills(self, conversation_id: str) -> list[str]:
        """读取当前会话已加载的 Skill id 列表。"""
