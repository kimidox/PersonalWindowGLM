from __future__ import annotations

from typing import Optional

import config

from .BaseChatModel import BaseChatModel
from .glm_chat_model import GLMChatModel
from .qwen_chat_model import QwenChatModel


def get_chat_model(model_name: Optional[str] = None) -> BaseChatModel:
    """
    根据 config.MODEL_NAME 选择具体的模型实现。
    """

    model = model_name or config.MODEL_NAME
    if model == "glm-5" or model.startswith("glm"):
        return GLMChatModel(model_name=model)
    if model.startswith("qwen3.5") or model.startswith("qwen"):
        return QwenChatModel(model_name=model)

    # 兜底：优先按 qwen 格式跑（tool schema 与解析已被统一）
    return QwenChatModel(model_name=model)


