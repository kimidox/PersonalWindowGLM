from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Optional

import json

import config
from base_tool import ToolContext, all_definition_dicts, execute_atomic_tool, tools_for_model
from executor import Executor
from llm import get_chat_model
from llm.BaseChatModel import BaseChatModel
from skill import (
    SkillRegistry,
    build_skills_catalog_text,
    execute_skill_control_tool,
    format_skill_for_prompt,
    skills_auto_matched_for_query,
    SKILL_CONTROL_TOOL_DEFINITIONS,
)


def _default_skills_dir() -> Path:
    return Path(__file__).resolve().parent / "skill" / "Skills"


def _message_text(message: Any) -> str:
    c = getattr(message, "content", None)
    if isinstance(c, str) and c.strip():
        return c.strip()
    return ""


def _build_system_prompt(catalog: str) -> str:
    return f"""你是 SkillAgent：根据用户的业务提问，从下列 Skill 中选择并执行合适流程。

{catalog}

## 工具使用约定
0. 部分 Skill 可能已在每轮开头由系统按 `auto_load` 或 **description 触发短语**（用 、，等分隔）自动注入，须遵守；若仍需其它 Skill，可再 `select_skill`（已自动加载的 id 再选不会重复追加）。
1. 按需调用 `select_skill` 加载 Skill 全文（可加载一个或多个）。若用户任务明显需要多套规范，请依次 `select_skill`；下文会同时列出本轮已加载的全部 Skill，须一并遵守（若有冲突，以更具体或后加载的说明为准）。
2. 执行过程中使用原子工具（读写文件、列目录、桌面自动化等）完成具体操作；桌面自动化通过 `execute_desktop_action` 传入单个动作的 JSON 字符串。
3. 当你认为已满足用户目标时，调用 `finish`，在参数 `message` 中给出完整、用户可读的最终答复。
4. 若当前没有可用 Skill，可直接用原子工具与常识完成用户请求，并 `finish` 结束。
"""


