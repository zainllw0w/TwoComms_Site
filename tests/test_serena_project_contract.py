from pathlib import Path
import unittest


PROJECT_CONFIG = Path(__file__).parents[1] / ".serena" / "project.yml"


class SerenaProjectContractTests(unittest.TestCase):
    def test_uses_current_languages_schema(self):
        config = PROJECT_CONFIG.read_text(encoding="utf-8")

        self.assertRegex(
            config,
            r"(?m)^languages:\s*$\n- python\s*$\n- typescript\s*$",
        )
        self.assertNotRegex(config, r"(?m)^language_servers\s*:")


if __name__ == "__main__":
    unittest.main()
