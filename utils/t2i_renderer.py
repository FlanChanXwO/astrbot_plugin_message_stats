"""AstrBot T2I 渲染适配。

本模块直接将已生成的 HTML 发送到兼容 AstrBot 的 T2I 服务，不启动浏览器、
不落地图片文件，也不依赖 Pillow。画布宽度在服务端截图前固定，避免
远端默认视口比模板宽时在右侧产生空白填充。
"""

import json
import re
from typing import Any


# astrbot-t2i-service 的接口文档将 720px 定义为默认视口高度；其当前实现仅在
# 宽高同时给出时才会实际设置视口，因此这里显式传入该服务默认值以确保宽度生效。
DEFAULT_VIEWPORT_HEIGHT = 720


class T2IRenderError(RuntimeError):
    """AstrBot T2I 未返回可发送图片地址时抛出。"""


def get_container_width(html_content: str, fallback_width: int) -> int:
    """读取排行榜模板的容器宽度，并加上原本的左右画布留白。"""
    match = re.search(
        r"\.container\s*\{[^{}]*?max-width\s*:\s*(\d+)px",
        html_content,
        re.IGNORECASE | re.DOTALL,
    )
    if not match:
        return fallback_width
    return int(match.group(1)) + 100


def prepare_html(html_content: str, width: int) -> str:
    """为服务端截图声明与模板一致的固定宽度画布。"""
    canvas_style = f"""
<style id="message-stats-t2i-canvas">
  html, body {{
    width: {width}px !important;
    min-width: {width}px !important;
    max-width: {width}px !important;
    margin: 0 !important;
    overflow-x: hidden !important;
  }}
</style>
"""
    if "</head>" in html_content:
        return html_content.replace("</head>", f"{canvas_style}</head>", 1)
    return f"{canvas_style}{html_content}"


def build_options(width: int) -> dict[str, Any]:
    """构造 AstrBot T2I 截图参数。

    ``viewport_width`` 和服务文档规定的默认 ``viewport_height`` 必须成对
    传入，才能让当前 T2I 服务实际应用模板画布宽度；``normal`` 保持一倍设备
    缩放，避免旧版 Playwright 链路的双倍像素输出。JPEG 质量沿用插件既有
    T2I 策略的 80，且不引入额外图像处理依赖。
    """
    return {
        "full_page": True,
        "type": "jpeg",
        "quality": 80,
        "animations": "disabled",
        "scale": "css",
        "viewport_width": width,
        "viewport_height": DEFAULT_VIEWPORT_HEIGHT,
        "device_scale_factor_level": "normal",
    }


def resolve_endpoint(plugin_config: Any, context: Any) -> str:
    """优先使用插件配置，否则继承 AstrBot 全局 T2I 端点。"""
    endpoint = str(getattr(plugin_config, "t2i_endpoint", "") or "").strip()
    if not endpoint:
        get_config = getattr(context, "get_config", None)
        config = get_config() if callable(get_config) else getattr(context, "_config", None)
        if hasattr(config, "get"):
            endpoint = str(config.get("t2i_endpoint", "") or "").strip()
    if not endpoint:
        raise T2IRenderError("未配置 T2I 端点；请设置插件 t2i_endpoint 或 AstrBot 的 t2i_endpoint")
    endpoint = endpoint.rstrip("/")
    return endpoint if endpoint.endswith("/text2img") else f"{endpoint}/text2img"


def build_request(html_content: str, width: int) -> dict[str, Any]:
    """使用服务端的 ``html`` 字段，避免 ``tmpl`` 路径忽略截图选项。"""
    return {
        "html": prepare_html(html_content, width),
        "json": True,
        "options": build_options(width),
    }


def get_image_url(endpoint: str, response_data: dict[str, Any]) -> str:
    """从本地 T2I 标准响应中取得可发送的图片 URL。"""
    if response_data.get("code") != 0:
        raise T2IRenderError(f"T2I 返回失败: {response_data}")
    image_id = str((response_data.get("data") or {}).get("id") or "").strip()
    if image_id.startswith(("http://", "https://")):
        return image_id
    if not image_id:
        raise T2IRenderError(f"T2I 未返回图片 ID: {response_data}")
    return f"{endpoint}/{image_id.lstrip('/')}"


async def render_html(endpoint: str, html_content: str, width: int) -> str:
    """直接调用 T2I ``html`` 接口，确保服务端应用截图尺寸参数。"""
    import aiohttp

    async with aiohttp.ClientSession(trust_env=True) as session:
        async with session.post(f"{endpoint}/generate", json=build_request(html_content, width)) as response:
            response_body = await response.text()
            if response.status != 200:
                raise T2IRenderError(f"T2I 请求失败 HTTP {response.status}: {response_body}")
    try:
        response_data = json.loads(response_body)
    except json.JSONDecodeError as exc:
        raise T2IRenderError(f"T2I 返回的不是 JSON: {response_body}") from exc
    return get_image_url(endpoint, response_data)
