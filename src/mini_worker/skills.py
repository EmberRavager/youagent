from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


DEFAULT_SKILLS: dict[str, str] = {
    "organize-files.md": """# Skill: organize-files

## Description
Organize files in a local workspace by type, date, or purpose.

## Inputs
- path: workspace-relative folder path, default `.`
- mode: type/date/purpose, default `type`

## Steps
1. Inspect the target folder with `list_files`.
2. Group files by extension, date, or clear purpose.
3. Produce a preview plan before moving or writing anything.
4. Ask the user for confirmation before applying changes.
5. If confirmed, create folders and move/copy files using safe workspace-relative paths.
6. Verify the final folder structure.

## Safety
- Do not delete files.
- Do not move files outside the workspace.
- Do not overwrite existing files without explicit confirmation.
- Prefer reversible operations and rely on YouAgent undo snapshots.

## Verify
- List the target folder after changes.
- Summarize moved files and skipped files.
""",
    "analyze-log.md": """# Skill: analyze-log

## Description
Analyze a log file, extract important errors, and suggest next diagnostic steps.

## Inputs
- path: workspace-relative log file path
- focus: optional keyword such as error, timeout, exception, redis, mysql, api

## Steps
1. Read the log file with a safe size limit.
2. Search for ERROR, WARN, Exception, timeout, failed, refused, denied, OOM, and stack traces.
3. Group repeated errors by root cause pattern.
4. Explain the likely root cause and impact.
5. Suggest the next commands or checks.

## Safety
- Do not modify files.
- Do not restart services.
- Do not run destructive commands.

## Verify
- Include exact log evidence with file path and line clues when available.
""",
    "diagnose-port.md": """# Skill: diagnose-port

## Description
Diagnose which process is using a local port and what to do next.

## Inputs
- port: local TCP port number

## Steps
1. Use safe shell inspection commands such as `lsof -i :{port}` or `netstat`/`ss` equivalents.
2. Identify PID, process name, command, and listening address.
3. Explain why the port is occupied.
4. Suggest safe next actions.
5. If the user wants to kill a process, ask for explicit confirmation first.

## Safety
- Never kill a process without explicit user confirmation.
- Never use `sudo` unless the user explicitly requests it and understands the risk.

## Verify
- Re-check the port after any confirmed action.
""",
    "debug-local-service.md": """# Skill: debug-local-service

## Description
Diagnose why a local service or development project fails to start.

## Inputs
- command: optional startup command
- path: workspace-relative project path, default `.`

## Steps
1. Inspect README, package files, env examples, and startup scripts.
2. Identify the expected run command.
3. Run safe diagnostic commands only when appropriate.
4. Capture and summarize errors.
5. Check common causes: missing dependency, occupied port, missing env var, wrong Node/Python/Java version, failed database connection.
6. Suggest a minimal fix.

## Safety
- Do not install packages automatically.
- Do not edit config files without confirmation.
- Do not expose secrets from env files.

## Verify
- Provide a concrete command the user can run to confirm the fix.
""",
}


@dataclass(frozen=True)
class Skill:
    name: str
    path: Path
    content: str
    description: str


class SkillRegistry:
    def __init__(self, workspace: str):
        self.workspace = Path(workspace).resolve()
        self.skills_dir = self.workspace / ".youagent" / "skills"

    def ensure_defaults(self, *, overwrite: bool = False) -> list[Path]:
        self.skills_dir.mkdir(parents=True, exist_ok=True)
        written: list[Path] = []
        for filename, content in DEFAULT_SKILLS.items():
            path = self.skills_dir / filename
            if path.exists() and not overwrite:
                continue
            path.write_text(content.strip() + "\n", encoding="utf-8")
            written.append(path)
        return written

    def list_skills(self) -> list[Skill]:
        if not self.skills_dir.exists():
            return []
        skills: list[Skill] = []
        for path in sorted(self.skills_dir.glob("*.md")):
            content = path.read_text(encoding="utf-8", errors="replace")
            name = self._skill_name(path, content)
            description = self._description(content)
            skills.append(Skill(name=name, path=path, content=content, description=description))
        return skills

    def get(self, name: str) -> Skill | None:
        normalized = self._normalize_name(name)
        for skill in self.list_skills():
            if self._normalize_name(skill.name) == normalized or self._normalize_name(skill.path.stem) == normalized:
                return skill
        return None

    def catalog_prompt(self) -> str:
        skills = self.list_skills()
        if not skills:
            return ""
        lines = ["Available workspace skills:"]
        for skill in skills:
            rel = skill.path.relative_to(self.workspace)
            desc = f" - {skill.description}" if skill.description else ""
            lines.append(f"- {skill.name} (`{rel}`){desc}")
        lines.append("Use a skill when the user task clearly matches it. If unsure, inspect files and ask a clarifying question only when necessary.")
        return "\n".join(lines)

    def render_task_prompt(self, skill: Skill, user_args: str) -> str:
        return (
            f"Run the following YouAgent skill for the user's task.\n\n"
            f"Skill name: {skill.name}\n"
            f"Skill file: {skill.path}\n\n"
            f"--- BEGIN SKILL ---\n{skill.content.strip()}\n--- END SKILL ---\n\n"
            f"User arguments / task details:\n{user_args.strip() or '(none)'}\n\n"
            "Follow the skill steps. Inspect before acting. For risky, destructive, or external-side-effect operations, present a preview plan and ask for confirmation before executing."
        )

    @staticmethod
    def _normalize_name(name: str) -> str:
        return name.strip().lower().replace("_", "-")

    @classmethod
    def _skill_name(cls, path: Path, content: str) -> str:
        for line in content.splitlines():
            stripped = line.strip()
            if stripped.lower().startswith("# skill:"):
                return stripped.split(":", 1)[1].strip()
            if stripped.startswith("# "):
                return stripped[2:].strip()
        return path.stem

    @staticmethod
    def _description(content: str) -> str:
        lines = content.splitlines()
        in_description = False
        for line in lines:
            stripped = line.strip()
            if stripped.lower() == "## description":
                in_description = True
                continue
            if in_description:
                if stripped.startswith("## "):
                    break
                if stripped:
                    return stripped
        return ""
