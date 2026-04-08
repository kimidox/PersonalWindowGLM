from __future__ import annotations

ATOMIC_TOOL_DEFINITIONS: list[dict] = [
    {
        "name": "read_text_file",
        "description": "在工作目录下读取 UTF-8 文本文件。path 为相对 work_dir 的相对路径。",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "相对工作目录的文件路径"},
            },
            "required": ["path"],
        },
    },
    {
        "name": "write_text_file",
        "description": "在工作目录下写入 UTF-8 文本文件（必要时创建父目录）。path 为相对路径。",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "相对工作目录的文件路径"},
                "content": {"type": "string", "description": "文件完整文本内容"},
            },
            "required": ["path", "content"],
        },
    },
    {
        "name": "list_directory",
        "description": "列出工作目录下某相对路径中的文件与子目录名称。",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "相对工作目录的目录路径，空或 '.' 表示工作目录根",
                },
            },
            "required": [],
        },
    },
    {
        "name": "execute_desktop_action",
        "description": (
            "执行桌面自动化动作。参数 action 为 JSON 字符串，解析后传给 Executor.execute_action。"
            " 例如 '{\"action\":\"click\",\"x\":10,\"y\":5}'；完成业务后可用 {\"action\":\"over\"}。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "action_json": {
                    "type": "string",
                    "description": "表示单个 action 字典的 JSON 字符串",
                },
            },
            "required": ["action_json"],
        },
    },
]
