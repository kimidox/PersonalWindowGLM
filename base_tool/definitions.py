from __future__ import annotations

ATOMIC_TOOL_DEFINITIONS: list[dict] = [
    {
        "name": "read_text_file",
        "description": "在工作目录下读取 UTF-8 文本文件。path 为相对 work_dir 的相对路径。如果path来源于某个skill中，则skill_id为该skill的id",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "相对工作目录的文件路径"},
                "skill_id":{"type": "integer", "description": "path来源的skill_id"}
            },
            "required": ["path"],
        },
    },
    {
        "name": "write_text_file",
        "description": "写入 UTF-8 文本文件。path 为相对 work_dir 的相对路径。如果path来源于某个skill中，则skill_id为该skill的id",
        "parameters": {
            "type": "object",
            "properties": {
                "content": {"type": "string", "description": "文件完整文本内容"},
                "path": {"type": "string", "description": "要写入的相对工作目录的文件路径"},
                "skill_id": {"type": "integer", "description": "path来源的skill_id"}
            },
            "required": [ "content","path"],
        },
    },
    {
        "name": "list_directory",
        "description": "列出工作目录下某相对路径中的文件与子目录名称。path 为相对 work_dir 的相对路径。如果path来源于某个skill中，则skill_id为该skill的id",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "相对工作目录的目录路径，空或 '.' 表示工作目录根",
                },
                "skill_id": {"type": "integer", "description": "path来源的skill_id"}
            },
            "required": ["path"],
        },
    },
    {
        "name": "run_skill_script",
        "description": (
            "在沙箱工作目录内，仅允许执行某个已加载 Skill 包下 `scripts/` 目录中的 Python 文件。"
            "使用 `sys.executable` 以子进程方式运行；工作目录为该 Skill 包根目录。"
            "script 为相对于 Skill 包根的路径，须位于 `scripts/` 下（可写 `scripts/foo.py`，"
            "或仅写 `foo.py` 表示 `scripts/foo.py`）。须传入 skill_id。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "skill_id": {"type": "string", "description": "Skill 的 id，与 select_skill 所用一致"},
                "script": {
                    "type": "string",
                    "description": "相对于 Skill 包根的路径，必须在 scripts/ 下，如 scripts/main.py",
                },
                "argv": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "传给脚本的额外命令行参数（可选）",
                },
                "stdin": {"type": "string", "description": "写入子进程 stdin 的文本（可选）"},
                "timeout_sec": {
                    "type": "number",
                    "description": "超时秒数，默认 60，最大 180",
                },
            },
            "required": [ "script"],
        },
    },
]
