from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass
class Message:
    """与 `database.models.Messages` 对应的领域消息（供 Memory 与业务层使用）。"""

    message_id: str
    conversation_id: str
    role: str
    content: str
    ext: dict[str, Any] | None = None
    created_at: datetime | None = None

    def to_llm_dict(self) -> dict[str, Any]:
        """拼装为 `BaseChatModel.complete_with_tools` 所需的 message 字典。"""
        d: dict[str, Any] = {"role": self.role, "content": self.content}
        if self.role == "tool" and self.ext and self.ext.get("name"):
            d["name"] = str(self.ext["name"])
        return d

    def to_record_dict(self) -> dict[str, Any]:
        """含 `metadata`（来自 ext）的记录，供 UI 恢复历史；不含 system 时可与 LLM 字典同构并附加元数据。"""
        d = dict(self.to_llm_dict())
        if self.ext:
            d["metadata"] = dict(self.ext)
        return d

    @classmethod
    def from_orm(cls, row: Any) -> Message:
        from database.models import Messages as MessagesRow

        if not isinstance(row, MessagesRow):
            raise TypeError(f"expected Messages ORM row, got {type(row)!r}")
        return cls(
            message_id=str(row.message_id),
            conversation_id=str(row.conversation_id),
            role=str(row.role),
            content=str(row.content) if row.content is not None else "",
            ext=dict(row.ext) if row.ext is not None else None,
            created_at=row.created_at,
        )
