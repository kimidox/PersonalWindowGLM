from __future__ import annotations

from pathlib import Path

from .loader import load_all_skills, load_skill_from_path
from .types import SkillDefinition


class SkillRegistry:
    """管理 Skills 目录：发现、按 id 查找、热加载单文件。"""

    def __init__(self, skills_dir: str | Path) -> None:
        self.skills_dir = Path(skills_dir).resolve()
        self._by_id: dict[str, SkillDefinition] = {}
        self.reload()

    def reload(self) -> None:
        self._by_id = {s.skill_id: s for s in load_all_skills(self.skills_dir)}

    def list_skills(self) -> list[SkillDefinition]:
        return list(self._by_id.values())

    def get(self, skill_id: str) -> SkillDefinition | None:
        return self._by_id.get((skill_id or "").strip())

    def load_file(self, path: str | Path) -> SkillDefinition:
        p = Path(path)
        if not p.is_file():
            p = self.skills_dir / path
        s = load_skill_from_path(p)
        self._by_id[s.skill_id] = s
        return s
