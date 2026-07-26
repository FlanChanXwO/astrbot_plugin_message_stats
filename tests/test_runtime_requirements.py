"""运行时依赖声明的回归测试。"""

import unittest
from pathlib import Path


REQUIREMENTS_PATH = Path(__file__).parents[1] / "requirements.txt"
VALIDATORS_PATH = Path(__file__).parents[1] / "utils" / "validators.py"


class RuntimeRequirementsTests(unittest.TestCase):
    """防止实际导入的安全依赖再次遗漏出插件清单。"""

    def test_bleach_is_declared_for_html_sanitization(self):
        requirements = REQUIREMENTS_PATH.read_text(encoding="utf-8")

        self.assertIn("bleach>=6.0.0", requirements)

    def test_html_sanitizer_requires_declared_bleach(self):
        validators = VALIDATORS_PATH.read_text(encoding="utf-8")

        self.assertIn("import bleach", validators)
        self.assertNotIn("bleach = None", validators)
