import importlib.util
import io
import json
import sys
import tomllib
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import mock


MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "skills"
    / "omx-project-installer"
    / "scripts"
    / "omx_project_installer.py"
)


def load_module():
    spec = importlib.util.spec_from_file_location("omx_project_installer", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    import tomlkit  # noqa: F401

    spec.loader.exec_module(module)
    return module


class PreserveExistingRootAgentsTests(unittest.TestCase):
    def test_preserve_existing_root_agents_creates_contract_parent_dirs(self):
        installer = load_module()
        with TemporaryDirectory() as tmpdir:
            target = Path(tmpdir)
            root_agents = target / "AGENTS.md"
            root_agents.write_text("# existing root contract\n", encoding="utf-8")
            contract_path = target / "contracts" / "project-truth" / "AGENTS.md"

            try:
                result = installer.preserve_existing_root_agents(target, contract_path)
            except FileNotFoundError as exc:
                self.fail(f"expected installer to create contract parent dirs, got {exc}")

            self.assertTrue(result["backed_up"])
            self.assertTrue(result["adopted_to_contract"])
            self.assertTrue(contract_path.exists())
            self.assertEqual(
                contract_path.read_text(encoding="utf-8"),
                root_agents.read_text(encoding="utf-8"),
            )


class ContractLayerWriteTests(unittest.TestCase):
    def test_apply_root_and_contracts_writes_root_and_omx_layers(self):
        installer = load_module()
        with TemporaryDirectory() as tmpdir:
            target = Path(tmpdir)
            contract_path = target / "contracts" / "project-truth" / "AGENTS.md"

            result = installer.apply_root_and_contracts(target, contract_path, "Demo Project")

            self.assertTrue(result["project_contract_written"])
            self.assertTrue((target / "AGENTS.md").exists())
            self.assertTrue((target / ".codex" / "AGENTS.md").exists())
            self.assertTrue(contract_path.exists())

            root_content = (target / "AGENTS.md").read_text(encoding="utf-8")
            omx_content = (target / ".codex" / "AGENTS.md").read_text(encoding="utf-8")

            self.assertNotIn("oh-my-codex", root_content)
            self.assertIn("project truth contract lives at `contracts/project-truth/AGENTS.md`", root_content)
            self.assertIn("oh-my-codex", omx_content)
            self.assertIn("This file lives at `.codex/AGENTS.md`", omx_content)


class ConfigInheritanceTests(unittest.TestCase):
    def test_reconcile_project_config_removes_context_limits_missing_from_user_config(self):
        installer = load_module()
        with TemporaryDirectory() as home_tmpdir, TemporaryDirectory() as repo_tmpdir:
            home_root = Path(home_tmpdir)
            user_codex = home_root / ".codex"
            user_codex.mkdir(parents=True, exist_ok=True)
            (user_codex / "config.toml").write_text(
                'model_provider = "gflab"\n'
                'model = "gpt-5.4"\n'
                'model_reasoning_effort = "xhigh"\n'
                '\n'
                '[model_providers.gflab]\n'
                'base_url = "https://example.invalid/v1"\n',
                encoding="utf-8",
            )

            repo_root = Path(repo_tmpdir)
            project_codex = repo_root / ".codex"
            project_codex.mkdir(parents=True, exist_ok=True)
            project_config = project_codex / "config.toml"
            project_config.write_text(
                'model_provider = "gflab"\n'
                'model = "gpt-5.4"\n'
                'model_reasoning_effort = "high"\n'
                'model_context_window = 1000000\n'
                'model_auto_compact_token_limit = 900000\n'
                '\n'
                '[model_providers.gflab]\n'
                'base_url = "https://placeholder.invalid/v1"\n',
                encoding="utf-8",
            )

            with mock.patch.object(installer.Path, "home", return_value=home_root):
                result = installer.reconcile_project_config(repo_root)

            self.assertTrue(result["applied"])

            parsed = tomllib.loads(project_config.read_text(encoding="utf-8"))
            self.assertEqual(parsed["model_reasoning_effort"], "xhigh")
            self.assertNotIn("model_context_window", parsed)
            self.assertNotIn("model_auto_compact_token_limit", parsed)

    def test_install_or_refresh_restores_project_config_snapshot_after_upstream_setup(self):
        installer = load_module()
        with TemporaryDirectory() as home_tmpdir, TemporaryDirectory() as repo_tmpdir:
            home_root = Path(home_tmpdir)
            user_codex = home_root / ".codex"
            user_codex.mkdir(parents=True, exist_ok=True)
            (user_codex / "config.toml").write_text(
                'model_provider = "gflab"\n'
                'model = "gpt-5.4"\n'
                'model_reasoning_effort = "xhigh"\n'
                '\n'
                '[model_providers.gflab]\n'
                'base_url = "https://example.invalid/v1"\n',
                encoding="utf-8",
            )

            repo_root = Path(repo_tmpdir)
            contract_path = repo_root / "contracts" / "project-truth" / "AGENTS.md"
            contract_path.parent.mkdir(parents=True, exist_ok=True)
            contract_path.write_text("# truth\n", encoding="utf-8")
            project_codex = repo_root / ".codex"
            project_codex.mkdir(parents=True, exist_ok=True)
            project_config = project_codex / "config.toml"
            project_config.write_text(
                'model_provider = "gflab"\n'
                'model = "gpt-5.4-mini"\n'
                'model_reasoning_effort = "medium"\n'
                'custom_setting = "preserve-me"\n'
                '\n'
                '[model_providers.gflab]\n'
                'base_url = "https://placeholder.invalid/v1"\n'
                '\n'
                '[mcp_servers.custom]\n'
                'command = "custom"\n',
                encoding="utf-8",
            )

            def fake_run_setup(target: Path, scope: str, force: bool, verbose: bool, omx_bin: str) -> None:
                self.assertEqual(scope, "project")
                (target / "AGENTS.md").write_text("upstream overwrite\n", encoding="utf-8")
                project_config.write_text(
                    'model_provider = "gflab"\n'
                    'model = "gpt-5.4"\n'
                    'model_reasoning_effort = "high"\n'
                    'model_context_window = 1000000\n'
                    'model_auto_compact_token_limit = 900000\n',
                    encoding="utf-8",
                )

            with mock.patch.dict("os.environ", {"HOME": str(home_root)}):
                with mock.patch.object(installer.Path, "home", return_value=home_root):
                    with mock.patch.object(installer, "run_omx_setup", side_effect=fake_run_setup):
                        result = installer.install_or_refresh(
                            target=repo_root,
                            scope="project",
                            contract_path=contract_path,
                            display_name="Demo",
                            run_setup=True,
                            force_setup=False,
                            verbose=False,
                            omx_bin="omx",
                        )

            parsed = tomllib.loads(project_config.read_text(encoding="utf-8"))
            self.assertEqual(parsed["custom_setting"], "preserve-me")
            self.assertEqual(parsed["model_reasoning_effort"], "xhigh")
            self.assertNotIn("model_context_window", parsed)
            self.assertNotIn("model_auto_compact_token_limit", parsed)
            self.assertIn("custom", parsed["mcp_servers"])
            self.assertEqual(result["update_policies"]["root_agents"], "auto")
            self.assertEqual(result["update_policies"]["project_config"], "auto")
            self.assertTrue(result["config_reconcile"]["restore_applied"])
            self.assertEqual(result["config_reconcile"]["restore_source"], "pre-setup-snapshot")
            self.assertNotEqual(
                (repo_root / "AGENTS.md").read_text(encoding="utf-8"),
                "upstream overwrite\n",
            )

    def test_install_or_refresh_recovers_root_and_config_from_latest_setup_backup_without_rerunning_setup(self):
        installer = load_module()
        with TemporaryDirectory() as home_tmpdir, TemporaryDirectory() as repo_tmpdir:
            home_root = Path(home_tmpdir)
            user_codex = home_root / ".codex"
            user_codex.mkdir(parents=True, exist_ok=True)
            (user_codex / "config.toml").write_text(
                'model_provider = "gflab"\n'
                'model = "gpt-5.4"\n'
                'model_reasoning_effort = "xhigh"\n'
                '\n'
                '[model_providers.gflab]\n'
                'base_url = "https://example.invalid/v1"\n',
                encoding="utf-8",
            )

            repo_root = Path(repo_tmpdir)
            (repo_root / ".agent-contract-baseline.json").write_text(
                json.dumps(
                    {
                        "scope": "project",
                        "display_name": "Demo",
                        "project_truth_path": "contracts/project-truth/AGENTS.md",
                        "update_policies": {"root_agents": "auto", "project_config": "auto"},
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            contract_path = repo_root / "contracts" / "project-truth" / "AGENTS.md"
            contract_path.parent.mkdir(parents=True, exist_ok=True)
            contract_path.write_text("# truth\n", encoding="utf-8")
            (repo_root / "AGENTS.md").write_text(
                "<!-- omx:generated:agents-md -->\n"
                "# oh-my-codex - Intelligent Multi-Agent Orchestration\n"
                "This AGENTS.md is the top-level operating contract for the workspace.\n",
                encoding="utf-8",
            )
            project_codex = repo_root / ".codex"
            project_codex.mkdir(parents=True, exist_ok=True)
            project_config = project_codex / "config.toml"
            project_config.write_text(
                'notify = ["node", "/tmp/overwrite.js"]\n'
                'model_provider = "gflab"\n'
                'model = "gpt-5.4"\n'
                'model_reasoning_effort = "high"\n'
                'model_context_window = 1000000\n'
                '\n'
                '[model_providers.gflab]\n'
                'base_url = "https://overwrite.invalid/v1"\n',
                encoding="utf-8",
            )
            backup_root = repo_root / ".omx" / "backups" / "setup" / "2026-04-07T00-00-00.000Z"
            (backup_root / ".codex").mkdir(parents=True, exist_ok=True)
            (backup_root / "AGENTS.md").write_text("# preserved root contract\n", encoding="utf-8")
            (backup_root / ".codex" / "config.toml").write_text(
                'notify = ["bash", "-c", "node \\"$(npm root -g)/oh-my-codex/dist/scripts/notify-hook.js\\" \\"$1\\"", "notify-hook"]\n'
                'model_provider = "gflab"\n'
                'model = "gpt-5.4"\n'
                'model_reasoning_effort = "high"\n'
                'model_context_window = 1000000\n'
                '\n'
                '[model_providers.gflab]\n'
                'base_url = "https://backup.invalid/v1"\n',
                encoding="utf-8",
            )

            with mock.patch.dict("os.environ", {"HOME": str(home_root)}):
                with mock.patch.object(installer.Path, "home", return_value=home_root):
                    result = installer.install_or_refresh(
                        target=repo_root,
                        scope="project",
                        contract_path=contract_path,
                        display_name="Demo",
                        run_setup=False,
                        force_setup=False,
                        verbose=False,
                        omx_bin="omx",
                    )

            parsed = tomllib.loads(project_config.read_text(encoding="utf-8"))
            self.assertEqual((repo_root / "AGENTS.md").read_text(encoding="utf-8"), "# preserved root contract\n")
            self.assertEqual(result["root_agents_state"]["source"], "latest-setup-backup")
            self.assertEqual(parsed["notify"][0], "bash")
            self.assertEqual(parsed["model_reasoning_effort"], "xhigh")
            self.assertEqual(parsed["model_providers"]["gflab"]["base_url"], "https://example.invalid/v1")
            self.assertNotIn("model_context_window", parsed)

    def test_reconcile_project_config_removes_legacy_omx_team_run_table(self):
        installer = load_module()
        with TemporaryDirectory() as home_tmpdir, TemporaryDirectory() as repo_tmpdir:
            home_root = Path(home_tmpdir)
            user_codex = home_root / ".codex"
            user_codex.mkdir(parents=True, exist_ok=True)
            (user_codex / "config.toml").write_text(
                'model_provider = "gflab"\n'
                'model = "gpt-5.4"\n'
                'model_reasoning_effort = "xhigh"\n'
                '\n'
                '[model_providers.gflab]\n'
                'base_url = "https://example.invalid/v1"\n',
                encoding="utf-8",
            )

            repo_root = Path(repo_tmpdir)
            project_codex = repo_root / ".codex"
            project_codex.mkdir(parents=True, exist_ok=True)
            project_config = project_codex / "config.toml"
            project_config.write_text(
                'model_provider = "gflab"\n'
                'model = "gpt-5.4"\n'
                'model_reasoning_effort = "high"\n'
                '\n'
                '[model_providers.gflab]\n'
                'base_url = "https://placeholder.invalid/v1"\n'
                '\n'
                '[mcp_servers.omx_state]\n'
                'command = "node"\n'
                'args = ["/tmp/state-server.js"]\n'
                '\n'
                '[mcp_servers.omx_team_run]\n'
                'command = "node"\n'
                'args = ["/tmp/team-server.js"]\n',
                encoding="utf-8",
            )

            with mock.patch.object(installer.Path, "home", return_value=home_root):
                result = installer.reconcile_project_config(repo_root)

            self.assertTrue(result["applied"])

            parsed = tomllib.loads(project_config.read_text(encoding="utf-8"))
            self.assertIn("mcp_servers", parsed)
            self.assertIn("omx_state", parsed["mcp_servers"])
            self.assertNotIn("omx_team_run", parsed["mcp_servers"])

    def test_inspect_project_config_inheritance_flags_legacy_omx_team_run_table(self):
        installer = load_module()
        with TemporaryDirectory() as home_tmpdir, TemporaryDirectory() as repo_tmpdir:
            home_root = Path(home_tmpdir)
            user_codex = home_root / ".codex"
            user_codex.mkdir(parents=True, exist_ok=True)
            (user_codex / "config.toml").write_text(
                'model_provider = "gflab"\n'
                'model = "gpt-5.4"\n'
                'model_reasoning_effort = "xhigh"\n'
                '\n'
                '[model_providers.gflab]\n'
                'base_url = "https://example.invalid/v1"\n',
                encoding="utf-8",
            )

            repo_root = Path(repo_tmpdir)
            project_codex = repo_root / ".codex"
            project_codex.mkdir(parents=True, exist_ok=True)
            (project_codex / "config.toml").write_text(
                'model_provider = "gflab"\n'
                'model = "gpt-5.4"\n'
                'model_reasoning_effort = "xhigh"\n'
                '\n'
                '[model_providers.gflab]\n'
                'base_url = "https://example.invalid/v1"\n'
                '\n'
                '[mcp_servers.omx_team_run]\n'
                'command = "node"\n'
                'args = ["/tmp/team-server.js"]\n',
                encoding="utf-8",
            )

            with mock.patch.object(installer.Path, "home", return_value=home_root):
                result = installer.inspect_project_config_inheritance(repo_root)

            self.assertFalse(result["in_sync"])
            self.assertIn("mcp_servers.omx_team_run:legacy", result["drifted_tables"])


class ReadmeSectionTests(unittest.TestCase):
    def test_apply_readme_section_leaves_public_readme_untouched(self):
        installer = load_module()
        with TemporaryDirectory() as tmpdir:
            target = Path(tmpdir)
            readme = target / "README.md"
            original = "# Demo\n\nPublic README stays human-owned.\n"
            readme.write_text(original, encoding="utf-8")
            contract_path = target / "contracts" / "project-truth" / "AGENTS.md"
            contract_path.parent.mkdir(parents=True, exist_ok=True)
            contract_path.write_text("# truth\n", encoding="utf-8")

            changed = installer.apply_readme_section(target, contract_path)

            self.assertFalse(changed)
            self.assertEqual(readme.read_text(encoding="utf-8"), original)

    def test_diff_target_does_not_require_managed_readme_section(self):
        installer = load_module()
        with TemporaryDirectory() as tmpdir:
            target = Path(tmpdir)
            readme = target / "README.md"
            readme.write_text("# Demo\n\nHuman-facing public docs.\n", encoding="utf-8")
            (target / ".gitignore").write_text(".omx/\n.codex/\n", encoding="utf-8")
            contract_path = target / "contracts" / "project-truth" / "AGENTS.md"

            installer.apply_root_and_contracts(target, contract_path, "Demo Project")
            changed = installer.apply_readme_section(target, contract_path)
            result = installer.diff_target(target, "user", contract_path, "Demo Project")

            self.assertFalse(changed)
            self.assertEqual(result, 0)


class MetadataSurfaceTests(unittest.TestCase):
    def test_managed_files_excludes_public_readme(self):
        installer = load_module()
        with TemporaryDirectory() as tmpdir:
            target = Path(tmpdir)
            contract_path = target / "contracts" / "project-truth" / "AGENTS.md"
            contract_path.parent.mkdir(parents=True, exist_ok=True)
            contract_path.write_text("# truth\n", encoding="utf-8")

            managed = installer.managed_files(target, contract_path)

            self.assertNotIn("README.md", managed)


class LegacyCleanupTests(unittest.TestCase):
    def test_reconcile_removes_legacy_dev_hosts_files(self):
        installer = load_module()
        with TemporaryDirectory() as home_tmpdir, TemporaryDirectory() as repo_tmpdir:
            home_root = Path(home_tmpdir)
            user_codex = home_root / ".codex"
            user_codex.mkdir(parents=True, exist_ok=True)
            (user_codex / "config.toml").write_text(
                'model_provider = "gflab"\n'
                'model = "gpt-5.4"\n'
                'model_reasoning_effort = "xhigh"\n'
                '\n'
                '[model_providers.gflab]\n'
                'base_url = "https://example.invalid/v1"\n',
                encoding="utf-8",
            )

            repo_root = Path(repo_tmpdir)
            (repo_root / "README.md").write_text("# Demo\n", encoding="utf-8")
            (repo_root / "contracts" / "project-truth").mkdir(parents=True, exist_ok=True)
            (repo_root / "contracts" / "project-truth" / "AGENTS.md").write_text("# truth\n", encoding="utf-8")
            legacy_dir = repo_root / "contracts" / "dev-hosts"
            legacy_dir.mkdir(parents=True, exist_ok=True)
            (legacy_dir / "README.md").write_text("old\n", encoding="utf-8")
            (legacy_dir / "omx-cli.md").write_text("old\n", encoding="utf-8")
            (legacy_dir / "codex-app.md").write_text("old\n", encoding="utf-8")

            project_codex = repo_root / ".codex"
            project_codex.mkdir(parents=True, exist_ok=True)
            (project_codex / "config.toml").write_text(
                'model_provider = "gflab"\n'
                'model = "gpt-5.4"\n'
                'model_reasoning_effort = "high"\n'
                '\n'
                '[model_providers.gflab]\n'
                'base_url = "https://placeholder.invalid/v1"\n',
                encoding="utf-8",
            )
            (project_codex / "skills" / "ralph").mkdir(parents=True, exist_ok=True)
            (project_codex / "skills" / "team").mkdir(parents=True, exist_ok=True)
            (project_codex / "skills" / "ultrawork").mkdir(parents=True, exist_ok=True)

            with mock.patch.object(installer.Path, "home", return_value=home_root):
                installer.install_or_refresh(
                    target=repo_root,
                    scope="project",
                    contract_path=repo_root / "contracts" / "project-truth" / "AGENTS.md",
                    display_name="Demo",
                    run_setup=False,
                    force_setup=False,
                    verbose=False,
                    omx_bin="omx",
                )

            self.assertFalse((legacy_dir / "README.md").exists())
            self.assertFalse((legacy_dir / "omx-cli.md").exists())
            self.assertFalse((legacy_dir / "codex-app.md").exists())

    def test_install_or_refresh_repairs_legacy_project_skill_aliases(self):
        installer = load_module()
        with TemporaryDirectory() as home_tmpdir, TemporaryDirectory() as repo_tmpdir:
            home_root = Path(home_tmpdir)
            user_codex = home_root / ".codex"
            user_codex.mkdir(parents=True, exist_ok=True)
            (user_codex / "config.toml").write_text(
                'model_provider = "gflab"\n'
                'model = "gpt-5.4"\n'
                'model_reasoning_effort = "xhigh"\n'
                '\n'
                '[model_providers.gflab]\n'
                'base_url = "https://example.invalid/v1"\n',
                encoding="utf-8",
            )

            repo_root = Path(repo_tmpdir)
            (repo_root / "contracts" / "project-truth").mkdir(parents=True, exist_ok=True)
            (repo_root / "contracts" / "project-truth" / "AGENTS.md").write_text("# truth\n", encoding="utf-8")
            project_codex = repo_root / ".codex"
            project_codex.mkdir(parents=True, exist_ok=True)
            (project_codex / "config.toml").write_text(
                'model_provider = "gflab"\n'
                'model = "gpt-5.4"\n'
                'model_reasoning_effort = "high"\n'
                '\n'
                '[model_providers.gflab]\n'
                'base_url = "https://placeholder.invalid/v1"\n',
                encoding="utf-8",
            )
            skills_dir = project_codex / "skills"
            for canonical in ("ralph", "team", "ultrawork"):
                (skills_dir / canonical).mkdir(parents=True, exist_ok=True)
                (skills_dir / canonical / "SKILL.md").write_text(f"# {canonical}\n", encoding="utf-8")

            with mock.patch.object(installer.Path, "home", return_value=home_root):
                result = installer.install_or_refresh(
                    target=repo_root,
                    scope="project",
                    contract_path=repo_root / "contracts" / "project-truth" / "AGENTS.md",
                    display_name="Demo",
                    run_setup=False,
                    force_setup=False,
                    verbose=False,
                    omx_bin="omx",
                )

            self.assertTrue((skills_dir / "analyze" / "SKILL.md").exists())
            self.assertTrue((skills_dir / "build-fix" / "SKILL.md").exists())
            self.assertTrue((skills_dir / "tdd" / "SKILL.md").exists())
            self.assertTrue((skills_dir / "ecomode").is_symlink())
            self.assertTrue((skills_dir / "ultraqa").is_symlink())
            self.assertTrue((skills_dir / "swarm").is_symlink())
            self.assertEqual(
                sorted(result["legacy_alias_repair"]["repaired"]),
                ["analyze", "build-fix", "ecomode", "swarm", "tdd", "ultraqa"],
            )


class ProgramRoutingAndPackTests(unittest.TestCase):
    def _seed_project(self, repo_root: Path) -> None:
        (repo_root / "README.md").write_text("# Demo Project\n", encoding="utf-8")
        (repo_root / "contracts" / "project-truth").mkdir(parents=True, exist_ok=True)
        (repo_root / "contracts" / "project-truth" / "AGENTS.md").write_text("# truth\n", encoding="utf-8")
        project_codex = repo_root / ".codex"
        project_codex.mkdir(parents=True, exist_ok=True)
        (project_codex / "config.toml").write_text(
            'model_provider = "gflab"\n'
            'model = "gpt-5.4"\n'
            'model_reasoning_effort = "high"\n'
            "\n"
            "[model_providers.gflab]\n"
            'base_url = "https://example.invalid/v1"\n',
            encoding="utf-8",
        )

    def _seed_user_home(self, home_root: Path) -> None:
        user_codex = home_root / ".codex"
        user_codex.mkdir(parents=True, exist_ok=True)
        (user_codex / "config.toml").write_text(
            'model_provider = "gflab"\n'
            'model = "gpt-5.4"\n'
            'model_reasoning_effort = "high"\n'
            "\n"
            "[model_providers.gflab]\n"
            'base_url = "https://example.invalid/v1"\n',
            encoding="utf-8",
        )

    def test_install_creates_program_routing_surface(self):
        installer = load_module()
        with TemporaryDirectory() as home_tmpdir, TemporaryDirectory() as repo_tmpdir:
            home_root = Path(home_tmpdir)
            repo_root = Path(repo_tmpdir) / "demo-project"
            repo_root.mkdir(parents=True, exist_ok=True)
            self._seed_user_home(home_root)
            self._seed_project(repo_root)

            with mock.patch.object(installer.Path, "home", return_value=home_root):
                installer.install_or_refresh(
                    target=repo_root,
                    scope="project",
                    contract_path=repo_root / "contracts" / "project-truth" / "AGENTS.md",
                    display_name="Demo Project",
                    run_setup=False,
                    force_setup=False,
                    verbose=False,
                    omx_bin="omx",
                )

            routing = repo_root / ".omx" / "context" / "PROGRAM_ROUTING.md"
            self.assertTrue(routing.exists())
            content = routing.read_text(encoding="utf-8")
            self.assertIn("CURRENT_PROGRAM.md", content)
            self.assertIn("roadmap-", content)

    def test_diff_target_requires_program_routing_surface(self):
        installer = load_module()
        with TemporaryDirectory() as home_tmpdir, TemporaryDirectory() as repo_tmpdir:
            home_root = Path(home_tmpdir)
            repo_root = Path(repo_tmpdir) / "demo-project"
            repo_root.mkdir(parents=True, exist_ok=True)
            self._seed_user_home(home_root)
            self._seed_project(repo_root)

            (repo_root / ".gitignore").write_text(".omx/\n.codex/\n", encoding="utf-8")
            installer.apply_root_and_contracts(
                repo_root,
                repo_root / "contracts" / "project-truth" / "AGENTS.md",
                "Demo Project",
            )
            (repo_root / ".omx" / "context").mkdir(parents=True, exist_ok=True)
            (repo_root / ".omx" / "plans").mkdir(parents=True, exist_ok=True)
            (repo_root / ".omx" / "reports" / "demo-project-mainline").mkdir(parents=True, exist_ok=True)
            (repo_root / ".omx" / "context" / "CURRENT_PROGRAM.md").write_text("# current\n", encoding="utf-8")
            (repo_root / ".omx" / "context" / "OMX_TEAM_PROMPT.md").write_text("# team\n", encoding="utf-8")
            (repo_root / ".omx" / "plans" / "spec-program-operating-model.md").write_text("# spec\n", encoding="utf-8")
            (repo_root / ".omx" / "plans" / "prd-demo-project-mainline.md").write_text("# prd\n", encoding="utf-8")
            (repo_root / ".omx" / "plans" / "test-spec-demo-project-mainline.md").write_text("# test-spec\n", encoding="utf-8")
            (repo_root / ".omx" / "plans" / "implementation-demo-project-mainline.md").write_text("# impl\n", encoding="utf-8")
            (repo_root / ".omx" / "reports" / "demo-project-mainline" / "README.md").write_text("# report\n", encoding="utf-8")
            (repo_root / ".omx" / "reports" / "demo-project-mainline" / "LATEST_STATUS.md").write_text("# status\n", encoding="utf-8")
            (repo_root / ".omx" / "reports" / "demo-project-mainline" / "ITERATION_LOG.md").write_text("# log\n", encoding="utf-8")
            (repo_root / ".omx" / "reports" / "demo-project-mainline" / "OPEN_ISSUES.md").write_text("# issues\n", encoding="utf-8")

            with mock.patch.object(installer.Path, "home", return_value=home_root):
                with mock.patch("sys.stdout", new_callable=io.StringIO) as stdout:
                    result = installer.diff_target(
                        repo_root,
                        "project",
                        repo_root / "contracts" / "project-truth" / "AGENTS.md",
                        "Demo Project",
                    )

            self.assertEqual(result, 1)
            self.assertIn("continuous program scaffold", stdout.getvalue())
            self.assertIn("PROGRAM_ROUTING", stdout.getvalue())

    def test_install_with_program_pack_creates_pack_documents_and_metadata(self):
        installer = load_module()
        with TemporaryDirectory() as home_tmpdir, TemporaryDirectory() as repo_tmpdir:
            home_root = Path(home_tmpdir)
            repo_root = Path(repo_tmpdir) / "med-autoscience"
            repo_root.mkdir(parents=True, exist_ok=True)
            self._seed_user_home(home_root)
            self._seed_project(repo_root)

            with mock.patch.object(installer.Path, "home", return_value=home_root):
                installer.install_or_refresh(
                    target=repo_root,
                    scope="project",
                    contract_path=repo_root / "contracts" / "project-truth" / "AGENTS.md",
                    display_name="Med Auto Science",
                    run_setup=False,
                    force_setup=False,
                    verbose=False,
                    omx_bin="omx",
                    program_pack="medical_research_foundry_delivery_closeout",
                )

            self.assertTrue(
                (
                    repo_root
                    / ".omx"
                    / "context"
                    / "LONG_HORIZON_RESEARCH_FOUNDRY_MEDICAL_PROGRAM.md"
                ).exists()
            )
            self.assertTrue(
                (
                    repo_root
                    / ".omx"
                    / "context"
                    / "OMX_RESEARCH_FOUNDRY_MEDICAL_DELIVERY_PLANE_CLOSEOUT_PROGRAM_PROMPT.md"
                ).exists()
            )
            self.assertTrue(
                (
                    repo_root
                    / ".omx"
                    / "plans"
                    / "roadmap-research-foundry-medical-delivery-plane-closeout-program.md"
                ).exists()
            )
            metadata = json.loads((repo_root / ".agent-contract-baseline.json").read_text(encoding="utf-8"))
            self.assertEqual(metadata["program_pack"]["id"], "medical_research_foundry_delivery_closeout")

    def test_install_with_program_pack_preserves_existing_pack_files(self):
        installer = load_module()
        with TemporaryDirectory() as home_tmpdir, TemporaryDirectory() as repo_tmpdir:
            home_root = Path(home_tmpdir)
            repo_root = Path(repo_tmpdir) / "med-autoscience"
            repo_root.mkdir(parents=True, exist_ok=True)
            self._seed_user_home(home_root)
            self._seed_project(repo_root)
            existing = (
                repo_root
                / ".omx"
                / "context"
                / "LONG_HORIZON_RESEARCH_FOUNDRY_MEDICAL_PROGRAM.md"
            )
            existing.parent.mkdir(parents=True, exist_ok=True)
            existing.write_text("# custom long horizon\n", encoding="utf-8")

            with mock.patch.object(installer.Path, "home", return_value=home_root):
                result = installer.install_or_refresh(
                    target=repo_root,
                    scope="project",
                    contract_path=repo_root / "contracts" / "project-truth" / "AGENTS.md",
                    display_name="Med Auto Science",
                    run_setup=False,
                    force_setup=False,
                    verbose=False,
                    omx_bin="omx",
                    program_pack="medical_research_foundry_delivery_closeout",
                )

            self.assertEqual(existing.read_text(encoding="utf-8"), "# custom long horizon\n")
            self.assertIn(
                ".omx/context/LONG_HORIZON_RESEARCH_FOUNDRY_MEDICAL_PROGRAM.md",
                result["program_pack"]["preserved"],
            )


if __name__ == "__main__":
    unittest.main()
