from __future__ import annotations

from .processing import format_skill_for_prompt, normalize_skill_id
from .registry import SkillRegistry

SKILL_CONTROL_TOOL_DEFINITIONS: list[dict] = [
    {
        "name": "select_skill",
        "description": (
            "从 Skill 列表中按 skill_id 加载完整文档。同一轮对话可多次调用："
            "若任务需要多种规范（例如先走 A 流程再走 B 约束），应依次 select_skill；"
            "后加载的文档会与先前已加载的一并作为约束，而非互相覆盖。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "skill_id": {"type": "string", "description": "Skill 唯一标识，与列表中反引号内一致"},
            },
            "required": ["skill_id"],
        },
    },
    {
        "name": "finish",
        "description": "当已根据所选 Skill（可多个）完成用户业务目标时调用，返回面向用户的最终答复。",
        "parameters": {
            "type": "object",
            "properties": {
                "message": {"type": "string", "description": "给用户的最终说明或结果摘要"},
            },
            "required": ["message"],
        },
    },
]


def execute_skill_control_tool(
    name: str,
    args: dict,
    *,
    registry: SkillRegistry,
    active_skill_text: list[str],
    active_skill_ids: list[str],
    disabled_skill_ids: frozenset[str] | None = None,
) -> tuple[str, bool, str | None]:
    """
    执行 Skill 控制类工具。
    返回 (tool_result_text, should_terminate, final_user_message)。
    should_terminate 为 True 且 final_user_message 非空时表示正常结束。
    """
    if name == "select_skill":
        print(f"select_skill: {args}")
        sid = normalize_skill_id(str(args.get("skill_id", "")))
        if sid in active_skill_ids:
            i = active_skill_ids.index(sid)
            return (active_skill_text[i], False, None)
        if disabled_skill_ids is not None and sid in disabled_skill_ids:
            return (
                f"错误: Skill「{sid}」已在设置中禁用，无法加载到会话。请在界面设置中重新启用后再试。",
                False,
                None,
            )
        s = registry.get(sid)
        if s is None:
            return (f"错误: 未找到 skill_id={sid!r}。请从系统提示的列表中选择有效 id。", False, None)
        doc = format_skill_for_prompt(s)
        active_skill_text.append(doc)
        active_skill_ids.append(sid)
        return (doc, False, None)

    if name == "finish":
        msg = str(args.get("message", "")).strip()
        return (msg or "（完成）", True, msg or "（完成）")

    return (f"未知 Skill 控制工具: {name}", False, None)
