from __future__ import annotations

import json
import os
from pathlib import Path

from .context import ToolContext


def _resolve_safe(ctx: ToolContext, rel: str) -> Path:
    root = Path(ctx.work_dir).resolve()
    rel = (rel or ".").strip().replace("\\", "/")
    if rel in ("", "."):
        return root
    candidate = (root / rel).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as e:
        raise ValueError("路径必须位于工作目录内") from e
    return candidate


def execute_atomic_tool(name: str, args: dict, ctx: ToolContext) -> str:
    if name == "read_text_file":
        p = _resolve_safe(ctx, str(args.get("path", "")))
        if not p.is_file():
            return f"错误: 不是文件或不存在: {p}"
        return p.read_text(encoding="utf-8", errors="replace")

    if name == "write_text_file":
        p = _resolve_safe(ctx, str(args.get("path", "")))
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(str(args.get("content", "")), encoding="utf-8")
        return f"已写入: {p}"

    if name == "list_directory":
        rel = str(args.get("path") or ".").strip()
        d = _resolve_safe(ctx, rel)
        if not d.is_dir():
            return f"错误: 不是目录或不存在: {d}"
        names = sorted(os.listdir(d))
        return "\n".join(names) if names else "(空目录)"

    if name == "execute_desktop_action":
        raw = args.get("action_json")
        if raw is None:
            return "错误: 缺少 action_json"
        try:
            action = json.loads(raw) if isinstance(raw, str) else raw
        except json.JSONDecodeError as e:
            return f"错误: action_json 不是合法 JSON: {e}"
        if not isinstance(action, dict):
            return "错误: 解析结果必须是 JSON 对象"
        if ctx.executor is None:
            return "错误: 未提供 Executor，无法执行桌面动作"
        return ctx.executor.execute_action(action)

    return f"未知原子工具: {name}"
