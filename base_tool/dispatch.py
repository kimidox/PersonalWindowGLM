from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

from skill import SkillRegistry
from .context import ToolContext

_RUN_SKILL_SCRIPT_MAX_TOTAL_OUT = 12000
_RUN_SKILL_SCRIPT_DEFAULT_TIMEOUT = 60
_RUN_SKILL_SCRIPT_MAX_TIMEOUT = 180


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

def splice_skill_path(rel_path: str, skill_id: str,registry: SkillRegistry):
    skill = registry.get(str(skill_id))
    if skill:
        skill_relative_path_parent = skill.relative_path.parent
        if skill_relative_path_parent:
            rel_path = os.path.join(skill_relative_path_parent, rel_path)
            return rel_path
        raise ValueError(f"未找到 Skill skill_relative_path_parent")
    raise ValueError(f"未找到 Skill {skill_id}")


def _normalize_skill_script_rel(raw: str) -> tuple[str | None, str | None]:
    """返回 (相对 skill 包根的路径, 错误信息)。"""
    s = (raw or "").strip().replace("\\", "/")
    while "//" in s:
        s = s.replace("//", "/")
    if not s:
        return None, "错误: script 不能为空"
    parts = [p for p in s.split("/") if p != ""]
    if any(p == ".." for p in parts):
        return None, "错误: script 路径中不允许使用 .."
    if not s.startswith("scripts/"):
        if len(parts) > 1:
            return None, "错误: script 须以 scripts/ 开头（相对于 Skill 包根目录），或仅提供 scripts 下的文件名"
        s = "scripts/" + s
    return s, None


def _truncate_run_output(text: str, limit: int = _RUN_SKILL_SCRIPT_MAX_TOTAL_OUT) -> str:
    t = text or ""
    if len(t) <= limit:
        return t
    return t[:limit] + "\n\n…（输出已截断）"


def execute_atomic_tool(name: str, args: dict, ctx: ToolContext, registry: SkillRegistry,) -> str:
    if name == "read_text_file":
        rel_path=str(args.get("path", ""))
        if args.get("skill_id"):
            rel_path=splice_skill_path(rel_path,args.get("skill_id"),registry)
        p = _resolve_safe(ctx,rel_path )
        if not p.is_file():
            return f"错误: 不是文件或不存在: {p}"
        return p.read_text(encoding="utf-8", errors="replace")

    if name == "write_text_file":
        rel_path=str(args.get("path", ""))
        if args.get("skill_id"):
            rel_path=splice_skill_path(rel_path,args.get("skill_id"),registry)
        p = _resolve_safe(ctx, str(rel_path))
        p.parent.mkdir(parents=True, exist_ok=True)
        print(f"已写入: {len(args.get('content', ''))}")
        p.write_text(str(args.get("content", "")), encoding="utf-8")
        return f"已写入: {p}"

    if name == "list_directory":
        rel_path = str(args.get("path", ""))
        if args.get("skill_id"):
            rel_path = splice_skill_path(rel_path, args.get("skill_id"), registry)
        d = _resolve_safe(ctx, rel_path)
        if not d.is_dir():
            return f"错误: 不是目录或不存在: {d}"
        names = sorted(os.listdir(d))
        return "\n".join(names) if names else "(空目录)"

    if name == "run_skill_script":
        sid = str(args.get("skill_id", "") or "").strip()
        if not sid:
            return "错误: 缺少 skill_id"
        script_raw = str(args.get("script", "") or "")
        norm_rel, err = _normalize_skill_script_rel(script_raw)
        if err:
            return err
        assert norm_rel is not None
        try:
            rel_spliced = splice_skill_path(norm_rel, sid, registry)
        except ValueError as e:
            return f"错误: {e}"

        try:
            script_path = _resolve_safe(ctx, rel_spliced)
        except ValueError as e:
            return f"错误: {e}"

        try:
            scripts_root_rel = splice_skill_path("scripts", sid, registry)
            scripts_root = _resolve_safe(ctx, scripts_root_rel)
        except ValueError as e:
            return f"错误: {e}"

        if not scripts_root.is_dir():
            return f"错误: 该 Skill 包下不存在 scripts 目录: {scripts_root}"
        try:
            script_path.resolve().relative_to(scripts_root.resolve())
        except ValueError:
            return "错误: 解析后的脚本路径不在该 Skill 的 scripts/ 目录内"
        if script_path.suffix.lower() != ".py":
            return "错误: 仅允许执行 .py 文件"
        if not script_path.is_file():
            return f"错误: 脚本不存在或不是文件: {script_path}"

        raw_argv = args.get("argv")
        if raw_argv is None:
            argv_extra: list[str] = []
        elif isinstance(raw_argv, list):
            argv_extra = [str(x) for x in raw_argv]
        else:
            return "错误: argv 必须是字符串数组"

        stdin_text = args.get("stdin")
        stdin_payload = (str(stdin_text) if stdin_text is not None else None)

        try:
            timeout_raw = args.get("timeout_sec", _RUN_SKILL_SCRIPT_DEFAULT_TIMEOUT)
            timeout_sec = int(float(timeout_raw))
        except (TypeError, ValueError):
            timeout_sec = _RUN_SKILL_SCRIPT_DEFAULT_TIMEOUT
        timeout_sec = max(1, min(timeout_sec, _RUN_SKILL_SCRIPT_MAX_TIMEOUT))

        pkg_root = scripts_root.resolve().parent
        cmd = [sys.executable, str(script_path.resolve()), *argv_extra]
        popen_kw: dict = {
            "cwd": str(pkg_root),
            "capture_output": True,
            "text": True,
            "encoding": "utf-8",
            "errors": "replace",
            "timeout": timeout_sec,
        }
        if sys.platform == "win32":
            popen_kw["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)

        try:
            proc = subprocess.run(
                cmd,
                input=stdin_payload if stdin_payload is not None else None,
                **popen_kw,
            )
        except subprocess.TimeoutExpired as e:
            out = (e.stdout or "") + (e.stderr or "")
            tail = _truncate_run_output(out)
            return f"错误: 脚本执行超时（{timeout_sec}s）\n{tail}".strip()

        stdout = proc.stdout or ""
        stderr = proc.stderr or ""
        merged = (
            f"exit_code: {proc.returncode}\n"
            f"--- stdout ---\n{stdout}\n"
            f"--- stderr ---\n{stderr}"
        )
        return _truncate_run_output(merged)

    # if name == "execute_desktop_action":
    #     raw = args.get("action_json")
    #     if raw is None:
    #         return "错误: 缺少 action_json"
    #     try:
    #         action = json.loads(raw) if isinstance(raw, str) else raw
    #     except json.JSONDecodeError as e:
    #         return f"错误: action_json 不是合法 JSON: {e}"
    #     if not isinstance(action, dict):
    #         return "错误: 解析结果必须是 JSON 对象"
    #     if ctx.executor is None:
    #         return "错误: 未提供 Executor，无法执行桌面动作"
    #     return ctx.executor.execute_action(action)

    return f"未知原子工具: {name}"
