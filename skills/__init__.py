"""轻量级 Skill 加载器 — 将 SKILL.md 解析为可注入系统提示词的结构化片段。

Skill 格式兼容 Hermes Agent（MIT）：目录 + SKILL.md（YAML frontmatter + Markdown body）。
"""

import os
import re
from dataclasses import dataclass

_FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.DOTALL)

SKILLS_DIR = os.path.join(os.path.dirname(__file__))


@dataclass
class SkillMeta:
    name: str
    description: str
    version: str
    body: str  # frontmatter 之后的 Markdown 正文


def _parse_skill_md(text: str) -> tuple[dict, str]:
    """拆分 YAML frontmatter 和 body。返回 (header_dict, body)。"""
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return {}, text
    header_raw = m.group(1)
    body = text[m.end():]
    # 简易 YAML 解析，只取顶级 key: value
    header = {}
    for line in header_raw.splitlines():
        if ":" in line and not line.startswith(" "):
            key, _, val = line.partition(":")
            header[key.strip()] = val.strip().strip('"').strip("'")
    return header, body


class SkillLoader:
    """发现并管理 skills/ 下的所有 Skill。"""

    def __init__(self, skills_dir: str = SKILLS_DIR):
        self.skills_dir = skills_dir
        self.skills: dict[str, SkillMeta] = {}
        self._discover()

    def _discover(self):
        if not os.path.isdir(self.skills_dir):
            return
        for entry in os.listdir(self.skills_dir):
            skill_path = os.path.join(self.skills_dir, entry, "SKILL.md")
            if os.path.isfile(skill_path):
                try:
                    with open(skill_path, "r", encoding="utf-8") as f:
                        text = f.read()
                    header, body = _parse_skill_md(text)
                    name = header.get("name", entry)
                    self.skills[name] = SkillMeta(
                        name=name,
                        description=header.get("description", ""),
                        version=header.get("version", "0.0.0"),
                        body=body.strip(),
                    )
                except Exception:
                    pass

    def list_skills(self) -> str:
        if not self.skills:
            return "当前没有可用的技能。"
        lines = ["可用技能列表："]
        for s in self.skills.values():
            lines.append(f"  - {s.name}: {s.description}")
        return "\n".join(lines)

    def get_skill_prompt(self, name: str) -> str | None:
        skill = self.skills.get(name)
        if not skill:
            return None
        return (
            f"\n\n[已激活技能: {skill.name}]\n"
            f"{skill.body}\n"
            f"[技能结束]\n"
        )

    def has_skill(self, name: str) -> bool:
        return name in self.skills
