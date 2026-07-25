"""T2I 渲染参数的无依赖回归测试。"""

import importlib.util
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).parents[1] / "utils" / "t2i_renderer.py"
SPEC = importlib.util.spec_from_file_location("t2i_renderer", MODULE_PATH)
t2i_renderer = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(t2i_renderer)


class T2IRendererTests(unittest.TestCase):
    def test_container_width_uses_template_width_without_new_cap(self):
        html = "<style>.container { max-width: 1400px; }</style>"
        self.assertEqual(t2i_renderer.get_container_width(html, 1200), 1500)

    def test_prepare_html_injects_fixed_canvas(self):
        rendered = t2i_renderer.prepare_html("<html><head></head><body></body></html>", 600)
        self.assertIn("width: 600px !important", rendered)
        self.assertIn('id="message-stats-t2i-canvas"', rendered)

    def test_request_uses_html_field_and_normal_scale(self):
        request = t2i_renderer.build_request("<html><head></head></html>", 480)
        self.assertIn("html", request)
        self.assertNotIn("tmpl", request)
        self.assertEqual(request["options"]["viewport_width"], 480)
        self.assertEqual(request["options"]["viewport_height"], 720)
        self.assertEqual(request["options"]["device_scale_factor_level"], "normal")

    def test_image_url_uses_response_id(self):
        response = {"code": 0, "data": {"id": "data/rendered.jpg"}}
        result = t2i_renderer.get_image_url("http://localhost:8999/text2img", response)
        self.assertEqual(result, "http://localhost:8999/text2img/data/rendered.jpg")

    def test_image_url_rejects_failed_response(self):
        with self.assertRaises(t2i_renderer.T2IRenderError):
            t2i_renderer.get_image_url("http://localhost:8999/text2img", {"code": 1})
