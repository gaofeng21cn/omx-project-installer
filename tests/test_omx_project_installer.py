import importlib.util
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


class ReadmeSectionTests(unittest.TestCase):
    def test_apply_readme_section_does_not_duplicate_heading_when_markers_exist(self):
        installer = load_module()
        with TemporaryDirectory() as tmpdir:
            target = Path(tmpdir)
            readme = target / "README.md"
            readme.write_text(
                "# Demo\n\n"
                "## Agent 合同分层\n\n"
                "<!-- AGENT-CONTRACT-BASELINE:START -->\n"
                "- old\n"
                "<!-- AGENT-CONTRACT-BASELINE:END -->\n",
                encoding="utf-8",
            )
            contract_path = target / "contracts" / "project-truth" / "AGENTS.md"
            contract_path.parent.mkdir(parents=True, exist_ok=True)
            contract_path.write_text("# truth\n", encoding="utf-8")

            installer.apply_readme_section(target, contract_path)

            content = readme.read_text(encoding="utf-8")
            self.assertEqual(content.count("## Agent 合同分层"), 1)


if __name__ == "__main__":
    unittest.main()
