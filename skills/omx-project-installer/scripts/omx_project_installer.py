#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import glob
import hashlib
import json
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import tomlkit


BASELINE_ROOT = Path(__file__).resolve().parents[3]
MANIFEST_PATH = BASELINE_ROOT / "baseline.manifest.json"


def load_manifest() -> dict[str, Any]:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


MANIFEST = load_manifest()
ROOT_AGENTS_POLICIES = ("auto", "preserve", "template")
PROJECT_CONFIG_POLICIES = ("auto", "preserve", "setup-output")
LEGACY_PROJECT_CONFIG_TABLE_PATHS = (
    ("mcp_servers", "omx_team_run"),
)
REQUIRED_ROOT_WORKTREE_DISCIPLINE = (
    ("omx-worktree-heading", "## OMX Worktree Discipline"),
    (
        "heavy-omx-must-use-worktree",
        "Heavy OMX work must run in an isolated worktree created from current `main`.",
    ),
    (
        "heavy-omx-definition",
        "Heavy OMX work includes `ralph`, `team`, `autopilot`, other long-running tmux-backed OMX sessions, and any lane expected to leave durable runtime state under `.omx/state/`.",
    ),
    (
        "shared-root-stays-light",
        "Keep the shared root checkout on `main` for light reads, planning, review, absorb-to-`main`, push, and cleanup; do not let it become the long-running owner checkout.",
    ),
    (
        "single-heavy-mainline-per-worktree",
        "Allow at most one active heavy OMX mainline per worktree. If multiple long-running lanes are needed, create multiple worktrees.",
    ),
    (
        "clean-owner-worktree-before-start",
        "Before starting a new heavy OMX lane, ensure the owner worktree is clean and free of stale `.omx/state/sessions/*`, lingering tmux sessions, and stale `skill-active` state.",
    ),
    (
        "cleanup-after-stop",
        "After the lane stops, either absorb the verified commits back to `main` or explicitly abandon the lane, then remove its worktree/branch and clear related tmux/session state.",
    ),
    (
        "no-session-only-isolation",
        "Do not rely on session-only isolation to prevent hook interference; use physical worktree isolation.",
    ),
)
ROOT_RUNTIME_STATE_FILES = (
    "session.json",
    "skill-active-state.json",
    "ralph-state.json",
    "team-state.json",
)


