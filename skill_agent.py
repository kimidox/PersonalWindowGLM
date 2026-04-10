from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any, Callable, Optional

import config
from base_tool import ToolContext, all_definition_dicts, execute_atomic_tool, tools_for_model
from executor import Executor
from llm import get_chat_model
from llm.BaseChatModel import BaseChatModel
from memory import Memory
from skill import (
    SkillRegistry,
    build_skills_catalog_text,
    execute_skill_control_tool,
    skills_auto_matched_for_query,
    SKILL_CONTROL_TOOL_DEFINITIONS,
)


def _message_text(message: Any) -> str:
    c = getattr(message, "content", None)
    if isinstance(c, str) and c.strip():
        return c.strip()
    return ""


def _history_without_system(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [m for m in messages if m.get("role") != "system"]


def _build_system_prompt(catalog: str) -> str:
    return f"""你是 SkillAgent：根据用户的业务提问，从下列 Skill 中选择并执行合适流程。

{catalog}

## 工具使用约定
0. 部分Skill里面描述中若说明仍需其它 Skill，可再 `select_skill`（已自动加载的 id 再选不会重复追加）。
1. 按需调用 `select_skill` 加载 Skill 全文（可加载一个或多个）。若用户任务明显需要多套规范，请依次 `select_skill`；下文会同时列出本轮已加载的全部 Skill，须一并遵守（若有冲突，以更具体或后加载的说明为准）。
2. 执行过程中使用原子工具（读文件、写文件、列目录、桌面自动化等）完成具体操作；桌面自动化通过 `execute_desktop_action` 传入单个动作的 JSON 字符串。
4. 部分Skill的md文件里面描述若说明仍需要读取相对路径下的文件时，需要调用原子工具-读文件，传入的Path要拼接上该相对路径所属的Skill的dir；同一输出文件最多写入一次，除非用户要求修改
4. 当你认为已满足用户目标时，调用 `finish`，在参数 `message` 中给出完整、用户可读的最终答复。
5. 若当前没有可用 Skill，可直接用原子工具与常识完成用户请求，并 `finish` 结束。
"""


class SkillAgent:
    def __init__(
        self,
        work_dir: str,
        *,
        skills_dir: str | Path | None = None,
        max_steps: int | None = None,
        executor: Executor | None = None,
        memory: Memory | None = None,
        conversation_id: str | None = None,
        username: str ,
    ) -> None:
        self.work_dir = str(Path(work_dir).resolve())
        sd = skills_dir if skills_dir is not None else config.SKILLS_DIR
        self.registry = SkillRegistry(sd)
        self.max_steps = int(max_steps if max_steps is not None else config.SKILL_AGENT_MAX_STEPS)
        self.executor = executor
        self.memory = memory
        self.username = username
        if memory is not None:
            self._conversation_id = conversation_id or str(uuid.uuid4())
        else:
            self._conversation_id = conversation_id or ""
        self._tool_ctx = ToolContext(work_dir=self.work_dir, executor=executor)
        self._definitions = list(SKILL_CONTROL_TOOL_DEFINITIONS) + list(all_definition_dicts())

    @property
    def conversation_id(self) -> str:
        return self._conversation_id

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

    def _append_model_messages(
        self,
        messages: list[dict[str, Any]],
        *,
        system_prompt: str,
        user_query: str,
    ) -> None:
        """从 Memory 恢复历史（不含 system），再追加本轮用户输入；system 始终用当前 catalog 现算。"""
        assert self.memory is not None
        cid = self._conversation_id
        self.memory.set_active_skills(cid, [])
        prior = _history_without_system(self.memory.get_messages(cid))
        messages.clear()
        messages.append({"role": "system", "content": system_prompt})
        messages.extend(prior)
        self.memory.append_message(cid, "user", user_query.strip())
        messages.append({"role": "user", "content": user_query.strip()})

    def _persist_after_tool_turn(
        self,
        fname: str,
        args:dict,
        result: str,
        active_skill_text: list[str],
        active_skill_ids: list[str],
        messages: list[dict[str, Any]],
    ) -> None:
        assert self.memory is not None
        cid = self._conversation_id
        args_str=json.dumps(args, ensure_ascii=False, indent=2)
        if fname == "select_skill":
            self.memory.append_message(cid, "tool", str(result), metadata={"type":"skill","name": fname,"args":args_str})
        else:
            self.memory.append_message(cid, "tool", str(result), metadata={"type":"base_tool","name": fname,"args":args_str})
        messages.append({"role": "tool", "name": fname, "content": str(result)})
        if fname == "select_skill" and active_skill_text and not str(result).startswith("错误"):
            self.memory.set_active_skills(cid, list(active_skill_ids))
            parts = [
                f"### 已加载 Skill #{i + 1}\n\n{t.strip()}"
                for i, t in enumerate(active_skill_text)
            ]
            merged = "\n\n---\n\n".join(parts)
            extra_user = (
                "当前会话中已加载的 Skill 文档如下（按加载顺序，须同时遵守；"
                "若有冲突以更具体的条款或后加载的文档为准）：\n\n" + merged
            )
            self.memory.append_message(cid, "user", extra_user,metadata={"type":"skill_content"})
            messages.append({"role": "user", "content": extra_user})

    def run(self, user_query: str, log_callback: Optional[Callable[[str, str], Any]] = None) -> str:
        model = get_chat_model()
        tools = self._merged_tools(model)
        catalog = build_skills_catalog_text(self.registry.list_skills())
        system_prompt = _build_system_prompt(catalog)
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_query.strip()},
        ]
        active_skill_text: list[str] = []
        active_skill_ids: list[str] = []

        if self.memory is not None:
            self._append_model_messages(messages, system_prompt=system_prompt, user_query=user_query)

        for step in range(self.max_steps):
            msg = model.complete_with_tools(messages, tools)
            fc = model.extract_function_call(msg)
            if not fc:
                text = _message_text(msg)
                if text:
                    if log_callback:
                        log_callback(text, "assistant")
                    if self.memory is not None:
                        self.memory.append_message(self._conversation_id, "assistant", text)
                    return text
                err = "模型未返回工具调用且无文本内容，无法继续。"
                if log_callback:
                    log_callback(err, "assistant")
                if self.memory is not None:
                    self.memory.append_message(self._conversation_id, "assistant", err)
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
            # 执行tool
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
                # 正常执行结束，最后回答非空
                if self.memory is not None:
                    cid = self._conversation_id
                    self.memory.append_message(cid, "tool", str(result), metadata={"name": fname})
                    self.memory.append_message(cid, "assistant", str(final))
                return final

            if self.memory is not None:
                self._persist_after_tool_turn(fname, args,str(result), active_skill_text, active_skill_ids, messages)
            else:
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
        if self.memory is not None:
            self.memory.append_message(self._conversation_id, "assistant", tail)
        return tail
