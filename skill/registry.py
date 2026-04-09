from __future__ import annotations

from pathlib import Path

from .loader import load_all_skills, load_skill_from_path, resolve_skill_markdown_in_package
from .types import SkillDefinition


class SkillRegistry:
    """管理 Skills 目录：每个 Skill 为根目录下的一级子文件夹，内含主 .md（见 loader）。"""

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
        if p.is_file():
            s = load_skill_from_path(p)
        else:
            rel = self.skills_dir / p
            if rel.is_dir():
                md = resolve_skill_markdown_in_package(rel)
                if md is None:
                    raise FileNotFoundError(f"Skill 包目录中未找到 .md 文件: {rel}")
                s = load_skill_from_path(md)
            elif rel.is_file():
                s = load_skill_from_path(rel)
            else:
                pkg = self.skills_dir / p.name
                if pkg.is_dir():
                    md = resolve_skill_markdown_in_package(pkg)
                    if md is None:
                        raise FileNotFoundError(f"Skill 包目录中未找到 .md 文件: {pkg}")
                    s = load_skill_from_path(md)
                else:
                    raise FileNotFoundError(f"找不到 Skill 文件或包: {rel}")
        self._by_id[s.skill_id] = s
        return s
