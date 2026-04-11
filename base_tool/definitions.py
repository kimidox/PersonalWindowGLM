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
            "required": ["path","skill_id"],
        },
    },
    {
        "name": "write_text_file",
        "description": "写入 UTF-8 文本文件",
        "parameters": {
            "type": "object",
            "properties": {
                "file_name": {"type": "string", "description": "要写入的文件的文件名，如'示例.md'。"},
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
    }
]