def now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def repo_slug(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or "project"


def display_name_from_repo(name: str) -> str:
    parts = re.split(r"[-_]+", name)
    return " ".join(part.capitalize() for part in parts if part) or "Project"


def metadata_path(target: Path) -> Path:
    return target / MANIFEST["managed_metadata_file"]


def project_truth_relpath() -> str:
    return MANIFEST["project_truth_path"]


def default_contract_path(target: Path) -> Path:
    return target / project_truth_relpath()


def omx_agents_path(target: Path) -> Path:
    return target / ".codex" / "AGENTS.md"


def dev_host_contract_paths(target: Path) -> dict[str, Path]:
    root = target / "contracts" / "dev-hosts"
    return {
        "readme": root / "README.md",
        "omx_cli": root / "omx-cli.md",
        "codex_app": root / "codex-app.md",
    }


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def command_capture(cmd: list[str], cwd: Path) -> dict[str, Any]:
    try:
        completed = subprocess.run(cmd, cwd=cwd, check=False, capture_output=True, text=True)
    except FileNotFoundError:
        return {
            "available": False,
            "returncode": None,
            "stdout": "",
            "stderr": "command-not-found",
        }
    return {
        "available": True,
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def resolve_git_probe_path(target: Path, raw: str) -> Path:
    candidate = Path(raw)
    if candidate.is_absolute():
        return candidate.resolve()
    return (target / raw).resolve()


def parse_git_worktree_porcelain(payload: str) -> list[dict[str, str]]:
    entries: list[dict[str, str]] = []
    current: dict[str, str] = {}
    for line in payload.splitlines():
        if not line.strip():
            if current:
                entries.append(current)
                current = {}
            continue
        key, _, value = line.partition(" ")
        if key == "worktree" and current:
            entries.append(current)
            current = {}
        current[key] = value
    if current:
        entries.append(current)
    return entries


def inspect_static_contract_compatibility(target: Path) -> dict[str, Any]:
    result = {
        "in_sync": True,
        "path": "AGENTS.md",
        "missing": [],
    }
    root_path = target / "AGENTS.md"
    if not root_path.exists():
        result["in_sync"] = False
        result["missing"].append("AGENTS.md:missing")
        return result
    content = read_text(root_path)
    for label, required_text in REQUIRED_ROOT_WORKTREE_DISCIPLINE:
        if required_text not in content:
            result["missing"].append(label)
    result["in_sync"] = not result["missing"]
    return result


def inspect_runtime_compatibility(target: Path) -> dict[str, Any]:
    result = {
        "in_sync": True,
        "git_available": False,
        "checkout_kind": "",
        "branch": "",
        "linked_worktree_count": 0,
        "worktrees": [],
        "root_state_files": [],
        "session_directories": [],
        "team_directories": [],
        "tmux_sessions": [],
        "notes": [],
        "risks": [],
    }

    state_root = target / ".omx" / "state"
    result["root_state_files"] = [
        (state_root / name).relative_to(target).as_posix()
        for name in ROOT_RUNTIME_STATE_FILES
        if (state_root / name).exists()
    ]

    sessions_root = state_root / "sessions"
    if sessions_root.exists():
        result["session_directories"] = sorted(
            path.relative_to(target).as_posix()
            for path in sessions_root.iterdir()
            if path.is_dir()
        )

    team_root = state_root / "team"
    if team_root.exists():
        result["team_directories"] = sorted(
            path.relative_to(target).as_posix()
            for path in team_root.iterdir()
            if path.is_dir()
        )

    if result["root_state_files"]:
        result["risks"].append(
            "root-runtime-state-present:" + ",".join(result["root_state_files"])
        )
    if result["session_directories"]:
        result["risks"].append(
            "session-directories-present:" + str(len(result["session_directories"]))
        )
    if result["team_directories"]:
        result["risks"].append(
            "team-state-directories-present:" + str(len(result["team_directories"]))
        )

    git_probe = command_capture(["git", "rev-parse", "--is-inside-work-tree"], target)
    if git_probe["available"] and git_probe["returncode"] == 0 and git_probe["stdout"].strip() == "true":
        result["git_available"] = True
        branch_probe = command_capture(["git", "branch", "--show-current"], target)
        if branch_probe["available"] and branch_probe["returncode"] == 0:
            result["branch"] = branch_probe["stdout"].strip()

        git_dir_probe = command_capture(["git", "rev-parse", "--absolute-git-dir"], target)
        common_dir_probe = command_capture(["git", "rev-parse", "--git-common-dir"], target)
        if (
            git_dir_probe["available"]
            and git_dir_probe["returncode"] == 0
            and common_dir_probe["available"]
            and common_dir_probe["returncode"] == 0
        ):
            git_dir = resolve_git_probe_path(target, git_dir_probe["stdout"].strip())
            common_dir = resolve_git_probe_path(target, common_dir_probe["stdout"].strip())
            result["checkout_kind"] = "linked-worktree" if git_dir != common_dir else "shared-root"

        worktree_probe = command_capture(["git", "worktree", "list", "--porcelain"], target)
        if worktree_probe["available"] and worktree_probe["returncode"] == 0:
            entries = parse_git_worktree_porcelain(worktree_probe["stdout"])
            result["linked_worktree_count"] = max(len(entries) - 1, 0)
            result["worktrees"] = [entry.get("worktree", "") for entry in entries]
    else:
        result["notes"].append("git-inspection-unavailable")

    tmux_probe = command_capture(["tmux", "ls"], target)
    if not tmux_probe["available"]:
        result["notes"].append("tmux-unavailable")
    elif tmux_probe["returncode"] == 0:
        result["tmux_sessions"] = [
            line.split(":", 1)[0]
            for line in tmux_probe["stdout"].splitlines()
            if line.strip()
        ]
        if result["tmux_sessions"]:
            result["risks"].append("tmux-sessions-present:" + str(len(result["tmux_sessions"])))
    else:
        stderr = (tmux_probe["stderr"] or "").lower()
        if "no server running" not in stderr and "failed to connect to server" not in stderr:
            result["notes"].append(f"tmux-inspection-error:{tmux_probe['returncode']}")

    if result["checkout_kind"] == "shared-root" and result["branch"] and result["branch"] != "main":
        result["risks"].append(f"shared-root-checkout-not-on-main:{result['branch']}")

    if result["checkout_kind"] == "shared-root" and (
        result["root_state_files"] or result["session_directories"] or result["team_directories"] or result["tmux_sessions"]
    ):
        result["risks"].append("shared-root-checkout-carries-runtime-state")

    result["in_sync"] = not result["risks"]
    return result


def inspect_compatibility_audit(target: Path) -> dict[str, Any]:
    static_contract = inspect_static_contract_compatibility(target)
    runtime = inspect_runtime_compatibility(target)
    return {
        "in_sync": static_contract["in_sync"] and runtime["in_sync"],
        "static_contract": static_contract,
        "runtime": runtime,
    }


def template_path(key: str) -> Path:
    return BASELINE_ROOT / MANIFEST["templates"][key]


def render_template(path: Path, replacements: dict[str, str]) -> str:
    content = read_text(path)
    for key, value in replacements.items():
        content = content.replace(f"{{{{{key}}}}}", value)
    return content


def backup_file(path: Path, target: Path) -> Path:
    rel_name = path.name
    backup_dir = target / ".omx" / "backups" / "agent-contract-baseline"
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup = backup_dir / f"{now_utc()}-{rel_name}"
    shutil.copy2(path, backup)
    return backup


def sha256_text(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def latest_setup_backup_path(target: Path, relative_path: str) -> Path | None:
    backup_root = target / ".omx" / "backups" / "setup"
    if not backup_root.exists():
        return None
    matches = sorted(glob.glob(str(backup_root / "*" / relative_path)))
    if not matches:
        return None
    return Path(matches[-1])


def latest_setup_backup_text(target: Path, relative_path: str) -> str | None:
    backup = latest_setup_backup_path(target, relative_path)
    if not backup or not backup.exists():
        return None
    return read_text(backup)


def is_full_omx_root_contract(content: str) -> bool:
    return (
        "<!-- omx:generated:agents-md -->" in content
        and "# oh-my-codex - Intelligent Multi-Agent Orchestration" in content
        and "This AGENTS.md is the top-level operating contract for the workspace." in content
    )


def upsert_marked_section(current: str, rendered_section: str, start: str, end: str) -> str:
    block_pattern = re.compile(re.escape(start) + r".*?" + re.escape(end), re.DOTALL)
    if block_pattern.search(current):
        return block_pattern.sub(rendered_section.strip(), current, count=1)
    lines = current.splitlines()
    if not lines:
        return rendered_section.strip() + "\n"
    insert_at = None
    for idx, line in enumerate(lines):
        if line.startswith("## "):
            insert_at = idx
            break
    if insert_at is None:
        insert_at = 1
        if lines and lines[0].startswith("# "):
            while insert_at < len(lines) and lines[insert_at].strip():
                insert_at += 1
            while insert_at < len(lines) and not lines[insert_at].strip():
                insert_at += 1
    new_lines = lines[:insert_at] + [""] + rendered_section.strip().splitlines() + [""] + lines[insert_at:]
    return "\n".join(new_lines).rstrip() + "\n"


def ensure_gitignore_entries(gitignore_path: Path, entries: list[str]) -> bool:
    existing = read_text(gitignore_path) if gitignore_path.exists() else ""
    lines = existing.splitlines()
    changed = False
    for entry in entries:
        if entry not in lines:
            if lines and lines[-1].strip():
                lines.append("")
            lines.append(entry)
            changed = True
    if changed or not gitignore_path.exists():
        content = "\n".join(lines).rstrip() + "\n"
        write_text(gitignore_path, content)
    return changed


def load_toml(path: Path) -> Any:
    return tomlkit.parse(read_text(path))


def write_toml(path: Path, doc: Any) -> None:
    write_text(path, tomlkit.dumps(doc))


def deepcopy_toml_item(item: Any) -> Any:
    return copy.deepcopy(item)


def normalize_toml_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): normalize_toml_value(v) for k, v in value.items()}
    if isinstance(value, list):
        return [normalize_toml_value(v) for v in value]
    if isinstance(value, tuple):
        return [normalize_toml_value(v) for v in value]
    if hasattr(value, "value"):
        try:
            inner = value.value
            return normalize_toml_value(inner)
        except Exception:
            pass
    return value


def project_config_path(target: Path) -> Path:
    return target / ".codex" / "config.toml"


def empty_config_reconcile_result() -> dict[str, Any]:
    return {
        "applied": False,
        "user_config_present": False,
        "project_config_present": False,
        "keys_synced": [],
        "tables_synced": [],
        "managed_keys_synced": [],
        "managed_tables_synced": [],
    }


def config_table_path_label(path: tuple[str, ...]) -> str:
    return ".".join(path)


def has_config_table_path(doc: Any, path: tuple[str, ...]) -> bool:
    current = doc
    for key in path:
        if key not in current:
            return False
        current = current[key]
    return True


def remove_config_table_path(doc: Any, path: tuple[str, ...]) -> bool:
    parents: list[tuple[Any, str]] = []
    current = doc
    for key in path[:-1]:
        if key not in current:
            return False
        parents.append((current, key))
        current = current[key]
    leaf = path[-1]
    if leaf not in current:
        return False
    del current[leaf]
    for parent, key in reversed(parents):
        child = parent[key]
        try:
            empty = len(child) == 0
        except Exception:
            empty = False
        if empty:
            del parent[key]
            continue
        break
    return True


def prune_legacy_project_config_tables(project_doc: Any) -> list[str]:
    removed: list[str] = []
    for path in LEGACY_PROJECT_CONFIG_TABLE_PATHS:
        if remove_config_table_path(project_doc, path):
            removed.append(f"{config_table_path_label(path)}:legacy-removed")
    return removed


def ensure_toml_table(doc: Any, table_key: str) -> Any:
    if table_key not in doc:
        doc[table_key] = tomlkit.table()
    return doc[table_key]


def remove_table_subkey(doc: Any, table_key: str, subkey: str) -> bool:
    if table_key not in doc:
        return False
    table = doc[table_key]
    if subkey not in table:
        return False
    del table[subkey]
    try:
        empty = len(table) == 0
    except Exception:
        empty = False
    if empty:
        del doc[table_key]
    return True


def sync_setup_managed_root_keys(project_doc: Any, setup_doc: Any) -> list[str]:
    synced: list[str] = []
    managed = MANIFEST.get("setup_managed_config", {})
    for key in managed.get("root_keys", []):
        if key in setup_doc:
            value = deepcopy_toml_item(setup_doc[key])
            if key not in project_doc or normalize_toml_value(project_doc[key]) != normalize_toml_value(value):
                project_doc[key] = value
                synced.append(key)
        elif key in project_doc:
            del project_doc[key]
            synced.append(f"{key}:removed")
    return synced


def sync_setup_managed_table_subkeys(project_doc: Any, setup_doc: Any) -> list[str]:
    synced: list[str] = []
    managed = MANIFEST.get("setup_managed_config", {})
    for table_key, subkeys in managed.get("table_subkeys", {}).items():
        setup_table = setup_doc.get(table_key)
        for subkey in subkeys:
            label = f"{table_key}.{subkey}"
            if setup_table and subkey in setup_table:
                project_table = ensure_toml_table(project_doc, table_key)
                value = deepcopy_toml_item(setup_table[subkey])
                if subkey not in project_table or normalize_toml_value(project_table[subkey]) != normalize_toml_value(value):
                    project_table[subkey] = value
                    synced.append(label)
            elif remove_table_subkey(project_doc, table_key, subkey):
                synced.append(f"{label}:removed")
    return synced


def sync_setup_managed_mcp_servers(project_doc: Any, setup_doc: Any) -> list[str]:
    synced: list[str] = []
    managed = MANIFEST.get("setup_managed_config", {})
    prefixes = tuple(managed.get("mcp_server_prefixes", []))
    if not prefixes:
        return synced
    setup_servers = setup_doc.get("mcp_servers")
    setup_managed_keys = {
        str(key) for key in (setup_servers.keys() if setup_servers else []) if str(key).startswith(prefixes)
    }
    project_servers = project_doc.get("mcp_servers")
    project_managed_keys = {
        str(key) for key in (project_servers.keys() if project_servers else []) if str(key).startswith(prefixes)
    }

    if setup_managed_keys:
        project_servers = ensure_toml_table(project_doc, "mcp_servers")
        for key in sorted(setup_managed_keys):
            value = deepcopy_toml_item(setup_servers[key])
            if key not in project_servers or normalize_toml_value(project_servers[key]) != normalize_toml_value(value):
                project_servers[key] = value
                synced.append(f"mcp_servers.{key}")

    for key in sorted(project_managed_keys - setup_managed_keys):
        if remove_table_subkey(project_doc, "mcp_servers", key):
            synced.append(f"mcp_servers.{key}:removed")
    return synced


def merge_setup_managed_project_config(seed_content: str, setup_output_content: str) -> dict[str, Any]:
    project_doc = tomlkit.parse(seed_content)
    setup_doc = tomlkit.parse(setup_output_content)
    managed_keys = sync_setup_managed_root_keys(project_doc, setup_doc)
    managed_tables = sync_setup_managed_table_subkeys(project_doc, setup_doc)
    managed_tables.extend(sync_setup_managed_mcp_servers(project_doc, setup_doc))
    return {
        "content": tomlkit.dumps(project_doc),
        "managed_keys_synced": managed_keys,
        "managed_tables_synced": managed_tables,
    }


def reconcile_project_config(target: Path) -> dict[str, Any]:
    result = empty_config_reconcile_result()
    user_config = Path.home() / ".codex" / "config.toml"
    project_config = project_config_path(target)
    if not user_config.exists():
        return result
    result["user_config_present"] = True
    if not project_config.exists():
        return result
    result["project_config_present"] = True
    user_doc = load_toml(user_config)
    project_doc = load_toml(project_config)
    changed = False
    inheritance = MANIFEST["config_inheritance"]
    for key in inheritance["root_keys"]:
        if key in user_doc:
            value = deepcopy_toml_item(user_doc[key])
            if key not in project_doc or normalize_toml_value(project_doc[key]) != normalize_toml_value(value):
                project_doc[key] = value
                changed = True
                result["keys_synced"].append(key)
    for key in inheritance.get("remove_if_absent_root_keys", []):
        if key not in user_doc and key in project_doc:
            del project_doc[key]
            changed = True
            result["keys_synced"].append(f"{key}:removed")
    for table_key in inheritance["table_keys"]:
        if table_key in user_doc:
            value = deepcopy_toml_item(user_doc[table_key])
            if table_key not in project_doc or normalize_toml_value(project_doc[table_key]) != normalize_toml_value(value):
                project_doc[table_key] = value
                changed = True
                result["tables_synced"].append(table_key)
    removed_legacy_tables = prune_legacy_project_config_tables(project_doc)
    if removed_legacy_tables:
        changed = True
        result["tables_synced"].extend(removed_legacy_tables)
    if changed:
        write_toml(project_config, project_doc)
        result["applied"] = True
    return result


def inspect_project_config_inheritance(target: Path) -> dict[str, Any]:
    result = {
        "in_sync": True,
        "user_config_present": False,
        "project_config_present": False,
        "drifted_keys": [],
        "drifted_tables": [],
    }
    user_config = Path.home() / ".codex" / "config.toml"
    project_config = project_config_path(target)
    if not user_config.exists():
        return result
    result["user_config_present"] = True
    if not project_config.exists():
        result["in_sync"] = False
        return result
    result["project_config_present"] = True
    user_doc = load_toml(user_config)
    project_doc = load_toml(project_config)
    inheritance = MANIFEST["config_inheritance"]
    for key in inheritance["root_keys"]:
        if key in user_doc:
            if key not in project_doc or normalize_toml_value(project_doc[key]) != normalize_toml_value(user_doc[key]):
                result["in_sync"] = False
                result["drifted_keys"].append(key)
    for key in inheritance.get("remove_if_absent_root_keys", []):
        if key not in user_doc and key in project_doc:
            result["in_sync"] = False
            result["drifted_keys"].append(f"{key}:should-be-absent")
    for table_key in inheritance["table_keys"]:
        if table_key in user_doc:
            if table_key not in project_doc or normalize_toml_value(project_doc[table_key]) != normalize_toml_value(user_doc[table_key]):
                result["in_sync"] = False
                result["drifted_tables"].append(table_key)
    for path in LEGACY_PROJECT_CONFIG_TABLE_PATHS:
        if has_config_table_path(project_doc, path):
            result["in_sync"] = False
            result["drifted_tables"].append(f"{config_table_path_label(path)}:legacy")
    return result


def skill_wrapper_content(alias: str, target_prompt: str, description: str) -> str:
    title = alias.replace("-", " ").title()
    return (
        f"---\n"
        f"name: {alias}\n"
        f"description: {description}\n"
        f"---\n\n"
        f"# {title}\n\n"
        f"This compatibility alias exists for repositories whose guidance still refers to `${alias}`.\n\n"
        f"Route the work to `./.codex/prompts/{target_prompt}.md` when that prompt exists, or to the equivalent canonical role/prompt in the current repository contract.\n"
    )


def path_exists_or_link(path: Path) -> bool:
    return path.exists() or path.is_symlink()


def repair_legacy_skill_aliases(target: Path) -> dict[str, Any]:
    skills_dir = target / ".codex" / "skills"
    skills_dir.mkdir(parents=True, exist_ok=True)
    repaired: list[str] = []
    skipped: list[str] = []
    for alias, spec in MANIFEST.get("legacy_skill_aliases", {}).items():
        alias_path = skills_dir / alias
        if path_exists_or_link(alias_path):
            if alias_path.is_symlink() or alias_path.is_file():
                alias_path.unlink()
            elif alias_path.is_dir():
                shutil.rmtree(alias_path)
        if spec["kind"] == "symlink":
            target_skill = skills_dir / spec["target_skill"]
            if not target_skill.exists():
                skipped.append(alias)
                continue
            alias_path.symlink_to(spec["target_skill"])
            repaired.append(alias)
            continue
        if spec["kind"] == "wrapper":
            alias_path.mkdir(parents=True, exist_ok=True)
            write_text(
                alias_path / "SKILL.md",
                skill_wrapper_content(alias, spec["target_prompt"], spec["description"]),
            )
            repaired.append(alias)
            continue
        skipped.append(alias)
    return {"repaired": repaired, "skipped": skipped}


def inspect_legacy_skill_aliases(target: Path) -> dict[str, Any]:
    skills_dir = target / ".codex" / "skills"
    status = {"in_sync": True, "missing": [], "broken": []}
    if not skills_dir.exists():
        status["in_sync"] = False
        status["missing"] = sorted(MANIFEST.get("legacy_skill_aliases", {}).keys())
        return status
    for alias, spec in MANIFEST.get("legacy_skill_aliases", {}).items():
        alias_path = skills_dir / alias
        if spec["kind"] == "symlink":
            if not alias_path.is_symlink():
                status["in_sync"] = False
                status["missing"].append(alias)
                continue
            try:
                resolved = alias_path.resolve(strict=True)
            except FileNotFoundError:
                status["in_sync"] = False
                status["broken"].append(alias)
                continue
            expected = (skills_dir / spec["target_skill"]).resolve(strict=False)
            if resolved != expected:
                status["in_sync"] = False
                status["broken"].append(alias)
            continue
        if spec["kind"] == "wrapper":
            if not (alias_path / "SKILL.md").exists():
                status["in_sync"] = False
                status["missing"].append(alias)
    return status



def available_program_packs() -> dict[str, Any]:
    return MANIFEST.get("program_packs", {})


def resolve_program_pack(raw: str | None) -> str | None:
    if raw is None or raw == "":
        return None
    if raw not in available_program_packs():
        raise ValueError(f"Unknown program pack: {raw}")
    return raw


def program_pack_choices() -> list[str]:
    return sorted(available_program_packs().keys())


def program_pack_spec(program_pack: str | None) -> dict[str, Any] | None:
    if not program_pack:
        return None
    return available_program_packs().get(program_pack)


def render_replacements(target: Path, contract_path: Path, display_name: str) -> dict[str, str]:
    rel_contract_path = contract_path.relative_to(target).as_posix()
    repo_name = target.name
    repo_id = repo_slug(repo_name)
    program_id = f"{repo_id}-mainline"
    report_dir = f".omx/reports/{program_id}"
    return {
        "PROJECT_CONTRACT_PATH": rel_contract_path,
        "DISPLAY_NAME": display_name,
        "TARGET_PATH": str(target),
        "REPO_NAME": repo_name,
        "REPO_ID": repo_id,
        "PROGRAM_ID": program_id,
        "REPORT_DIR": report_dir,
        "CURRENT_PROGRAM_PATH": f"{target}/.omx/context/CURRENT_PROGRAM.md",
        "PROGRAM_ROUTING_PATH": f"{target}/.omx/context/PROGRAM_ROUTING.md",
        "TEAM_PROMPT_PATH": f"{target}/.omx/context/OMX_TEAM_PROMPT.md",
        "PROGRAM_SPEC_PATH": f"{target}/.omx/plans/spec-program-operating-model.md",
        "PROGRAM_PRD_PATH": f"{target}/.omx/plans/prd-{program_id}.md",
        "PROGRAM_TEST_SPEC_PATH": f"{target}/.omx/plans/test-spec-{program_id}.md",
        "PROGRAM_IMPLEMENTATION_PATH": f"{target}/.omx/plans/implementation-{program_id}.md",
        "PROGRAM_REPORT_README_PATH": f"{target}/.omx/reports/{program_id}/README.md",
        "PROGRAM_REPORT_STATUS_PATH": f"{target}/.omx/reports/{program_id}/LATEST_STATUS.md",
        "PROGRAM_REPORT_LOG_PATH": f"{target}/.omx/reports/{program_id}/ITERATION_LOG.md",
        "PROGRAM_REPORT_ISSUES_PATH": f"{target}/.omx/reports/{program_id}/OPEN_ISSUES.md",
        "INSTALLED_PROGRAM_PACK_ID": "none",
        "INSTALLED_PROGRAM_PACK_DESCRIPTION": "No optional program pack installed.",
        "INSTALLED_PROGRAM_PACK_DOCS": "- none",
        "PACK_TITLE": "",
        "PACK_PROGRAM_ID": "",
        "PACK_MAINLINE_ID": "",
        "PACK_PHASE": "",
        "PACK_ACTIVE_SUBLINE": "",
    }


def render_program_pack_docs(target: Path, program_pack: str | None) -> str:
    spec = program_pack_spec(program_pack)
    if not spec:
        return "- none"
    return "\n".join(f"- `{target / rel_path}`" for rel_path in spec["files"])


def pack_replacements(
    target: Path,
    contract_path: Path,
    display_name: str,
    program_pack: str | None,
) -> dict[str, str]:
    replacements = render_replacements(target, contract_path, display_name)
    spec = program_pack_spec(program_pack)
    if not spec:
        return replacements
    replacements["INSTALLED_PROGRAM_PACK_ID"] = program_pack or "none"
    replacements["INSTALLED_PROGRAM_PACK_DESCRIPTION"] = spec.get("description", "")
    replacements["INSTALLED_PROGRAM_PACK_DOCS"] = render_program_pack_docs(target, program_pack)
    for key, value in spec.get("replacements", {}).items():
        replacements[key] = value
    return replacements


def continuous_program_scaffold_paths(target: Path) -> dict[str, Path]:
    repo_id = repo_slug(target.name)
    program_id = f"{repo_id}-mainline"
    report_root = target / ".omx" / "reports" / program_id
    return {
        "current_program": target / ".omx" / "context" / "CURRENT_PROGRAM.md",
        "program_routing": target / ".omx" / "context" / "PROGRAM_ROUTING.md",
        "team_prompt": target / ".omx" / "context" / "OMX_TEAM_PROMPT.md",
        "operating_model_spec": target / ".omx" / "plans" / "spec-program-operating-model.md",
        "mainline_prd": target / ".omx" / "plans" / f"prd-{program_id}.md",
        "mainline_test_spec": target / ".omx" / "plans" / f"test-spec-{program_id}.md",
        "mainline_implementation": target / ".omx" / "plans" / f"implementation-{program_id}.md",
        "report_readme": report_root / "README.md",
        "report_latest_status": report_root / "LATEST_STATUS.md",
        "report_iteration_log": report_root / "ITERATION_LOG.md",
        "report_open_issues": report_root / "OPEN_ISSUES.md",
    }


def empty_program_pack_result(program_pack: str | None = None) -> dict[str, Any]:
    spec = program_pack_spec(program_pack)
    return {
        "id": program_pack or "",
        "description": spec.get("description", "") if spec else "",
        "created": [],
        "preserved": [],
    }


def apply_continuous_program_scaffold(
    target: Path,
    display_name: str,
    contract_path: Path,
    program_pack: str | None,
) -> dict[str, Any]:
    replacements = pack_replacements(target, contract_path, display_name, program_pack)
    scaffold_paths = continuous_program_scaffold_paths(target)
    if inspect_continuous_program_scaffold(target)["in_sync"]:
        return {
            "enabled_by_default": bool(MANIFEST.get("continuous_program_scaffold", {}).get("enabled_by_default", False)),
            "program_id": replacements["PROGRAM_ID"],
            "report_dir": replacements["REPORT_DIR"],
            "created": [],
            "preserved": ["existing-custom-scaffold"],
        }
    template_map = {
        "current_program": "program_current_context",
        "program_routing": "program_routing_context",
        "team_prompt": "program_team_prompt",
        "operating_model_spec": "program_operating_model_spec",
        "mainline_prd": "program_mainline_prd",
        "mainline_test_spec": "program_mainline_test_spec",
        "mainline_implementation": "program_mainline_implementation",
        "report_readme": "program_report_readme",
        "report_latest_status": "program_report_latest_status",
        "report_iteration_log": "program_report_iteration_log",
        "report_open_issues": "program_report_open_issues",
    }
    created: list[str] = []
    preserved: list[str] = []
    for key, template_key in template_map.items():
        path = scaffold_paths[key]
        if path.exists():
            preserved.append(path.relative_to(target).as_posix())
            continue
        write_text(path, render_template(template_path(template_key), replacements))
        created.append(path.relative_to(target).as_posix())
    return {
        "enabled_by_default": bool(MANIFEST.get("continuous_program_scaffold", {}).get("enabled_by_default", False)),
        "program_id": replacements["PROGRAM_ID"],
        "report_dir": replacements["REPORT_DIR"],
        "created": created,
        "preserved": preserved,
    }


def inspect_continuous_program_scaffold(target: Path) -> dict[str, Any]:
    missing: list[str] = []
    required_exact = {
        "current_program": target / ".omx" / "context" / "CURRENT_PROGRAM.md",
        "program_routing": target / ".omx" / "context" / "PROGRAM_ROUTING.md",
        "team_prompt": target / ".omx" / "context" / "OMX_TEAM_PROMPT.md",
    }
    for path in required_exact.values():
        if not path.exists():
            missing.append(path.relative_to(target).as_posix())

    plan_patterns = {
        "spec": ".omx/plans/spec-*.md",
        "prd": ".omx/plans/prd-*.md",
        "test_spec": ".omx/plans/test-spec-*.md",
        "implementation": ".omx/plans/implementation-*.md",
    }
    for pattern in plan_patterns.values():
        if not any(target.glob(pattern)):
            missing.append(pattern)

    report_roots = sorted(target.glob(".omx/reports/*-mainline"))
    if not report_roots:
        missing.append(".omx/reports/*-mainline/")
    else:
        required_report_files = ["README.md", "LATEST_STATUS.md", "ITERATION_LOG.md", "OPEN_ISSUES.md"]
        if not any(all((root / name).exists() for name in required_report_files) for root in report_roots):
            missing.append(".omx/reports/*-mainline/{README,LATEST_STATUS,ITERATION_LOG,OPEN_ISSUES}.md")
    return {
        "in_sync": not missing,
        "missing": missing,
    }


def apply_program_pack(
    target: Path,
    display_name: str,
    contract_path: Path,
    program_pack: str | None,
) -> dict[str, Any]:
    result = empty_program_pack_result(program_pack)
    spec = program_pack_spec(program_pack)
    if not spec:
        return result
    replacements = pack_replacements(target, contract_path, display_name, program_pack)
    for rel_path, template_rel in spec["files"].items():
        destination = target / rel_path
        if destination.exists():
            result["preserved"].append(rel_path)
            continue
        write_text(destination, render_template(BASELINE_ROOT / template_rel, replacements))
        result["created"].append(rel_path)
    return result


def inspect_program_pack(target: Path, program_pack: str | None) -> dict[str, Any]:
    spec = program_pack_spec(program_pack)
    if not spec:
        return {"in_sync": True, "missing": []}
    missing = [rel_path for rel_path in spec["files"] if not (target / rel_path).exists()]
    return {"in_sync": not missing, "missing": missing}


def parse_contract_path_from_root(root_path: Path) -> Path | None:
    if not root_path.exists():
        return None
    content = read_text(root_path)
    for pattern in [
        r"lives at `([^`]+/AGENTS\.md)`",
        r"truth source(?:\.| lives at)? `([^`]+/AGENTS\.md)`",
        r"`(contracts/[^`]+/AGENTS\.md)`",
    ]:
        match = re.search(pattern, content)
        if match:
            candidate = Path(match.group(1))
            return candidate if candidate.is_absolute() else (root_path.parent / candidate)
    return None


def resolve_root_agents_policy(raw: str | None) -> str | None:
    if raw in ROOT_AGENTS_POLICIES:
        return raw
    return None


def resolve_project_config_policy(raw: str | None) -> str | None:
    if raw in PROJECT_CONFIG_POLICIES:
        return raw
    return None


def select_root_agents_content(
    target: Path,
    rendered_root: str,
    metadata: dict[str, Any] | None,
    policy: str,
    pre_setup_root_content: str | None,
) -> tuple[str, str]:
    current_path = target / "AGENTS.md"
    current_content = read_text(current_path) if current_path.exists() else None
    backup_content = latest_setup_backup_text(target, "AGENTS.md")

    if policy == "template":
        return rendered_root, "template"

    if policy == "preserve":
        if pre_setup_root_content is not None:
            return pre_setup_root_content, "pre-setup-snapshot"
        if backup_content is not None:
            return backup_content, "latest-setup-backup"
        if current_content is not None:
            return current_content, "current"
        return rendered_root, "template-missing"

    if metadata is None:
        return rendered_root, "first-install-template"
    if pre_setup_root_content is not None:
        return pre_setup_root_content, "pre-setup-snapshot"
    if current_content is not None and is_full_omx_root_contract(current_content):
        if backup_content is not None and not is_full_omx_root_contract(backup_content):
            return backup_content, "latest-setup-backup"
        return rendered_root, "restore-app-template"
    if current_content is not None:
        return current_content, "preserve-current"
    if backup_content is not None:
        return backup_content, "latest-setup-backup"
    return rendered_root, "template-missing"


def apply_project_config_update(
    target: Path,
    metadata: dict[str, Any] | None,
    policy: str,
    pre_setup_project_config: str | None,
    setup_ran: bool,
) -> dict[str, Any]:
    result = empty_config_reconcile_result()
    managed_keys_synced: list[str] = []
    managed_tables_synced: list[str] = []
    project_config = project_config_path(target)
    backup_content = latest_setup_backup_text(target, ".codex/config.toml")
    setup_output_content = read_text(project_config) if project_config.exists() else None
    seed_content: str | None = None
    seed_source = ""

    if policy == "preserve":
        seed_content = pre_setup_project_config or backup_content
        seed_source = "pre-setup-snapshot" if pre_setup_project_config is not None else ("latest-setup-backup" if backup_content is not None else "")
    elif policy == "setup-output":
        seed_source = "setup-output"
    else:
        seed_content = pre_setup_project_config
        seed_source = "pre-setup-snapshot" if pre_setup_project_config is not None else ""
        if seed_content is None and metadata is not None and backup_content is not None:
            seed_content = backup_content
            seed_source = "latest-setup-backup"

    if policy == "auto" and setup_ran and seed_content is not None and setup_output_content is not None:
        merged = merge_setup_managed_project_config(seed_content, setup_output_content)
        seed_content = merged["content"]
        managed_keys_synced = merged["managed_keys_synced"]
        managed_tables_synced = merged["managed_tables_synced"]

    restored = False
    if seed_content is not None:
        current = read_text(project_config) if project_config.exists() else None
        if current != seed_content:
            write_text(project_config, seed_content)
            restored = True

    if policy == "setup-output":
        result["project_config_present"] = project_config.exists()
        result["restore_applied"] = restored
        result["restore_source"] = seed_source
        result["policy"] = policy
        return result

    result = reconcile_project_config(target)
    result["managed_keys_synced"] = managed_keys_synced
    result["managed_tables_synced"] = managed_tables_synced
    result["restore_applied"] = restored
    result["restore_source"] = seed_source
    result["policy"] = policy
    return result


def discover_legacy_contract_source(target: Path, metadata: dict[str, Any] | None, destination: Path) -> Path | None:
    candidates: list[Path] = []
    if metadata and metadata.get("project_contract_path"):
        candidates.append(resolve_contract_path(target, metadata.get("project_contract_path")))
    parsed = parse_contract_path_from_root(target / "AGENTS.md")
    if parsed:
        candidates.append(parsed)
    for pattern in MANIFEST.get("legacy_project_contract_path_patterns", []):
        for raw in sorted(glob.glob(str(target / pattern))):
            candidates.append(Path(raw))
    seen: set[Path] = set()
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        if candidate == destination:
            continue
        if candidate.exists():
            return candidate
    return None


def migrate_project_truth_contract(
    target: Path,
    destination: Path,
    metadata: dict[str, Any] | None,
) -> dict[str, Any]:
    result = {
        "migrated": False,
        "source_path": "",
        "removed_legacy_source": False,
    }
    if destination.exists():
        return result
    source = discover_legacy_contract_source(target, metadata, destination)
    if not source:
        return result
    write_text(destination, read_text(source))
    result["migrated"] = True
    result["source_path"] = str(source)
    if metadata:
        managed = set(metadata.get("managed_files") or [])
        rel_source = source.relative_to(target).as_posix() if source.is_relative_to(target) else ""
        if rel_source and rel_source in managed:
            backup_file(source, target)
            source.unlink()
            result["removed_legacy_source"] = True
    return result


def cleanup_legacy_paths(target: Path) -> dict[str, Any]:
    removed: list[str] = []
    for rel in MANIFEST.get("legacy_cleanup_paths", []):
        path = target / rel
        if path.exists() or path.is_symlink():
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()
            removed.append(rel)
            parent = path.parent
            while parent != target and parent.exists():
                try:
                    parent.rmdir()
                except OSError:
                    break
                parent = parent.parent
    return {"removed": removed}


def apply_root_and_contracts(
    target: Path,
    contract_path: Path,
    display_name: str,
    force_contract: bool = False,
    metadata: dict[str, Any] | None = None,
    root_agents_policy: str = "auto",
    pre_setup_root_content: str | None = None,
) -> dict[str, Any]:
    replacements = render_replacements(target, contract_path, display_name)
    rendered_root = render_template(template_path("root_agents"), replacements)
    root_content, root_source = select_root_agents_content(
        target=target,
        rendered_root=rendered_root,
        metadata=metadata,
        policy=root_agents_policy,
        pre_setup_root_content=pre_setup_root_content,
    )
    root_path = target / "AGENTS.md"
    root_written = not root_path.exists() or read_text(root_path) != root_content
    if root_written:
        write_text(root_path, root_content)
    write_text(omx_agents_path(target), render_template(template_path("omx_project_agents"), replacements))
    host_adapter_template_map = {
        "readme": "dev_host_readme",
        "omx_cli": "dev_host_omx_cli",
        "codex_app": "dev_host_codex_app",
    }
    host_adapters_written: list[str] = []
    for key, path in dev_host_contract_paths(target).items():
        rendered = render_template(template_path(host_adapter_template_map[key]), replacements)
        if not path.exists() or read_text(path) != rendered:
            write_text(path, rendered)
            host_adapters_written.append(path.relative_to(target).as_posix())
    if force_contract or not contract_path.exists():
        write_text(contract_path, render_template(template_path("project_truth_contract"), replacements))
        project_contract_written = True
    else:
        project_contract_written = False
    return {
        "project_contract_written": project_contract_written,
        "root_agents_policy": root_agents_policy,
        "root_agents_source": root_source,
        "root_agents_written": root_written,
        "root_agents_sha256": sha256_text(root_content),
        "host_adapters_written": host_adapters_written,
    }


def apply_readme_section(target: Path, contract_path: Path) -> bool:
    return False


def run_omx_setup(target: Path, scope: str, force: bool, verbose: bool, omx_bin: str) -> None:
    cmd = [omx_bin, "setup", "--scope", scope]
    if force:
        cmd.append("--force")
    if verbose:
        cmd.append("--verbose")
    subprocess.run(cmd, cwd=target, check=True)


def preserve_existing_root_agents(target: Path, contract_path: Path) -> dict[str, Any]:
    root_agents = target / "AGENTS.md"
    result = {
        "backed_up": False,
        "backup_path": "",
        "adopted_to_contract": False,
    }
    if not root_agents.exists():
        return result
    if metadata_path(target).exists():
        return result
    backup = backup_file(root_agents, target)
    result["backed_up"] = True
    result["backup_path"] = str(backup)
    if not contract_path.exists():
        contract_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(root_agents, contract_path)
        result["adopted_to_contract"] = True
    return result


def managed_files(target: Path, contract_path: Path) -> list[str]:
    return [
        "AGENTS.md",
        ".gitignore",
        contract_path.relative_to(target).as_posix(),
        omx_agents_path(target).relative_to(target).as_posix(),
        *(path.relative_to(target).as_posix() for path in dev_host_contract_paths(target).values()),
    ]


def write_metadata(target: Path, scope: str, contract_path: Path, display_name: str, extra: dict[str, Any]) -> None:
    payload = {
        "baseline_name": MANIFEST["baseline_name"],
        "baseline_version": MANIFEST["baseline_version"],
        "contract_layout": "single-project-truth",
        "scope": scope,
        "display_name": display_name,
        "project_truth_path": contract_path.relative_to(target).as_posix(),
        "managed_files": managed_files(target, contract_path),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    legacy_mode = extra.pop("legacy_mode", None)
    legacy_project_contract_path = extra.pop("legacy_project_contract_path", None)
    if legacy_mode:
        payload["legacy_mode"] = legacy_mode
    if legacy_project_contract_path:
        payload["legacy_project_contract_path"] = legacy_project_contract_path
    payload.update(extra)
    write_text(metadata_path(target), json.dumps(payload, indent=2, ensure_ascii=False) + "\n")


def load_metadata(target: Path) -> dict[str, Any]:
    path = metadata_path(target)
    if not path.exists():
        raise SystemExit(f"Missing baseline metadata: {path}")
    return json.loads(read_text(path))


def resolve_legacy_mode(raw: str | None) -> str | None:
    if raw in {"runtime-service", "project-native"}:
        return raw
    return None


def metadata_program_pack(metadata: dict[str, Any] | None) -> str | None:
    if not metadata:
        return None
    program_pack = metadata.get("program_pack")
    if isinstance(program_pack, dict):
        return resolve_program_pack(program_pack.get("id"))
    if isinstance(program_pack, str):
        return resolve_program_pack(program_pack)
    return None


def install_or_refresh(
    target: Path,
    scope: str,
    contract_path: Path,
    display_name: str,
    run_setup: bool,
    force_setup: bool,
    verbose: bool,
    omx_bin: str,
    legacy_mode: str | None = None,
    program_pack: str | None = None,
    root_agents_policy: str | None = None,
    project_config_policy: str | None = None,
) -> dict[str, Any]:
    metadata = json.loads(read_text(metadata_path(target))) if metadata_path(target).exists() else None
    resolved_program_pack = resolve_program_pack(program_pack) if program_pack is not None else metadata_program_pack(metadata)
    stored_root_agents_policy = resolve_root_agents_policy((metadata or {}).get("update_policies", {}).get("root_agents"))
    if stored_root_agents_policy == "auto":
        stored_root_agents_policy = None
    stored_project_config_policy = resolve_project_config_policy((metadata or {}).get("update_policies", {}).get("project_config"))
    if stored_project_config_policy == "auto":
        stored_project_config_policy = None
    resolved_root_agents_policy = (
        resolve_root_agents_policy(root_agents_policy)
        or stored_root_agents_policy
        or resolve_root_agents_policy(MANIFEST.get("controlled_update", {}).get("root_agents_policy"))
        or "auto"
    )
    resolved_project_config_policy = (
        resolve_project_config_policy(project_config_policy)
        or stored_project_config_policy
        or resolve_project_config_policy(MANIFEST.get("controlled_update", {}).get("project_config_policy"))
        or "auto"
    )
    preserved = preserve_existing_root_agents(target, contract_path)
    pre_setup_root_content = read_text(target / "AGENTS.md") if run_setup and (target / "AGENTS.md").exists() else None
    pre_setup_project_config = (
        read_text(project_config_path(target))
        if run_setup and project_config_path(target).exists()
        else None
    )
    if run_setup:
        run_omx_setup(target, scope, force_setup, verbose, omx_bin)
    migration = migrate_project_truth_contract(target, contract_path, metadata)
    cleanup = cleanup_legacy_paths(target)
    ensured_ignore = ensure_gitignore_entries(target / ".gitignore", MANIFEST["gitignore_entries"])
    applied = apply_root_and_contracts(
        target,
        contract_path,
        display_name,
        metadata=metadata,
        root_agents_policy=resolved_root_agents_policy,
        pre_setup_root_content=pre_setup_root_content,
    )
    config_result = empty_config_reconcile_result()
    alias_result = {"repaired": [], "skipped": []}
    scaffold_result = {"enabled_by_default": False, "program_id": "", "report_dir": "", "created": [], "preserved": []}
    program_pack_result = empty_program_pack_result(resolved_program_pack)
    if scope == "project":
        config_result = apply_project_config_update(
            target=target,
            metadata=metadata,
            policy=resolved_project_config_policy,
            pre_setup_project_config=pre_setup_project_config,
            setup_ran=run_setup,
        )
        alias_result = repair_legacy_skill_aliases(target)
        if MANIFEST.get("continuous_program_scaffold", {}).get("enabled_by_default", False):
            scaffold_result = apply_continuous_program_scaffold(target, display_name, contract_path, resolved_program_pack)
        program_pack_result = apply_program_pack(target, display_name, contract_path, resolved_program_pack)
    compatibility_audit = inspect_compatibility_audit(target)
    write_metadata(
        target,
        scope,
        contract_path,
        display_name,
        {
            "legacy_mode": legacy_mode,
            "legacy_project_contract_path": metadata.get("project_contract_path") if metadata else None,
            "preserved_existing_root": preserved,
            "project_truth_migration": migration,
            "legacy_cleanup": cleanup,
            "gitignore_updated": ensured_ignore,
            "update_policies": {
                "root_agents": resolved_root_agents_policy,
                "project_config": resolved_project_config_policy,
            },
            "root_agents_state": {
                "policy": applied["root_agents_policy"],
                "source": applied["root_agents_source"],
                "sha256": applied["root_agents_sha256"],
            },
            "config_reconcile": config_result,
            "legacy_alias_repair": alias_result,
            "continuous_program_scaffold": scaffold_result,
            "program_pack": program_pack_result,
            "compatibility_audit": compatibility_audit,
        },
    )
    return {
        "target": str(target),
        "contract_layout": "single-project-truth",
        "scope": scope,
        "project_truth_path": str(contract_path),
        "omx_agents_path": str(omx_agents_path(target)),
        "preserved_existing_root": preserved,
        "project_truth_migration": migration,
        "legacy_cleanup": cleanup,
        "gitignore_updated": ensured_ignore,
        "project_contract_written": applied["project_contract_written"],
        "update_policies": {
            "root_agents": resolved_root_agents_policy,
            "project_config": resolved_project_config_policy,
        },
        "root_agents_state": {
            "policy": applied["root_agents_policy"],
            "source": applied["root_agents_source"],
            "sha256": applied["root_agents_sha256"],
        },
        "config_reconcile": config_result,
        "legacy_alias_repair": alias_result,
        "continuous_program_scaffold": scaffold_result,
        "program_pack": program_pack_result,
        "compatibility_audit": compatibility_audit,
    }


def expected_root(target: Path, contract_path: Path, display_name: str) -> str:
    return render_template(template_path("root_agents"), render_replacements(target, contract_path, display_name))


def expected_omx_agents(target: Path, contract_path: Path, display_name: str) -> str:
    return render_template(template_path("omx_project_agents"), render_replacements(target, contract_path, display_name))


def diff_target(target: Path, scope: str, contract_path: Path, display_name: str) -> int:
    issues = 0
    checks: list[str] = []
    metadata = json.loads(read_text(metadata_path(target))) if metadata_path(target).exists() else None
    configured_program_pack = metadata_program_pack(metadata)
    root_path = target / "AGENTS.md"
    expected = expected_root(target, contract_path, display_name)
    if not root_path.exists():
        checks.append("AGENTS.md: missing")
        issues += 1
    else:
        current_root = read_text(root_path)
        root_state = metadata.get("root_agents_state") if metadata else None
        if root_state and root_state.get("sha256") == sha256_text(current_root):
            checks.append(f"AGENTS.md: ok ({root_state.get('source', 'managed')})")
        elif current_root == expected:
            checks.append("AGENTS.md: ok")
        else:
            checks.append("AGENTS.md: drift")
            issues += 1
    omx_path = omx_agents_path(target)
    omx_expected = expected_omx_agents(target, contract_path, display_name)
    if not omx_path.exists():
        checks.append(".codex/AGENTS.md: missing")
        issues += 1
    elif read_text(omx_path) != omx_expected:
        checks.append(".codex/AGENTS.md: drift")
        issues += 1
    else:
        checks.append(".codex/AGENTS.md: ok")
    checks.append("README public surface: unmanaged by baseline")
    gitignore_path = target / ".gitignore"
    missing_entries = [entry for entry in MANIFEST["gitignore_entries"] if not gitignore_path.exists() or entry not in read_text(gitignore_path).splitlines()]
    if missing_entries:
        checks.append(f".gitignore entries: missing {', '.join(missing_entries)}")
        issues += 1
    else:
        checks.append(".gitignore entries: ok")
    if scope == "project":
        cfg = inspect_project_config_inheritance(target)
        if cfg["user_config_present"] and cfg["project_config_present"] and cfg["in_sync"]:
            checks.append("project config inheritance: ok")
        elif cfg["user_config_present"] and cfg["project_config_present"] and not cfg["in_sync"]:
            drift_bits = cfg["drifted_keys"] + cfg["drifted_tables"]
            checks.append(f"project config inheritance: drift ({', '.join(drift_bits)})")
            issues += 1
        else:
            checks.append("project config inheritance: skipped")
        aliases = inspect_legacy_skill_aliases(target)
        if aliases["in_sync"]:
            checks.append("legacy skill aliases: ok")
        else:
            detail = aliases["missing"] + aliases["broken"]
            checks.append(f"legacy skill aliases: drift ({', '.join(detail)})")
            issues += 1
        if MANIFEST.get("continuous_program_scaffold", {}).get("enabled_by_default", False):
            scaffold = inspect_continuous_program_scaffold(target)
            if scaffold["in_sync"]:
                checks.append("continuous program scaffold: ok")
            else:
                checks.append(f"continuous program scaffold: missing ({', '.join(scaffold['missing'])})")
                issues += 1
        if configured_program_pack:
            pack = inspect_program_pack(target, configured_program_pack)
            if pack["in_sync"]:
                checks.append(f"program pack ({configured_program_pack}): ok")
            else:
                checks.append(f"program pack ({configured_program_pack}): missing ({', '.join(pack['missing'])})")
                issues += 1
    compatibility_audit = inspect_compatibility_audit(target)
    if compatibility_audit["static_contract"]["in_sync"]:
        checks.append("compatibility audit (static contract): ok")
    else:
        checks.append(
            "compatibility audit (static contract): drift "
            f"({', '.join(compatibility_audit['static_contract']['missing'])})"
        )
        issues += 1
    if compatibility_audit["runtime"]["in_sync"]:
        checks.append("compatibility audit (runtime): ok")
    else:
        checks.append(
            "compatibility audit (runtime): risk "
            f"({', '.join(compatibility_audit['runtime']['risks'])})"
        )
        issues += 1
    for line in checks:
        print(line)
    return 1 if issues else 0


def resolve_display_name(target: Path, raw: str | None) -> str:
    return raw.strip() if raw else display_name_from_repo(target.name)


def resolve_contract_path(target: Path, raw: str | None) -> Path:
    if not raw:
        return default_contract_path(target)
    candidate = Path(raw)
    return candidate if candidate.is_absolute() else (target / candidate)


def command_install(args: argparse.Namespace) -> int:
    target = Path(args.target).resolve()
    display_name = resolve_display_name(target, args.display_name)
    contract_path = resolve_contract_path(target, args.project_contract_path)
    result = install_or_refresh(
        target=target,
        scope=args.scope,
        contract_path=contract_path,
        display_name=display_name,
        run_setup=not args.skip_omx_setup,
        force_setup=args.force,
        verbose=args.verbose,
        omx_bin=args.omx_bin,
        legacy_mode=resolve_legacy_mode(args.mode),
        program_pack=args.program_pack,
        root_agents_policy=args.root_agents_policy,
        project_config_policy=args.project_config_policy,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


def command_diff(args: argparse.Namespace) -> int:
    target = Path(args.target).resolve()
    metadata = load_metadata(target) if metadata_path(target).exists() else {}
    scope = args.scope or metadata.get("scope", MANIFEST["default_scope"])
    contract_path = resolve_contract_path(target, args.project_contract_path or metadata.get("project_truth_path"))
    display_name = resolve_display_name(target, args.display_name or metadata.get("display_name"))
    return diff_target(target, scope, contract_path, display_name)


def command_upgrade(args: argparse.Namespace) -> int:
    target = Path(args.target).resolve()
    metadata = load_metadata(target)
    scope = args.scope or metadata.get("scope", MANIFEST["default_scope"])
    contract_path = resolve_contract_path(target, args.project_contract_path or metadata.get("project_truth_path"))
    display_name = resolve_display_name(target, args.display_name or metadata.get("display_name"))
    result = install_or_refresh(
        target=target,
        scope=scope,
        contract_path=contract_path,
        display_name=display_name,
        run_setup=args.run_omx_setup,
        force_setup=args.force,
        verbose=args.verbose,
        omx_bin=args.omx_bin,
        legacy_mode=resolve_legacy_mode(args.mode) or metadata.get("legacy_mode"),
        program_pack=args.program_pack if args.program_pack is not None else metadata_program_pack(metadata),
        root_agents_policy=args.root_agents_policy,
        project_config_policy=args.project_config_policy,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


def command_reconcile(args: argparse.Namespace) -> int:
    target = Path(args.target).resolve()
    metadata = load_metadata(target)
    scope = metadata.get("scope", MANIFEST["default_scope"])
    contract_path = resolve_contract_path(target, metadata.get("project_truth_path"))
    display_name = resolve_display_name(target, metadata.get("display_name"))
    result = install_or_refresh(
        target=target,
        scope=scope,
        contract_path=contract_path,
        display_name=display_name,
        run_setup=args.run_omx_setup,
        force_setup=args.force,
        verbose=args.verbose,
        omx_bin=args.omx_bin,
        legacy_mode=metadata.get("legacy_mode"),
        program_pack=args.program_pack if args.program_pack is not None else metadata_program_pack(metadata),
        root_agents_policy=args.root_agents_policy,
        project_config_policy=args.project_config_policy,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Install and reconcile OMX project contracts with baseline management.")
    sub = parser.add_subparsers(dest="command", required=True)

    def add_common(
        sp: argparse.ArgumentParser,
        include_contract: bool = True,
        scope_default: str | None = None,
    ) -> None:
        sp.add_argument("--target", required=True, help="Target repository root")
        sp.add_argument("--mode", choices=["runtime-service", "project-native"], help=argparse.SUPPRESS)
        if include_contract:
            sp.add_argument("--project-contract-path", help="Override project truth contract path (default: contracts/project-truth/AGENTS.md)")
        sp.add_argument("--display-name", help="Display name for contract stubs")
        sp.add_argument("--scope", default=scope_default, choices=["project", "user"], help="OMX setup scope")
        sp.add_argument("--omx-bin", default="omx", help="omx executable to use")
        sp.add_argument("--program-pack", choices=program_pack_choices(), help="Optional long-horizon program scaffold pack")
        sp.add_argument("--root-agents-policy", choices=ROOT_AGENTS_POLICIES, help="How to update the repository root AGENTS.md")
        sp.add_argument("--project-config-policy", choices=PROJECT_CONFIG_POLICIES, help="How to update project .codex/config.toml")
        sp.add_argument("--verbose", action="store_true")
        sp.add_argument("--force", action="store_true", help="Pass --force to omx setup when invoked")

    install = sub.add_parser("install")
    add_common(install, scope_default=MANIFEST["default_scope"])
    install.add_argument("--skip-omx-setup", action="store_true", help="Apply baseline without running omx setup")
    install.set_defaults(func=command_install)

    diff = sub.add_parser("diff")
    add_common(diff)
    diff.set_defaults(func=command_diff)

    upgrade = sub.add_parser("upgrade")
    add_common(upgrade)
    upgrade.add_argument("--run-omx-setup", action="store_true", help="Run omx setup again before applying upgraded baseline")
    upgrade.set_defaults(func=command_upgrade)

    reconcile = sub.add_parser("reconcile")
    add_common(reconcile, include_contract=False)
    reconcile.add_argument("--run-omx-setup", action="store_true", help="Run omx setup again before reconciling")
    reconcile.set_defaults(func=command_reconcile)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
