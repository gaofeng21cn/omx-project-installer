#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import glob
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


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


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


def reconcile_project_config(target: Path) -> dict[str, Any]:
    result = {
        "applied": False,
        "user_config_present": False,
        "project_config_present": False,
        "keys_synced": [],
        "tables_synced": [],
    }
    user_config = Path.home() / ".codex" / "config.toml"
    project_config = target / ".codex" / "config.toml"
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
    project_config = target / ".codex" / "config.toml"
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
    for alias, spec in MANIFEST["legacy_skill_aliases"].items():
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
        status["missing"] = sorted(MANIFEST["legacy_skill_aliases"].keys())
        return status
    for alias, spec in MANIFEST["legacy_skill_aliases"].items():
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
            skill_file = alias_path / "SKILL.md"
            if not skill_file.exists():
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
) -> dict[str, Any]:
    replacements = render_replacements(target, contract_path, display_name)
    write_text(target / "AGENTS.md", render_template(template_path("root_agents"), replacements))
    write_text(omx_agents_path(target), render_template(template_path("omx_project_agents"), replacements))
    if force_contract or not contract_path.exists():
        write_text(contract_path, render_template(template_path("project_truth_contract"), replacements))
        return {"project_contract_written": True}
    return {"project_contract_written": False}


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
) -> dict[str, Any]:
    metadata = json.loads(read_text(metadata_path(target))) if metadata_path(target).exists() else None
    resolved_program_pack = resolve_program_pack(program_pack) if program_pack is not None else metadata_program_pack(metadata)
    preserved = preserve_existing_root_agents(target, contract_path)
    if run_setup:
        run_omx_setup(target, scope, force_setup, verbose, omx_bin)
    migration = migrate_project_truth_contract(target, contract_path, metadata)
    cleanup = cleanup_legacy_paths(target)
    ensured_ignore = ensure_gitignore_entries(target / ".gitignore", MANIFEST["gitignore_entries"])
    applied = apply_root_and_contracts(target, contract_path, display_name)
    config_result = {"applied": False}
    alias_result = {"repaired": [], "skipped": []}
    scaffold_result = {"enabled_by_default": False, "program_id": "", "report_dir": "", "created": [], "preserved": []}
    program_pack_result = empty_program_pack_result(resolved_program_pack)
    if scope == "project":
        config_result = reconcile_project_config(target)
        alias_result = repair_legacy_skill_aliases(target)
        if MANIFEST.get("continuous_program_scaffold", {}).get("enabled_by_default", False):
            scaffold_result = apply_continuous_program_scaffold(target, display_name, contract_path, resolved_program_pack)
        program_pack_result = apply_program_pack(target, display_name, contract_path, resolved_program_pack)
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
            "config_reconcile": config_result,
            "legacy_alias_repair": alias_result,
            "continuous_program_scaffold": scaffold_result,
            "program_pack": program_pack_result,
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
        "config_reconcile": config_result,
        "legacy_alias_repair": alias_result,
        "continuous_program_scaffold": scaffold_result,
        "program_pack": program_pack_result,
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
    elif read_text(root_path) != expected:
        checks.append("AGENTS.md: drift")
        issues += 1
    else:
        checks.append("AGENTS.md: ok")
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
