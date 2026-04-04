#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import glob
import json
import re
import shutil
import subprocess
import sys
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


def render_replacements(target: Path, contract_path: Path, display_name: str) -> dict[str, str]:
    rel_contract_path = contract_path.relative_to(target).as_posix()
    return {
        "PROJECT_CONTRACT_PATH": rel_contract_path,
        "DISPLAY_NAME": display_name,
    }


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


def apply_root_and_contracts(
    target: Path,
    contract_path: Path,
    display_name: str,
    force_contract: bool = False,
) -> dict[str, Any]:
    replacements = render_replacements(target, contract_path, display_name)
    write_text(target / "AGENTS.md", render_template(template_path("root_agents"), replacements))
    write_text(
        target / "contracts" / "dev-hosts" / "README.md",
        render_template(template_path("dev_hosts_readme"), replacements),
    )
    write_text(
        target / "contracts" / "dev-hosts" / "omx-cli.md",
        render_template(template_path("dev_hosts_omx_cli"), replacements),
    )
    write_text(
        target / "contracts" / "dev-hosts" / "codex-app.md",
        render_template(template_path("dev_hosts_codex_app"), replacements),
    )
    if force_contract or not contract_path.exists():
        write_text(contract_path, render_template(template_path("project_truth_contract"), replacements))
        return {"project_contract_written": True}
    return {"project_contract_written": False}


def apply_readme_section(target: Path, contract_path: Path) -> bool:
    readme_path = target / "README.md"
    if not readme_path.exists():
        return False
    replacements = {"PROJECT_CONTRACT_PATH": contract_path.relative_to(target).as_posix()}
    rendered = render_template(template_path("readme_section"), replacements)
    markers = MANIFEST["readme_markers"]
    updated = upsert_marked_section(read_text(readme_path), rendered, markers["start"], markers["end"])
    if updated != read_text(readme_path):
        write_text(readme_path, updated)
        return True
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
        shutil.copy2(root_agents, contract_path)
        result["adopted_to_contract"] = True
    return result


def managed_files(target: Path, contract_path: Path) -> list[str]:
    return [
        "AGENTS.md",
        "README.md",
        ".gitignore",
        "contracts/dev-hosts/README.md",
        "contracts/dev-hosts/omx-cli.md",
        "contracts/dev-hosts/codex-app.md",
        contract_path.relative_to(target).as_posix(),
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
) -> dict[str, Any]:
    metadata = json.loads(read_text(metadata_path(target))) if metadata_path(target).exists() else None
    preserved = preserve_existing_root_agents(target, contract_path)
    if run_setup:
        run_omx_setup(target, scope, force_setup, verbose, omx_bin)
    migration = migrate_project_truth_contract(target, contract_path, metadata)
    ensured_ignore = ensure_gitignore_entries(target / ".gitignore", MANIFEST["gitignore_entries"])
    applied = apply_root_and_contracts(target, contract_path, display_name)
    readme_updated = apply_readme_section(target, contract_path)
    config_result = {"applied": False}
    alias_result = {"repaired": [], "skipped": []}
    if scope == "project":
        config_result = reconcile_project_config(target)
        alias_result = repair_legacy_skill_aliases(target)
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
            "gitignore_updated": ensured_ignore,
            "readme_updated": readme_updated,
            "config_reconcile": config_result,
            "legacy_alias_repair": alias_result,
        },
    )
    return {
        "target": str(target),
        "contract_layout": "single-project-truth",
        "scope": scope,
        "project_truth_path": str(contract_path),
        "preserved_existing_root": preserved,
        "project_truth_migration": migration,
        "gitignore_updated": ensured_ignore,
        "readme_updated": readme_updated,
        "project_contract_written": applied["project_contract_written"],
        "config_reconcile": config_result,
        "legacy_alias_repair": alias_result,
    }


def expected_root(target: Path, contract_path: Path, display_name: str) -> str:
    return render_template(template_path("root_agents"), render_replacements(target, contract_path, display_name))


def expected_readme_section(target: Path, contract_path: Path) -> str:
    rendered = render_template(
        template_path("readme_section"),
        {"PROJECT_CONTRACT_PATH": contract_path.relative_to(target).as_posix()},
    ).strip()
    markers = MANIFEST["readme_markers"]
    pattern = re.compile(re.escape(markers["start"]) + r".*?" + re.escape(markers["end"]), re.DOTALL)
    match = pattern.search(rendered)
    return match.group(0).strip() if match else rendered


def diff_target(target: Path, scope: str, contract_path: Path, display_name: str) -> int:
    issues = 0
    checks: list[str] = []
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
    for rel, template_key in [
        ("contracts/dev-hosts/README.md", "dev_hosts_readme"),
        ("contracts/dev-hosts/omx-cli.md", "dev_hosts_omx_cli"),
        ("contracts/dev-hosts/codex-app.md", "dev_hosts_codex_app"),
    ]:
        path = target / rel
        rendered = render_template(template_path(template_key), render_replacements(target, contract_path, display_name))
        if not path.exists():
            checks.append(f"{rel}: missing")
            issues += 1
        elif read_text(path) != rendered:
            checks.append(f"{rel}: drift")
            issues += 1
        else:
            checks.append(f"{rel}: ok")
    readme_path = target / "README.md"
    if readme_path.exists():
        content = read_text(readme_path)
        markers = MANIFEST["readme_markers"]
        pattern = re.compile(re.escape(markers["start"]) + r".*?" + re.escape(markers["end"]), re.DOTALL)
        match = pattern.search(content)
        if not match:
            checks.append("README managed section: missing")
            issues += 1
        elif match.group(0).strip() != expected_readme_section(target, contract_path):
            checks.append("README managed section: drift")
            issues += 1
        else:
            checks.append("README managed section: ok")
    else:
        checks.append("README managed section: skipped (README missing)")
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
