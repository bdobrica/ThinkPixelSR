"""Documentation gates must inspect repository docs, not installed dependencies."""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from config import ConfigError
from verify import documentation_links


class DocumentationTests(unittest.TestCase):
    def fixture(self, directory):
        repo = Path(directory)
        subprocess.run(["git", "init", "-q", str(repo)], check=True)
        (repo / "clients/php/vendor").mkdir(parents=True)
        (repo / ".gitignore").write_text("clients/php/vendor/\n")
        (repo / "README.md").write_text("[SDK](clients/php/README.md)\n")
        (repo / "clients/php/README.md").write_text("SDK\n")
        (repo / "clients/php/vendor/README.md").write_text("[Upstream](missing.md)\n")
        return repo

    def test_ignored_dependency_docs_are_excluded(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(documentation_links(self.fixture(directory)), 1)

    def test_nonignored_sdk_links_are_still_checked(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = self.fixture(directory)
            (repo / "clients/php/README.md").write_text("[Missing](missing.md)\n")
            with self.assertRaisesRegex(ConfigError, "broken relative"):
                documentation_links(repo)
