"""运行时依赖声明的回归测试。"""

import unittest
from pathlib import Path


REQUIREMENTS_PATH = Path(__file__).parents[1] / "requirements.txt"


class RuntimeRequirementsTests(unittest.TestCase):
    """防止实际导入的安全依赖再次遗漏出插件清单。"""

    def test_bleach_is_declared_for_html_sanitization(self):
        requirements = REQUIREMENTS_PATH.read_text(encoding="utf-8")

        self.assertIn("bleach>=6.0.0", requirements)
