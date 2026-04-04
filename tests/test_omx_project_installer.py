import importlib.util
import sys
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
    tomlkit_stub = SimpleNamespace(parse=lambda content: content, dumps=lambda doc: str(doc))
    with mock.patch.dict(sys.modules, {"tomlkit": tomlkit_stub}):
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


if __name__ == "__main__":
    unittest.main()
