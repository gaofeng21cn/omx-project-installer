#!/usr/bin/env python3
from __future__ import annotations

import os
from pathlib import Path


def main() -> int:
    baseline_dir = Path(__file__).resolve().parent
    codex_home = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))
    skills_dir = codex_home / "skills"
    skill_name = "omx-project-installer"
    source_skill_dir = baseline_dir / "skills" / skill_name
    target_skill_dir = skills_dir / skill_name

    if not source_skill_dir.exists():
        raise SystemExit(f"Missing skill source: {source_skill_dir}")

    skills_dir.mkdir(parents=True, exist_ok=True)
    if target_skill_dir.exists() or target_skill_dir.is_symlink():
        target_skill_dir.unlink()
    target_skill_dir.symlink_to(source_skill_dir)

    print(f"Installed {skill_name} -> {target_skill_dir}")
    print("Next: in a target repo, tell Codex:")
    print("  使用 $omx-project-installer，把当前项目完成 OMX project-scope 安装与合同分层收口。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
