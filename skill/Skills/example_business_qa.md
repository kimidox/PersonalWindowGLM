---
id: 1
name: 业务问答示例
description: 用户提出一般业务分析或说明类问题时，先澄清目标再分步回答；需要文件证据时用 read_text_file。
---

## 使用方式

1. 若问题含糊，先用简短文字向用户确认范围或补充条件（可通过 `finish` 直接回复，或继续调用工具收集信息）。
2. 若需要读取项目内文件：使用 `read_text_file` / `list_directory`，路径均为相对工作目录。
3. 若需要操作 Windows 桌面：使用 `execute_desktop_action`，`action_json` 为单个动作对象的 JSON 字符串，字段与现有自动化一致（如 `click`、`type_text`、`over` 等）。
4. 任务结束时必须调用 `finish`，在 `message` 中给出完整用户可见结论。
