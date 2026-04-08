from __future__ import annotations

from pathlib import Path

from .types import SkillDefinition


def _parse_simple_frontmatter(raw: str) -> tuple[dict[str, str], str]:
    """
    解析可选的 YAML 风格前置块（无 PyYAML 依赖）：以 --- 包裹的简单 key: value 行。
    """
    text = raw.lstrip("\ufeff")
    if not text.startswith("---"):
        return {}, text

    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text

    meta_block = parts[1].strip()
    body = parts[2].lstrip("\n")
    meta: dict[str, str] = {}
    for line in meta_block.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            continue
        k, v = line.split(":", 1)
        meta[k.strip()] = v.strip().strip('"').strip("'")
    return meta, body


def load_skill_from_path(path: Path) -> SkillDefinition:
    raw = path.read_text(encoding="utf-8", errors="replace")
    meta, body = _parse_simple_frontmatter(raw)
    skill_id = (meta.get("id") or meta.get("skill_id") or path.stem).strip()
    name = (meta.get("name") or skill_id).strip()
    description = (meta.get("description") or meta.get("desc") or "").strip()
    extra = {k: v for k, v in meta.items() if k not in ("id", "skill_id", "name", "description", "desc")}
    return SkillDefinition(
        skill_id=skill_id,
        name=name,
        description=description,
        body=body.strip(),
        source_path=path.resolve(),
        extra_meta=extra,
    )


def discover_skill_files(skills_dir: Path) -> list[Path]:
    if not skills_dir.is_dir():
        return []
    paths: list[Path] = []
    for p in sorted(skills_dir.iterdir()):
        if p.is_file() and p.suffix.lower() in (".md", ".markdown", ".txt"):
            paths.append(p)
    return paths


def load_all_skills(skills_dir: Path) -> list[SkillDefinition]:
    return [load_skill_from_path(p) for p in discover_skill_files(skills_dir)]