class SkillAgent:
    def __init__(
        self,
        work_dir: str,
        *,
        skills_dir: str | Path | None = None,
        max_steps: int | None = None,
        executor: Executor | None = None,
    ) -> None:
        self.work_dir = str(Path(work_dir).resolve())
        sd = skills_dir if skills_dir is not None else _default_skills_dir()
        self.registry = SkillRegistry(sd)
        self.max_steps = int(max_steps if max_steps is not None else config.SKILL_AGENT_MAX_STEPS)
        self.executor = executor
        self._tool_ctx = ToolContext(work_dir=self.work_dir, executor=executor)
        self._definitions = list(SKILL_CONTROL_TOOL_DEFINITIONS) + list(all_definition_dicts())

    def reload_skills(self) -> None:
        self.registry.reload()

    def _merged_tools(self, model: BaseChatModel) -> list[dict]:
        return tools_for_model(model, self._definitions)

    def _dispatch(
        self,
        name: str,
        args: dict,
        active_skill_text: list[str],
        active_skill_ids: list[str],
    ) -> tuple[str, bool, Optional[str]]:
        if name in ("select_skill", "finish"):
            return execute_skill_control_tool(
                name,
                args,
                registry=self.registry,
                active_skill_text=active_skill_text,
                active_skill_ids=active_skill_ids,
            )
        return (execute_atomic_tool(name, args, self._tool_ctx), False, None)

    def run(self, user_query: str, log_callback: Optional[Callable[[str, str], Any]] = None) -> str:
        model = get_chat_model()
        tools = self._merged_tools(model)
        catalog = build_skills_catalog_text(self.registry.list_skills())
        system_prompt = _build_system_prompt(catalog)
        messages: list[dict] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_query.strip()},
        ]
        active_skill_text: list[str] = []
        active_skill_ids: list[str] = []

        if getattr(config, "SKILL_AGENT_AUTO_LOAD", True):
            auto_skills = skills_auto_matched_for_query(self.registry.list_skills(), user_query.strip())
            for s in auto_skills:
                doc = format_skill_for_prompt(s)
                active_skill_text.append(doc)
                active_skill_ids.append(str(s.skill_id).strip())
            if auto_skills:
                parts = [
                    f"### 自动加载 Skill #{i + 1}（id：`{s.skill_id}`）\n\n{t.strip()}"
                    for i, (s, t) in enumerate(zip(auto_skills, active_skill_text))
                ]
                merged_auto = "\n\n---\n\n".join(parts)
                messages.append(
                    {
                        "role": "user",
                        "content": (
                            "以下 Skill 已由系统根据 `auto_load` 或 **description** 与用户问题的匹配规则 "
                            "自动加载，须与后续通过 `select_skill` 追加的文档一并遵守：\n\n" + merged_auto
                        ),
                    }
                )
                if log_callback:
                    ids_join = "、".join(active_skill_ids)
                    log_callback(
                        f"自动命中 Skill（规则）｜id：{ids_join}（共 {len(auto_skills)} 个）",
                        "tool",
                    )
                    log_callback(
                        "［自动加载的 Skill 文档汇总］\n\n" + merged_auto,
                        "doc",
                    )

        for step in range(self.max_steps):
            msg = model.complete_with_tools(messages, tools)
            fc = model.extract_function_call(msg)
            if not fc:
                text = _message_text(msg)
                if text:
                    if log_callback:
                        log_callback(text, "assistant")
                    return text
                err = "模型未返回工具调用且无文本内容，无法继续。"
                if log_callback:
                    log_callback(err, "assistant")
                return err

            fname = fc.get("name") or ""
            arg_str = fc.get("arguments") or "{}"
            try:
                args = json.loads(arg_str) if isinstance(arg_str, str) else {}
            except json.JSONDecodeError:
                args = {}

            if log_callback:
                if fname == "finish":
                    log_callback(str(args.get("message", "")), "assistant")
                elif fname != "select_skill":
                    try:
                        args_s = json.dumps(args, ensure_ascii=False)
                    except (TypeError, ValueError):
                        args_s = str(args)
                    log_callback(f"调用工具 `{fname}` · {args_s}", "tool")

            result, terminate, final = self._dispatch(fname, args, active_skill_text, active_skill_ids)

            if log_callback and fname == "select_skill":
                if str(result).startswith("错误"):
                    log_callback(f"选择 Skill 失败：{result}", "tool")
                else:
                    ids_join = "、".join(active_skill_ids)
                    n = len(active_skill_ids)
                    log_callback(
                        f"命中 Skill「{args.get('skill_id', '')}」｜本轮已累计 id：{ids_join}（共 {n} 个）",
                        "tool",
                    )
                    prefix = (
                        f"［第 {n} 次加载｜本轮已累计 {n} 份｜id 顺序：{ids_join}］\n\n"
                    )
                    log_callback(prefix + str(result), "doc")

            if log_callback and fname != "finish" and fname != "select_skill":
                r = str(result)
                if len(r) > 12000:
                    r = r[:12000] + "\n\n…（内容已截断）"
                log_callback(r, "assistant")

            if terminate and final is not None:
                return final

            messages.append({"role": "tool", "name": fname, "content": str(result)})
            if fname == "select_skill" and active_skill_text and not str(result).startswith("错误"):
                parts = [
                    f"### 已加载 Skill #{i + 1}\n\n{t.strip()}"
                    for i, t in enumerate(active_skill_text)
                ]
                merged = "\n\n---\n\n".join(parts)
                messages.append(
                    {
                        "role": "user",
                        "content": (
                            "当前会话中已加载的 Skill 文档如下（按加载顺序，须同时遵守；"
                            "若有冲突以更具体的条款或后加载的文档为准）：\n\n" + merged
                        ),
                    }
                )

        tail = f"已达到最大执行步数限制（{self.max_steps}），已停止。"
        if log_callback:
            log_callback(tail, "assistant")
        return tail
