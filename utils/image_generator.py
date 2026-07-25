"""
HTML 模板生成模块
负责生成交给 AstrBot T2I 服务渲染的排行榜 HTML
"""

import asyncio
import aiofiles
from pathlib import Path
from typing import List, Optional, Dict, Any, Union
from datetime import datetime
import os
import hashlib
import html
import base64
from urllib.parse import quote

from astrbot.api import logger as astrbot_logger
from astrbot.api.star import StarTools

# 异步 HTTP 请求（用于获取 TG/Discord 头像）
try:
    import aiohttp
    AIOHTTP_AVAILABLE = True
except ImportError:
    aiohttp = None
    AIOHTTP_AVAILABLE = False

# 从集中管理的常量模块导入图片生成配置
from .constants import (
    IMAGE_WIDTH,
)

# Jinja2模板引擎
try:
    from jinja2 import Template, Environment, select_autoescape, FileSystemLoader
    JINJA2_AVAILABLE = True
except ImportError:
    JINJA2_AVAILABLE = False
    astrbot_logger.warning("Jinja2未安装，将使用不安全的字符串拼接方式")

from .models import UserData, GroupInfo, PluginConfig
from .exception_handlers import safe_generation, safe_file_operation
from .group_id_utils import get_fallback_group_name, is_official_qq_openid, is_placeholder_group_name




class ImageGenerationError(Exception):
    """图片生成异常
    
    当图片生成过程中发生错误时抛出的自定义异常。
    
    Attributes:
        message (str): 异常消息，描述具体的错误原因
        
    Example:
        >>> raise ImageGenerationError("HTML 模板生成失败")
    """
    pass


_AVATAR_COLORS = ['#F59E0B','#3B82F6','#8B5CF6','#EC4899','#10B981','#EF4444','#14B8A6','#F97316','#6366F1','#84CC16','#06B6D4','#D946EF','#0EA5E9','#EAB308','#A855F7']

def _gen_bubble_layout(users):
    import math, random; n = len(users)
    if n == 0: return [], [], [], 800, 800
    max_msg = max(u.display_total if u.display_total is not None else u.message_count for u in users)
    if max_msg == 0: max_msg = 1
    sqrt_max = max(1, math.sqrt(max_msg))
    sizes = [max(80, min(250, 80 + ((u.display_total if u.display_total is not None else u.message_count) / max_msg) ** 0.4 * 170)) for u in users]
    fonts = [max(14, min(28, 14 + (s-80)/170 * 14)) for s in sizes]
    placed, raw_pos = [], []
    def overlaps(x, y, r):
        for px, py, pr in placed:
            dx, dy = x - px, y - py
            if dx*dx + dy*dy < (r + pr + 8)**2: return True
        return False
    random.seed(42)
    jitter = lambda: (random.random() - 0.5) * 5.0
    for i in range(n):
        r = sizes[i]/2
        if i == 0: bx, by = 0, 0
        else:
            ta = math.atan2(-placed[0][1], -placed[0][0]) + i * 2.39996; found = False
            for st in range(1, 1000):
                sr = r + sizes[0]/2 + st * 4.0
                for ao in range(24):
                    a = ta + ao * math.pi / 12
                    tx, ty = math.cos(a) * sr + jitter(), math.sin(a) * sr + jitter()
                    if not overlaps(tx, ty, r): bx, by = tx, ty; found = True; break
                if found: break
            if not found: bx, by = 0, 0
        raw_pos.append((bx, by)); placed.append((bx, by, r))
    
    if n == 1:
        min_x = -sizes[0]/2
        max_x = sizes[0]/2
        min_y = -sizes[0]/2
        max_y = sizes[0]/2
    else:
        min_x = min(p[0]-sizes[i]/2 for i,p in enumerate(raw_pos))
        max_x = max(p[0]+sizes[i]/2 for i,p in enumerate(raw_pos))
        min_y = min(p[1]-sizes[i]/2 for i,p in enumerate(raw_pos))
        max_y = max(p[1]+sizes[i]/2 for i,p in enumerate(raw_pos))
        
    margin = 20
    cw = 800
    ch = 800
    sx = (cw - margin*2) / max(1, max_x - min_x)
    sy = (ch - margin*2) / max(1, max_y - min_y)
    scale = min(1.0, min(sx, sy))
    
    ox = (cw - (max_x - min_x) * scale) / 2 - min_x * scale + margin
    oy = (ch - (max_y - min_y) * scale) / 2 - min_y * scale + margin
    
    fs2, ff2, fp2 = [], [], []
    final_max_y = 0
    
    for i in range(n):
        fx = raw_pos[i][0] * scale + ox
        fy = raw_pos[i][1] * scale + oy
        fs = max(60, sizes[i] * scale); ff = max(10, fonts[i] * scale)
        fs2.append(int(fs)); ff2.append(int(ff)); fp2.append((int(fx - fs/2), int(fy - fs/2)))
        
        bottom = fy + fs/2
        if bottom > final_max_y: final_max_y = bottom

    area_h = 800
    if n > 0 and final_max_y + margin > 800:
        area_h = final_max_y + margin

    return fs2, ff2, fp2, 800, int(area_h)


class ImageGenerator:
    """HTML 模板生成器。

    类名为兼容已有插件调用而保留；它只负责整理数据、读取模板并生成 HTML，
    具体截图完全交由 AstrBot 的 T2I 服务处理。
    """
    
    def __init__(self, config: PluginConfig):
        """初始化图片生成器
        
        Args:
            config (PluginConfig): 插件配置对象，包含生成参数和设置
        """
        self.config = config
        self.logger = astrbot_logger
        
        # 图片生成配置
        self.width = IMAGE_WIDTH
        
        # 模板路径 - 根据主题选择
        self._templates_dir = Path(__file__).parent.parent / "templates"
        self._update_template_path()
        
        # 模板缓存机制
        self._template_cache: Dict[str, Any] = {}
        self._cache_lock = asyncio.Lock()
        self._cache_hits = 0
        self._cache_misses = 0
        
        # Jinja2环境将在initialize方法中初始化
        self.jinja_env = None
        
        # 头像缓存字典 {user_id: avatar_url}，每次生成图片时预获取，用完即弃
        self._avatar_cache: Dict[str, str] = {}
        self._font_css_cache_key = None
        self._font_css_cache_value = ""

    def _update_template_path(self):
        """根据主题配置更新模板路径（支持自动根据时间切换主题）"""
        theme = getattr(self.config, 'theme', 'default')
        auto_switch = getattr(self.config, 'auto_theme_switch', False)
        
        if auto_switch:
            # 自动根据时间切换主题
            theme = self._get_auto_theme(theme)
            self.logger.info(f"自动主题切换已启用，当前时间匹配主题: {theme}")
        
        template_map = {
        'default': 'rank_template_cartoon_light.html',
        'cartoon_light': 'rank_template_cartoon_light.html',
        'cartoon_dark': 'rank_template_cartoon_dark.html',
        'liquid_glass': 'rank_template_liquid_glass.html',
        'liquid_glass_dark': 'rank_template_liquid_glass_dark.html',
        }
        template_file = template_map.get(theme, 'rank_template.html')
        self.template_path = self._templates_dir / template_file
        self.logger.info(f"使用排行榜主题: {theme}, 模板: {template_file}")
    
    def _get_auto_theme(self, base_theme: str) -> str:
        """根据当前时间自动选择合适的主题
        
        根据 auto_theme_switch 配置中的 light/dark 切换时间，
        判断当前应该使用浅色主题还是深色主题，并自动映射到对应的主题版本。
        
        Args:
            base_theme: 用户配置的基础主题名称
            
        Returns:
            str: 主题名称，根据当前时段自动映射到对应的浅色/深色版本
        """
        try:
            switch_times = getattr(self.config, 'theme_switch_times', {"light": "06:00", "dark": "18:00"})
            now = datetime.now()
            current_minutes = now.hour * 60 + now.minute
            
            # 解析浅色主题开始时间
            light_time_str = switch_times.get("light", "06:00")
            light_h, light_m = map(int, light_time_str.split(':'))
            light_minutes = light_h * 60 + light_m
            
            # 解析深色主题开始时间
            dark_time_str = switch_times.get("dark", "18:00")
            dark_h, dark_m = map(int, dark_time_str.split(':'))
            dark_minutes = dark_h * 60 + dark_m
            
            # 深色→浅色 映射表（深色时段配置的主题在浅色时段自动映射）
            light_theme_map = {
                'cartoon_dark': 'cartoon_light',
                'liquid_glass_dark': 'liquid_glass',
            }
            # 浅色→深色 映射表（浅色时段配置的主题在深色时段自动映射）
            dark_theme_map = {
                'liquid_glass': 'liquid_glass_dark',
                'default': 'cartoon_dark',
                'cartoon_light': 'cartoon_dark',
            }
            
            # 判断当前时间段
            if light_minutes <= current_minutes < dark_minutes:
                # 浅色时间段：深色主题自动映射回浅色版本
                return light_theme_map.get(base_theme, base_theme)
            else:
                # 深色时间段：浅色主题自动映射回深色版本
                return dark_theme_map.get(base_theme, 'cartoon_dark')
        except (ValueError, AttributeError, KeyError, TypeError) as e:
            self.logger.warning(f"自动主题切换时间解析失败，使用默认主题: {e}")
            return base_theme
    

    
    async def _init_jinja2_env(self):
        """初始化Jinja2环境
        
        创建Jinja2模板环境，启用自动转义以防止XSS攻击。
        如果Jinja2不可用，将使用不安全的字符串拼接方式作为备用。
        添加模板缓存机制以提高性能。
        
        Returns:
            None: 无返回值，初始化结果通过日志输出
            
        Example:
            >>> await self._init_jinja2_env()
            # 将初始化Jinja2环境或记录警告信息
        """
        if JINJA2_AVAILABLE:
            try:
                # 创建Jinja2环境，启用自动转义和缓存，但不启用异步
                self.jinja_env = Environment(
                    autoescape=select_autoescape(['html', 'xml']),
                    trim_blocks=True,
                    lstrip_blocks=True,
                    cache_size=400  # 启用模板缓存，但不启用异步
                )
                
                # 预加载模板文件
                await self._preload_templates()
                
                self.logger.info("Jinja2环境初始化成功，模板缓存已启用")
            except Exception as e:
                self.logger.error(f"Jinja2环境初始化失败: {e}")
                self.jinja_env = None
        else:
            self.jinja_env = None
            self.logger.warning("Jinja2不可用，将使用不安全的字符串拼接")
    
    async def _preload_templates(self):
        """预加载模板文件到缓存（使用模板路径区分的缓存键）"""
        try:
            if os.path.exists(self.template_path):
                # 使用异步文件读取优化
                async with aiofiles.open(self.template_path, 'r', encoding='utf-8') as f:
                    template_content = await f.read()
                
                # 缓存模板内容
                template_hash = self._get_template_hash(template_content)
                cache_key = self._get_template_cache_key()
                async with self._cache_lock:
                    self._template_cache[cache_key] = {
                        'content': template_content,
                        'hash': template_hash,
                        'template': self.jinja_env.from_string(template_content) if self.jinja_env else None
                    }
                
                self.logger.info(f"模板预加载完成，缓存键: {cache_key}")
            else:
                self.logger.warning(f"模板文件不存在: {self.template_path}")
        except Exception as e:
            self.logger.error(f"模板预加载失败: {e}")
    
    def _get_template_hash(self, content: str) -> str:
        """获取模板内容的哈希值，用于缓存验证"""
        return hashlib.md5(content.encode('utf-8')).hexdigest()

    def _get_template_cache_key(self) -> str:
        """获取基于当前模板路径的缓存键，确保不同主题模板各自独立缓存"""
        return f"main_template:{self.template_path.stem}"

    def _resolve_font_path(self) -> Optional[Path]:
        font_path = str(getattr(self.config, 'font_path', '') or '').strip()
        if not font_path:
            return None

        raw_path = Path(font_path).expanduser()
        candidates = []
        if raw_path.is_absolute():
            candidates.append(raw_path)
        else:
            plugin_dir = Path(__file__).parent.parent
            candidates.extend([
                plugin_dir / raw_path,
                plugin_dir / "fonts" / raw_path.name,
            ])
            font_base_dirs = getattr(self.config, 'font_base_dirs', []) or []
            for base_dir in font_base_dirs:
                base_path = Path(str(base_dir))
                candidates.extend([
                    base_path / raw_path,
                    base_path / raw_path.name,
                ])
            try:
                data_dir = Path(StarTools.get_data_dir('message_stats'))
                legacy_data_dir = Path(StarTools.get_data_dir("astrbot_plugin_message_stats"))
                candidates.extend([
                    data_dir / raw_path,
                    data_dir / "resources" / "fonts" / raw_path.name,
                    legacy_data_dir / raw_path,
                    legacy_data_dir / "resources" / "fonts" / raw_path.name,
                ])
            except Exception:
                pass

        checked = []
        for candidate in candidates:
            checked.append(str(candidate))
            if candidate.exists() and candidate.is_file():
                resolved = candidate.resolve()
                self.logger.info(f"自定义字体文件解析成功: {resolved}")
                return resolved

        self.logger.warning(f"自定义字体文件不存在，使用主题默认字体: {font_path}; 已检查: {' | '.join(checked)}")
        return None

    def _get_font_format(self, font_path: Path) -> str:
        suffix = font_path.suffix.lower()
        if suffix in {'.otf'}:
            return 'opentype'
        if suffix in {'.woff'}:
            return 'woff'
        if suffix in {'.woff2'}:
            return 'woff2'
        return 'truetype'

    def _get_font_mime_type(self, font_path: Path) -> str:
        suffix = font_path.suffix.lower()
        if suffix in {'.otf'}:
            return 'font/otf'
        if suffix in {'.woff'}:
            return 'font/woff'
        if suffix in {'.woff2'}:
            return 'font/woff2'
        return 'font/ttf'

    def _get_custom_font_css(self) -> str:
        font_path = self._resolve_font_path()
        if not font_path:
            self._font_css_cache_key = None
            self._font_css_cache_value = ""
            return ""

        try:
            stat = font_path.stat()
            cache_key = (str(font_path), stat.st_mtime_ns, stat.st_size)
            if cache_key == self._font_css_cache_key:
                return self._font_css_cache_value

            font_data = base64.b64encode(font_path.read_bytes()).decode('ascii')
        except OSError as e:
            self._font_css_cache_key = None
            self._font_css_cache_value = ""
            self.logger.warning(f"读取自定义字体文件失败，使用主题默认字体: {e}")
            return ""

        font_format = self._get_font_format(font_path)
        mime_type = self._get_font_mime_type(font_path)
        css = (
            "@font-face { "
            "font-family: 'MessageStatsCustomFont'; "
            f"src: url(\"data:{mime_type};base64,{font_data}\") format('{font_format}'); "
            "font-weight: 100 900; font-style: normal; font-display: block; "
            "}\n"
            ":root { --message-stats-font-family: 'MessageStatsCustomFont', 'Microsoft YaHei', 'Segoe UI', sans-serif; }\n"
            "body, body * { font-family: var(--message-stats-font-family) !important; }"
        )
        self.logger.info(f"自定义字体文件已读取，准备注入CSS: {font_path}")
        self._font_css_cache_key = cache_key
        self._font_css_cache_value = css
        return css

    async def _get_cached_template(self) -> Optional[Union[str, Template]]:
        """获取缓存的模板（使用模板路径区分的缓存键，确保深浅色主题独立缓存）"""
        cache_key = self._get_template_cache_key()
        async with self._cache_lock:
            cached = self._template_cache.get(cache_key)
            if cached:
                self._cache_hits += 1
                return cached.get('template') if self.jinja_env else cached.get('content')
            else:
                self._cache_misses += 1
                return None
    
    async def _update_template_cache(self, content: str):
        """更新模板缓存（使用模板路径区分的缓存键）"""
        try:
            template_hash = self._get_template_hash(content)
            cache_key = self._get_template_cache_key()
            async with self._cache_lock:
                self._template_cache[cache_key] = {
                    'content': content,
                    'hash': template_hash,
                    'template': self.jinja_env.from_string(content) if self.jinja_env else None
                }

        except Exception as e:
            self.logger.error(f"更新模板缓存失败: {e}")
    
    async def get_cache_stats(self) -> Dict[str, int]:
        """获取缓存统计信息"""
        async with self._cache_lock:
            return {
                'hits': self._cache_hits,
                'misses': self._cache_misses,
                'total_requests': self._cache_hits + self._cache_misses,
                'hit_rate': self._cache_hits / max(1, self._cache_hits + self._cache_misses)
            }
    
    @safe_generation(default_return=None)
    async def initialize(self):
        """初始化本地 HTML 模板环境。

        图片由 AstrBot 的 T2I 服务生成；此处不再创建浏览器进程或本地截图文件。
        """
        try:
            await self._init_jinja2_env()
            self.logger.info("HTML 模板生成器初始化完成，将使用 AstrBot T2I 渲染")
        except (FileNotFoundError, PermissionError, OSError) as exc:
            self.logger.error(f"初始化 HTML 模板生成器失败: {exc}")
            raise ImageGenerationError(f"初始化失败: {exc}") from exc

    async def cleanup(self):
        """清理模板与头像缓存，不持有浏览器或本地图片资源。"""
        self._avatar_cache.clear()
        await self.clear_cache()
        self.logger.info("HTML 模板生成器资源已清理")
    
    @safe_generation(default_return="")
    async def generate_rank_html(
        self,
        users: List[UserData],
        group_info: GroupInfo,
        title: str,
        current_user_id: Optional[str] = None,
        llm_token_usage: Optional[Dict[str, int]] = None,
        titles_map: Optional[Dict[str, str]] = None,
    ) -> str:
        """生成排行榜 HTML，供调用方交给 AstrBot T2I 截图。"""
        self._update_template_path()
        return await self._generate_html(
            users,
            group_info,
            title,
            current_user_id,
            llm_token_usage,
            titles_map,
        )

    @safe_generation(default_return="")
    async def generate_personal_stats_html(self, data: dict, group_info: GroupInfo) -> str:
        """生成个人统计卡片 HTML，使用固定的 480px T2I 画布。"""
        theme = getattr(self.config, "theme", "default")
        if getattr(self.config, "auto_theme_switch", False):
            theme = self._get_auto_theme(theme)
        personal_template_map = {
            "default": "personal_stats.html",
            "cartoon_light": "personal_stats_cartoon_light.html",
            "cartoon_dark": "personal_stats_cartoon_dark.html",
            "liquid_glass": "personal_stats.html",
            "liquid_glass_dark": "personal_stats.html",
        }
        template_path = self._templates_dir / personal_template_map.get(theme, "personal_stats.html")
        if not template_path.is_file():
            raise ImageGenerationError(f"个人卡片模板文件不存在: {template_path}")

        template_data = dict(data)
        template_data["is_dark"] = theme.endswith("_dark")
        template_data["custom_font_css"] = self._get_custom_font_css()
        template_data["current_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        async with aiofiles.open(template_path, "r", encoding="utf-8") as template_file:
            template_content = await template_file.read()
        if JINJA2_AVAILABLE and self.jinja_env:
            return self.jinja_env.from_string(template_content).render(data=template_data)

        for key, value in template_data.items():
            template_content = template_content.replace(f"{{{{ data.{key} }}}}", str(value))
            template_content = template_content.replace(f"{{{{data.{key}}}}}", str(value))
        return template_content

    @safe_generation(default_return="")
    async def generate_milestone_html(
        self,
        user_id: str,
        nickname: str,
        milestone_count: int,
        rank: int,
        daily_count: int,
        active_days: int,
        last_date: str,
        group_total_messages: int,
        percentage: float,
        group_info: GroupInfo,
    ) -> str:
        """生成里程碑卡片 HTML，使用固定的 600px T2I 画布。"""
        template_path = self._templates_dir / "milestone_template.html"
        if not template_path.is_file():
            raise ImageGenerationError(f"里程碑模板文件不存在: {template_path}")
        async with aiofiles.open(template_path, "r", encoding="utf-8") as template_file:
            template_content = await template_file.read()

        group_name = self._get_display_group_name(group_info)
        template_data = {
            "avatar_url": self._get_avatar_url(user_id, nickname, group_info),
            "nickname": self._escape_html_safe(nickname),
            "user_id": self._escape_html_safe(str(user_id)),
            "group_name": self._escape_html_safe(
                f"{group_name}[{group_info.group_id}]"
                if not is_official_qq_openid(group_info.group_id)
                else group_name
            ),
            "show_group_id": not is_official_qq_openid(group_info.group_id),
            "milestone_count": milestone_count,
            "rank": rank,
            "daily_count": daily_count,
            "active_days": active_days,
            "last_date": self._escape_html_safe(last_date or "未知"),
            "group_total_messages": group_total_messages,
            "percentage": f"{percentage:.2f}",
            "current_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "custom_font_css": self._get_custom_font_css(),
        }
        if JINJA2_AVAILABLE and self.jinja_env:
            return self.jinja_env.from_string(template_content).render(**template_data)

        for key, value in template_data.items():
            template_content = template_content.replace(f"{{{{ {key} }}}}", str(value))
            template_content = template_content.replace(f"{{{{{key}}}}}", str(value))
        return template_content
    
    @safe_generation(default_return="")
    async def _generate_html(self, 
                      users: List[UserData], 
                      group_info: GroupInfo, 
                      title: str,
                      current_user_id: Optional[str] = None,
                      llm_token_usage: Dict[str, int] = None,
                      titles_map: Optional[Dict[str, str]] = None) -> str:
        """生成HTML内容
        
        Args:
            users: 用户数据列表
            group_info: 群组信息
            title: 排行榜标题
            current_user_id: 当前用户ID，用于高亮显示
            llm_token_usage: LLM token使用统计
            titles_map: 用户ID到头衔的映射字典 {user_id: title}
        """
        if not users:
            return await self._generate_empty_html(group_info, title)
        
        # 预获取非QQ平台用户的真实头像（TG/Discord），填充到 _avatar_cache
        await self._prefetch_avatars(users, group_info)
        
        # 使用批量处理优化性能（显式传入头衔映射）
        self._current_group_info = group_info
        processed_data = self._process_user_data_batch(users, current_user_id, titles_map, group_info)
        
        # 计算统计数据
        total_messages = processed_data['total_messages']
        
        # 生成完整HTML
        html_template = await self._load_html_template()
        
        # 获取当前时间
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # 准备模板数据（使用字典构建优化）
        llm_token_text = ""
        if llm_token_usage and llm_token_usage.get("total_tokens", 0) > 0:
            llm_token_text = f"LLM Token 消耗: {llm_token_usage.get('total_tokens', 0)} (输入{llm_token_usage.get('prompt_tokens', 0)}+输出{llm_token_usage.get('completion_tokens', 0)})"
        
        template_data = {
            'group_name': self._escape_html_safe(self._get_display_group_name(group_info)),
            'group_id': self._escape_html_safe(str(group_info.group_id)),
            'show_group_id': not is_official_qq_openid(group_info.group_id),
            'title': self._escape_html_safe(title),
            'total_messages': self._escape_html_safe(str(total_messages)),
            'user_count': self._escape_html_safe(str(len(users))),
            'current_time': self._escape_html_safe(current_time),
            'custom_font_css': self._get_custom_font_css(),
            'llm_token_info': self._escape_html_safe(llm_token_text) if llm_token_text else ""
        }
        
        # 生成HTML内容（优化渲染逻辑）
        return await self._render_html_template(html_template, template_data, processed_data['user_items'])
    
    def _process_user_data_batch(self, users: List[UserData], current_user_id: Optional[str], 
                                  titles_map: Optional[Dict[str, str]] = None, group_info=None) -> Dict[str, Any]:
        """批量处理用户数据，优化性能
        
        Args:
            users: 用户数据列表
            current_user_id: 当前用户ID，用于高亮显示
            titles_map: 用户ID到头衔的映射字典 {user_id: title}
                      优先使用此参数中的头衔，若无则回退到 user.display_title
            group_info: 群组信息，用于判断平台获取头像
        """
        if not users:
            return {'total_messages': 0, 'user_items': []}
        
        # 预计算统计数据 - 使用时间段内的发言数
        total_messages = sum(user.display_total if user.display_total is not None else user.message_count for user in users)
        max_messages = max((user.display_total if user.display_total is not None else user.message_count) for user in users) if users else 1
        
        # 批量生成用户项目
        sizes, fonts, pos, area_w, area_h = _gen_bubble_layout(users)
        if len(sizes) < len(users):
            sizes.extend([70] * (len(users) - len(sizes)))
            fonts.extend([10] * (len(users) - len(fonts)))
            pos.extend([(area_w/2, area_h/2)] * (len(users) - len(pos)))
        user_items = []
        current_user_found = False
        
        for i, user in enumerate(users):
            is_current_user = current_user_id and user.user_id == current_user_id
            if is_current_user:
                current_user_found = True
            
            # 使用时间段内的发言数
            user_messages = user.display_total if user.display_total is not None else user.message_count
            
            # 获取 LLM 头衔：优先使用 titles_map，其次 user.display_title
            user_title = None
            user_title_color = None
            if titles_map and user.user_id in titles_map:
                raw = titles_map[user.user_id]
                if isinstance(raw, dict):
                    user_title = raw.get("title")
                    user_title_color = raw.get("color")
                else:
                    user_title = raw
            elif user.display_title:
                user_title = user.display_title
                user_title_color = user.display_title_color

            
            if user_title:
                self.logger.info(f"头衔数据: {user.nickname} -> 「{user_title}」")
            
            c = _AVATAR_COLORS[sum(ord(ch) for ch in str(user.user_id)) % 15]
            idx = _AVATAR_COLORS.index(c) if c in _AVATAR_COLORS else sum(ord(ch) for ch in str(user.user_id)) % 15
            g2 = _AVATAR_COLORS[(idx + 5) % 15]
            user_items.append({
                'rank': i + 1,
                'nickname': user.nickname,
                'title': user_title,
                'title_color': user_title_color,
                'avatar_url': self._get_avatar_url(user, user.nickname, self._current_group_info),
                'total': user_messages,
                'percentage': (user_messages / total_messages * 100) if total_messages > 0 else 0,
                'fill_ratio': (user_messages / max_messages * 100) if max_messages > 0 else 0,
                'last_date': user.last_date or "未知",
                'is_current_user': is_current_user,
                'is_separator': False,
                'bubble_size': sizes[i], 'bubble_font': fonts[i], 'pos_x': pos[i][0], 'pos_y': pos[i][1],
                'card_grad1': c, 'card_grad2': g2, '_group_info': group_info
            })
        
        # 如果当前用户不在排行榜中，添加到末尾
        if current_user_id and not current_user_found:
            current_user_data = next((user for user in users if user.user_id == current_user_id), None)
            if current_user_data:
                current_user_messages = current_user_data.display_total if current_user_data.display_total is not None else current_user_data.message_count
                current_rank = sum(1 for user in users if (user.display_total if user.display_total is not None else user.message_count) > current_user_messages) + 1
                user_items.append({
                    'rank': current_rank,
                    'nickname': current_user_data.nickname,
                    'avatar_url': self._get_avatar_url(current_user_data, current_user_data.nickname, self._current_group_info),
                    'total': current_user_messages,
                    'percentage': (current_user_messages / total_messages * 100) if total_messages > 0 else 0,
                    'last_date': current_user_data.last_date or "未知",
                    'is_current_user': True,
                    'is_separator': True,
                    '_group_info': group_info
                })
        
        return {
            'total_messages': total_messages,
            'user_items': user_items,
            'area_w': area_w,
            'area_h': area_h
        }

    
    async def _render_html_template(self, template_content: str, template_data: Dict[str, Any], user_items: List[Dict[str, Any]]) -> str:
        """优化的HTML模板渲染方法"""
        try:
            if JINJA2_AVAILABLE and self.jinja_env:
                # 使用缓存的模板
                cached_template = await self._get_cached_template()
                if cached_template and isinstance(cached_template, Template):
                    template_data['user_items'] = user_items
                    return cached_template.render(**template_data)
                else:
                    # 动态创建模板
                    template = self.jinja_env.from_string(template_content)
                    template_data['user_items'] = user_items
                    return template.render(**template_data)
            else:
                # Jinja2不可用时，使用纯占位符回退模板
                return await self._render_fallback(template_data, user_items)
        except (ValueError, TypeError, KeyError, PermissionError, UnicodeDecodeError) as e:
            self.logger.error(f"HTML模板渲染失败({type(e).__name__}): {e}")
            return await self._render_fallback(template_data, user_items)
    
    async def _render_fallback(self, template_data: Dict[str, Any], user_items: List[Dict[str, Any]]) -> str:
        """统一的回退渲染方法"""
        fallback_template = await self._get_fallback_template()
        return self._render_fallback_template(fallback_template, template_data, user_items)
    
    def _render_fallback_template(self, template_content: str, template_data: Dict[str, Any], user_items: List[Dict[str, Any]]) -> str:
        """回退模板渲染方法（安全版本）
        
        当Jinja2不可用时的安全回退方案。
        使用简单的字符串替换而不是format()，避免Jinja2语法冲突。
        """
        # 使用生成器表达式优化内存使用
        user_items_html = ''.join(self._generate_user_item_html_safe(item) for item in user_items)
        
        # 安全替换：避免Jinja2语法冲突
        safe_content = template_content
        for key, value in template_data.items():
            if isinstance(value, str):
                # 对字符串值进行HTML转义
                safe_value = self._escape_html_safe(value)
                safe_content = safe_content.replace('{{' + key + '}}', safe_value)
            else:
                # 对于非字符串值，直接替换
                safe_content = safe_content.replace('{{' + key + '}}', str(value))
        
        # 替换user_items
        safe_content = safe_content.replace('{{user_items}}', user_items_html)
        
        return safe_content
    
    # 最简单的空数据回退HTML常量
    _EMPTY_FALLBACK_HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>发言排行榜</title>
</head>
<body>
    <h1>发言排行榜</h1>
    <p>暂无数据</p>
</body>
</html>"""

    async def _generate_empty_html(self, group_info: GroupInfo, title: str) -> str:
        """生成空数据HTML（优化版本）"""
        # 尝试从缓存获取空数据模板
        empty_template_cache_key = 'empty_template'
        async with self._cache_lock:
            cached_empty = self._template_cache.get(empty_template_cache_key)
        
        if cached_empty:
            template_content = cached_empty['content']
            template_obj = cached_empty.get('template')
        else:
            # 创建空数据模板
            template_content = await self._get_empty_template()
            async with self._cache_lock:
                self._template_cache[empty_template_cache_key] = {
                    'content': template_content,
                    'template': self.jinja_env.from_string(template_content) if self.jinja_env else None
                }
            template_obj = self._template_cache[empty_template_cache_key].get('template')
        
        # 准备模板数据
        template_data = {
            'group_name': self._escape_html_safe(self._get_display_group_name(group_info)),
            'group_id': self._escape_html_safe(str(group_info.group_id)),
            'show_group_id': not is_official_qq_openid(group_info.group_id),
            'title': self._escape_html_safe(title),
            'custom_font_css': self._get_custom_font_css()
        }
        
        try:
            if JINJA2_AVAILABLE and self.jinja_env and template_obj:
                return template_obj.render(**template_data)
            else:
                # 使用安全的字符串替换而不是format()
                safe_content = template_content
                for key, value in template_data.items():
                    if isinstance(value, str):
                        safe_value = self._escape_html_safe(value)
                        safe_content = safe_content.replace('{{' + key + '}}', safe_value)
                    else:
                        safe_content = safe_content.replace('{{' + key + '}}', str(value))
                return safe_content
        except (ValueError, TypeError, KeyError, PermissionError, UnicodeDecodeError) as e:
            self.logger.error(f"空数据HTML模板渲染失败({type(e).__name__}): {e}")
            return self._EMPTY_FALLBACK_HTML
    
    async def _get_empty_template(self) -> str:
        """获取空数据模板（简化版本）"""
        return """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>{{ title }}</title>
    <style>
        {{ custom_font_css | safe }}
        body {
            font-family: var(--message-stats-font-family, 'Microsoft YaHei', sans-serif);
            background: linear-gradient(135deg, #E9EFF6 0%, #D6E4F0 100%);
            margin: 0;
            padding: 40px;
            text-align: center;
        }
        .container {
            background: rgba(255,255,255,0.95);
            border-radius: 20px;
            padding: 60px;
            max-width: 600px;
            margin: 0 auto;
        }
        .title {
            font-size: 32px;
            color: #1F2937;
            margin-bottom: 20px;
        }
        .subtitle {
            font-size: 24px;
            color: #6B7280;
            margin-bottom: 40px;
        }
        .empty-text {
            font-size: 18px;
            color: #9CA3AF;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="title">{{ group_name }}{% if show_group_id %}[{{ group_id }}]{% endif %}</div>
        <div class="subtitle">{{ title }}</div>
        <div class="empty-text">
            暂无发言数据
            <br>
            期待大家的活跃发言！
        </div>
    </div>
</body>
</html>"""
    
    def _generate_user_item_html_safe(self, item_data: Dict[str, Any]) -> str:
        """生成安全的用户条目HTML"""
        # 使用元组和字典预构建减少字符串操作
        css_classes = self._get_css_classes(item_data)
        styles = self._get_item_styles(item_data)
        safe_content = self._get_safe_content(item_data)
        
        # 使用更安全的字符串拼接方式
        # 对所有动态内容进行HTML转义
        safe_nickname = html.escape(safe_content['nickname'])
        safe_avatar_url = html.escape(safe_content['avatar_url'])
        safe_last_date = html.escape(safe_content['last_date'])
        safe_separator_style = html.escape(styles['separator'])
        safe_avatar_border = html.escape(styles['avatar_border'])
        
        # 根据当前用户状态选择合适的排名样式类
        rank_class = "rank-current" if item_data['is_current_user'] else "rank"
        
        # 获取头衔和颜色
        user_title_raw = item_data.get('title', None) or item_data.get('safe_content', {}).get('title', None)
        user_title_color_raw = item_data.get('title_color', None) or item_data.get('safe_content', {}).get('title_color', None)
        user_title_html = ""
        if user_title_raw:
            safe_title = html.escape(str(user_title_raw))
            safe_title_color = html.escape(str(user_title_color_raw)) if user_title_color_raw else '#7C3AED'
            user_title_html = f'<div class="user-title" style="color:{safe_title_color};background:{safe_title_color}22;font-size:13px;font-weight:700;padding:0px 8px;border-radius:10px;display:inline-block;margin-left:8px;vertical-align:middle;line-height:24px;">「{safe_title}」</div>'
        
        html_parts = [
            f'<div class="{css_classes["item"]}" style="{safe_separator_style}">',
            f'    <div class="{rank_class}">#{item_data["rank"]}</div>',
            f'    <img class="avatar" src="{safe_avatar_url}" style="border-color: {safe_avatar_border};" />',
            '    <div class="info">',
            '        <div class="name-date">',
            f'            <div style="display:flex;align-items:center;gap:8px;margin-bottom:6px;"><span class="nickname" style="font-size:24px;font-weight:600;color:#1F2937;line-height:1.3;">{safe_nickname}</span>{user_title_html}</div>',
            f'            <div class="date" style="color:#6B7280;font-size:15px;">最近发言: {safe_last_date}</div>',
            '        </div>',
            '        <div class="stats">',
            f'            <div class="count">{item_data["total"]} 次</div>',
            f'            <div class="percentage">({item_data["percentage"]:.2f}%)</div>',
            '        </div>',
            '    </div>',
            '</div>'
        ]
        return '\n'.join(html_parts)
    
    def _get_css_classes(self, item_data: Dict[str, Any]) -> Dict[str, str]:
        """获取CSS类名（优化版本）"""
        return {
            'item': "user-item-current" if item_data['is_current_user'] else "user-item"
        }
    
    def _get_item_styles(self, item_data: Dict[str, Any]) -> Dict[str, str]:
        """获取样式信息（优化版本）"""
        return {
            'separator': "margin-top: 20px; border-top: 2px dashed #bdc3c7;" if item_data['is_separator'] else "margin-top: 10px;",
            'rank_color': "#EF4444" if item_data['is_current_user'] else "#3B82F6",
            'avatar_border': "#ffffff"
        }
    
    def _get_safe_content(self, item_data: Dict[str, Any]) -> Dict[str, str]:
        """获取安全的内容（优化版本）
        
        注意：不在此处进行 HTML 转义，转义推迟到最终渲染阶段：
        - Jinja2 路径：模板引擎的 autoescape 自动处理
        - Fallback 路径：_generate_user_item_html_safe 中手动转义
        避免重复转义导致 &amp; 等乱码。
        """
        # 不做HTML转义，仅提取原始值（转义由接收方负责）
        nickname = str(item_data.get('nickname', '未知用户'))
        last_date = str(item_data.get('last_date', '未知'))
        avatar_url = self._validate_url_safe(str(item_data.get('avatar_url', '')))
        
        # 处理头衔
        title = item_data.get('title', None)
        
        # 如果头像URL无效，使用回退彩色文字头像
        if not avatar_url:
            avatar_url = self._get_avatar_url(
                str(item_data.get('user_id', '0')),
                str(item_data.get('nickname', '')),
                item_data.get('_group_info', None)
            )
        
        content = {
            'nickname': nickname,
            'last_date': last_date,
            'avatar_url': avatar_url
        }
        
        if title:
            content['title'] = title
            
        return content

    def _escape_html_safe(self, text: str) -> str:
        """安全的HTML转义"""
        if not isinstance(text, str):
            text = str(text)
        return html.escape(text, quote=True)
    
    def _validate_url_safe(self, url: str) -> str:
        """验证并清理URL（支持 http/https 和 data URI）"""
        if not isinstance(url, str):
            url = str(url)
        
        if not url:
            return ""
        if not url.startswith(('http://', 'https://', 'data:')):
            return ""
        
        # 移除潜在的恶意字符
        url = url.replace('<', '').replace('>', '').replace('"', '').replace("'", '')
        return url

    _AVATAR_COLORS = ['#F59E0B','#3B82F6','#8B5CF6','#EC4899','#10B981',
                      '#EF4444','#14B8A6','#F97316','#6366F1','#84CC16',
                      '#06B6D4','#D946EF','#0EA5E9','#EAB308','#A855F7']

    @staticmethod
    def _get_avatar_color(seed: str) -> str:
        h = 0
        for ch in seed:
            h = (h * 31 + ord(ch)) & 0xFFFFFFFF
        colors = ImageGenerator._AVATAR_COLORS
        return colors[h % len(colors)]

    @staticmethod
    def _generate_avatar_svg_data_uri(nickname: str, seed: str) -> str:
        letter = '?'
        if nickname and nickname.strip():
            letter = nickname.strip()[0]
        color = ImageGenerator._get_avatar_color(seed or 'x')
        svg = f'<svg xmlns="http://www.w3.org/2000/svg" width="640" height="640" viewBox="0 0 640 640"><circle cx="320" cy="320" r="320" fill="{color}"/><text x="320" y="320" text-anchor="middle" dominant-baseline="central" font-size="280" font-weight="700" font-family="Microsoft YaHei,sans-serif" fill="white">{html.escape(letter)}</text></svg>'
        encoded = quote(svg)
        return f"data:image/svg+xml,{encoded}"

    # ========== 跨平台头像获取（TG / Discord / 飞书 / QQ） ==========

    @staticmethod
    def _detect_platform(group_id: str) -> str:
        """根据群ID特征识别平台
        
        - TG: 以 - 或 -100 开头的负数
        - Discord: 18-19 位纯数字
        - 飞书: 以 oc_ 开头
        - QQ: 5-10 位纯数字
        - 其他: 未知
        """
        gid = str(group_id).strip()
        
        # 飞书：oc_ 前缀
        if gid.startswith('oc_'):
            return 'feishu'
        
        # Telegram：以 - 或 -100 开头的负数
        if gid.startswith('-'):
            return 'telegram'
        
        # 到这里都是正数
        if gid.isdigit():
            length = len(gid)
            # QQ：5-10 位短数字
            if 5 <= length <= 10:
                return 'qq'
            # Discord：18-19 位 Snowflake
            if 18 <= length <= 19:
                return 'discord'
        
        return 'unknown'

    @staticmethod
    def _get_display_group_name(group_info: GroupInfo) -> str:
        group_id = str(group_info.group_id) if group_info else ""
        group_name = getattr(group_info, "group_name", "") if group_info else ""
        if not is_placeholder_group_name(group_name, group_id):
            return str(group_name).strip()
        return get_fallback_group_name(group_id)

    async def _prefetch_avatars(self, users: List[UserData], group_info: GroupInfo):
        """预获取本批用户的头像URL，填充到 _avatar_cache
        
        在生成HTML之前调用，异步并发获取TG/Discord/飞书的真实头像。
        获取失败或未配置Token的用户会自动回退到彩色文字头像。
        
        Args:
            users: 用户数据列表
            group_info: 群组信息
        """
        self._avatar_cache.clear()
        group_id_str = str(group_info.group_id) if group_info else ""
        platform = self._detect_platform(group_id_str)
        
        # QQ 不需要预获取，直接通过 qlogo.cn 拼接
        if platform == 'qq':
            return
        
        # 飞书：保留之前逻辑（回退彩色文字头像）
        if platform == 'feishu':
            return
        
        if platform == 'telegram':
            await self._prefetch_tg_avatars(users)
        elif platform == 'discord':
            await self._prefetch_dc_avatars(users)
    
    async def _prefetch_tg_avatars(self, users: List[UserData]):
        """预获取 Telegram 用户头像
        
        使用 TG Bot API 获取用户最新的头像文件路径，拼接为可下载的 URL。
        API 调用链路：getUserProfilePhotos -> getFile -> 拼接下载链接
        """
        tg_token = getattr(self.config, 'tg_bot_token', '')
        if not tg_token or not AIOHTTP_AVAILABLE:
            self.logger.debug("TG Bot Token 未配置或 aiohttp 不可用，跳过 TG 头像预获取")
            return
        
        self.logger.info(f"开始预获取 {len(users)} 个 TG 用户头像...")
        success_count = 0
        
        async def fetch_single(user_id: str):
            """获取单个用户的头像 URL"""
            try:
                # 步骤1: 获取用户头像列表
                photos_url = f"https://api.telegram.org/bot{tg_token}/getUserProfilePhotos"
                params = {"user_id": int(float(user_id)), "limit": 1}
                
                async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
                    async with session.get(photos_url, params=params) as resp:
                        if resp.status != 200:
                            return
                        data = await resp.json()
                    
                    if not data.get("ok") or not data.get("result", {}).get("photos"):
                        return
                    
                    # 取最新的头像（数组第一个），取最大分辨率的 file_id（数组最后一个）
                    latest_photos = data["result"]["photos"][0]
                    file_id = latest_photos[-1]["file_id"]
                    
                    # 步骤2: 获取文件路径
                    get_file_url = f"https://api.telegram.org/bot{tg_token}/getFile"
                    async with session.get(get_file_url, params={"file_id": file_id}) as resp2:
                        if resp2.status != 200:
                            return
                        file_data = await resp2.json()
                    
                    if not file_data.get("ok") or not file_data.get("result", {}).get("file_path"):
                        return
                    
                    file_path = file_data["result"]["file_path"]
                    
                    # 步骤3: 拼接最终下载链接
                    avatar_url = f"https://api.telegram.org/file/bot{tg_token}/{file_path}"
                    self._avatar_cache[user_id] = avatar_url
                    return True
            except Exception as e:
                self.logger.warning(f"获取 TG 头像失败 (user_id={user_id}): {e}")
                return None
        
        # 并发获取所有用户头像
        tasks = [fetch_single(u.user_id) for u in users if u.user_id]
        results = await asyncio.gather(*tasks)
        success_count = sum(1 for r in results if r)
        
        if success_count > 0:
            self.logger.info(f"TG 头像预获取完成: {success_count}/{len(users)} 成功")
        else:
            self.logger.warning("TG 头像预获取：所有用户均未获取到头像，将使用彩色文字头像回退")
    
    async def _prefetch_dc_avatars(self, users: List[UserData]):
        """预获取 Discord 用户头像
        
        通过 Discord API 获取用户信息，提取 avatar hash，拼接 CDN URL。
        如果用户的 avatar hash 以 a_ 开头，使用 GIF 格式。
        """
        dc_token = getattr(self.config, 'dc_bot_token', '')
        if not dc_token or not AIOHTTP_AVAILABLE:
            self.logger.debug("Discord Bot Token 未配置或 aiohttp 不可用，跳过 DC 头像预获取")
            return
        
        self.logger.info(f"开始预获取 {len(users)} 个 Discord 用户头像...")
        success_count = 0
        
        # Discord 需要 Bot 认证头
        headers = {
            "Authorization": f"Bot {dc_token}",
            "User-Agent": "DiscordBot (astrbot_plugin_message_stats, 1.0)"
        }
        
        async def fetch_single(user_id: str):
            """获取单个 Discord 用户的头像 URL"""
            try:
                user_url = f"https://discord.com/api/v10/users/{int(float(user_id))}"
                
                async with aiohttp.ClientSession(
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as session:
                    async with session.get(user_url) as resp:
                        if resp.status != 200:
                            return
                        user_data = await resp.json()
                    
                    avatar_hash = user_data.get("avatar")
                    if not avatar_hash:
                        # 用户没有设置头像，使用默认头像算法
                        # Discord 默认头像：user_id 右移 22 位后对 6（默认头像数量）取模
                        try:
                            uid_int = int(float(user_id))
                            default_index = (uid_int >> 22) % 6
                            avatar_url = f"https://cdn.discordapp.com/embed/avatars/{default_index}.png"
                            self._avatar_cache[user_id] = avatar_url
                            return True
                        except (ValueError, OverflowError):
                            return
                    
                    # 有自定义头像：判断是否为 GIF（a_ 开头）
                    ext = "gif" if avatar_hash.startswith("a_") else "png"
                    avatar_url = f"https://cdn.discordapp.com/avatars/{int(float(user_id))}/{avatar_hash}.{ext}"
                    self._avatar_cache[user_id] = avatar_url
                    return True
            except Exception as e:
                self.logger.debug(f"获取 DC 头像失败 (user_id={user_id}): {e}")
                return None
        
        # 并发获取所有用户头像
        tasks = [fetch_single(u.user_id) for u in users if u.user_id]
        results = await asyncio.gather(*tasks)
        success_count = sum(1 for r in results if r)
        
        if success_count > 0:
            self.logger.info(f"DC 头像预获取完成: {success_count}/{len(users)} 成功")
        else:
            self.logger.debug("DC 头像预获取：所有用户均未获取到头像，将使用彩色文字头像回退")

    def _get_avatar_url(self, user_id: str, nickname: str = "", group_info=None) -> str:
        """获取用户头像URL
        
        优先级：
        1. 预获取缓存（_avatar_cache，由 _prefetch_avatars 填充的 TG/Discord/飞书真实头像）
        2. QQ 平台：qlogo.cn 真实头像
        3. 回退：彩色文字 SVG 头像
        
        Args:
            user_id: 用户ID
            nickname: 用户昵称
            group_info: 群组信息
        
        Returns:
            str: 头像URL
        """
        if hasattr(user_id, "avatar_url"):
            avatar_url = self._validate_url_safe(str(getattr(user_id, "avatar_url", "") or ""))
            if avatar_url:
                return avatar_url
            nickname = nickname or getattr(user_id, "nickname", "")
            user_id = getattr(user_id, "user_id", "")

        user_id_str = str(user_id)
        group_id_str = str(group_info.group_id) if group_info else ""
        platform = self._detect_platform(group_id_str)
        
        # 优先级1: 预获取缓存（TG/Discord 的真实头像）
        cached_url = self._avatar_cache.get(user_id_str)
        if cached_url:
            return cached_url
        
        # 优先级2: QQ 平台使用 qlogo.cn 真实头像
        if platform == 'qq':
            return f"https://q1.qlogo.cn/g?b=qq&nk={user_id_str}&s=640"
        
        # 优先级3: 回退彩色文字头像（飞书、未知平台、或预获取失败的 TG/Discord）
        return self._generate_avatar_svg_data_uri(nickname, user_id_str)
    
    @safe_file_operation(default_return="")
    async def _load_html_template(self) -> str:
        """加载HTML模板（简化缓存逻辑）"""
        try:
            # 尝试从缓存获取
            cached_template = await self._get_cached_template()
            if cached_template:
                if isinstance(cached_template, str):
                    return cached_template
                elif hasattr(cached_template, 'source'):
                    # Jinja2模板对象，返回源代码
                    return cached_template.source
                else:
                    return str(cached_template)
            
            # 缓存未命中，从文件加载
            if os.path.exists(self.template_path):
                async with aiofiles.open(self.template_path, 'r', encoding='utf-8') as f:
                    content = await f.read()
                
                # 更新缓存
                await self._update_template_cache(content)
                return content
            else:
                self.logger.warning(f"模板文件不存在: {self.template_path}")
                # 使用默认模板
                default_template = await self._get_default_template()
                await self._update_template_cache(default_template)
                return default_template
        except FileNotFoundError as e:
            self.logger.warning(f"模板文件未找到: {e}")
            default_template = await self._get_default_template()
            await self._update_template_cache(default_template)
            return default_template
        except PermissionError as e:
            self.logger.error(f"模板文件权限错误: {e}")
            default_template = await self._get_default_template()
            await self._update_template_cache(default_template)
            return default_template
        except UnicodeDecodeError as e:
            self.logger.error(f"模板文件编码错误: {e}")
            default_template = await self._get_default_template()
            await self._update_template_cache(default_template)
            return default_template
    
    async def _get_fallback_template(self) -> str:
        """获取纯占位符回退模板（不含Jinja2语法）
        
        当Jinja2不可用时使用的安全模板，只使用简单的{{ key }}占位符，
        不包含任何Jinja2特有的语法（如循环、过滤器等）。
        """
        return """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ title }}</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        body {
            font-family: var(--message-stats-font-family, 'Microsoft YaHei', 'Segoe UI', sans-serif);
            background: linear-gradient(135deg, #E9EFF6 0%, #D6E4F0 100%);
            padding: 30px;
            min-height: 100vh;
        }
        .title {
            text-align: center;
            font-size: 28px;
            color: #1F2937;
            margin-bottom: 25px;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.1);
        }
        .user-list {
            max-width: 800px;
            margin: 0 auto;
            background: rgba(255,255,255,0.9);
            border-radius: 12px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            padding: 20px;
        }
        .user-item {
            display: flex;
            align-items: center;
            padding: 15px;
            border-bottom: 1px solid #E5E7EB;
            transition: transform 0.2s ease;
            border-radius: 8px;
            margin-bottom: 8px;
        }
        .user-item:hover {
            transform: translateX(10px);
            background-color: rgba(59, 130, 246, 0.05);
        }
        .user-item-current {
            display: flex;
            align-items: center;
            padding: 15px;
            border-bottom: 1px solid #E5E7EB;
            transition: transform 0.2s ease;
            background: linear-gradient(135deg, #F3E8FF 0%, #EDE9FE 100%);
            border-radius: 12px;
            margin-bottom: 8px;
            box-shadow: 0 2px 4px rgba(139, 92, 246, 0.1);
        }
        .user-item-current:hover {
            transform: translateX(10px);
            box-shadow: 0 4px 8px rgba(139, 92, 246, 0.2);
        }
        .rank {
            width: 50px;
            height: 50px;
            border-radius: 50%;
            background: linear-gradient(135deg, #3B82F6 0%, #1D4ED8 100%);
            color: white;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 18px;
            font-weight: bold;
            margin-right: 20px;
            box-shadow: 0 2px 4px rgba(59, 130, 246, 0.3);
            transition: transform 0.2s ease;
        }
        .rank:hover {
            transform: scale(1.1);
        }
        .rank-current {
            width: 50px;
            height: 50px;
            border-radius: 50%;
            background: linear-gradient(135deg, #8B5CF6 0%, #7C3AED 100%);
            color: white;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 18px;
            font-weight: bold;
            margin-right: 20px;
            box-shadow: 0 2px 4px rgba(139, 92, 246, 0.3);
            transition: transform 0.2s ease;
        }
        .rank-current:hover {
            transform: scale(1.1);
        }
        .avatar {
            width: 60px;
            height: 60px;
            border-radius: 50%;
            margin-right: 20px;
            border: 3px solid #ffffff;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            transition: transform 0.2s ease;
        }
        .avatar:hover {
            transform: scale(1.05);
        }
        .info {
            flex: 1;
        }
        .name-date {
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 8px;
        }
        .nickname {
            font-size: 18px;
            font-weight: bold;
            color: #1F2937;
        }
        .nickname-with-title {
            max-width: 150px;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }
        .user-title {
            font-size: 12px;
            color: #7C3AED;
            font-weight: 700;
            background: #EDE9FE;
            padding: 2px 6px;
            border-radius: 10px;
            white-space: nowrap;
            flex-shrink: 0;
            margin-left: 6px;
        }
        .date {
            font-size: 14px;
            color: #6B7280;
        }
        .stats {
            display: flex;
            align-items: center;
            justify-content: space-between;
        }
        .count {
            font-size: 16px;
            font-weight: bold;
            color: #3B82F6;
        }
        .percentage {
            font-size: 14px;
            color: #6B7280;
        }
        .footer {
            text-align: center;
            margin-top: 20px;
            color: #6B7280;
            font-size: 14px;
        }
    </style>
</head>
<body>
    <div class="title">{{ group_name }}{% if show_group_id %}[{{ group_id }}]{% endif %}</div>
    <div class="title">{{ title }}</div>
    <div class="user-list">
        {{ user_items }}
    </div>
    <div class="footer">
        <p>🤖 由 AstrBot 发言统计插件生成</p>
        <p>生成时间: {{ current_time }}</p>
        {{ llm_token_info }}
    </div>
</body>
</html>"""

    async def _get_default_template(self) -> str:
        """获取默认HTML模板（优化版本）"""
        # 尝试从缓存获取默认模板
        default_cache_key = 'default_template'
        async with self._cache_lock:
            cached_default = self._template_cache.get(default_cache_key)
        
        if cached_default:
            return cached_default['content']
        
        # 创建优化的默认模板（使用简单占位符）
        default_template = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ title }}</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        body {
            font-family: var(--message-stats-font-family, 'Microsoft YaHei', 'Segoe UI', sans-serif);
            background: linear-gradient(135deg, #E9EFF6 0%, #D6E4F0 100%);
            padding: 30px;
            min-height: 100vh;
        }
        .title {
            text-align: center;
            font-size: 28px;
            color: #1F2937;
            margin-bottom: 25px;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.1);
        }
        .user-list {
            max-width: 800px;
            margin: 0 auto;
            background: rgba(255,255,255,0.9);
            border-radius: 12px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            padding: 20px;
        }
        .user-item {
            display: flex;
            align-items: center;
            padding: 15px;
            border-bottom: 1px solid #E5E7EB;
            transition: transform 0.2s ease;
            border-radius: 8px;
            margin-bottom: 8px;
        }
        .user-item:hover {
            transform: translateX(10px);
            background-color: rgba(59, 130, 246, 0.05);
        }
        .user-item-current {
            display: flex;
            align-items: center;
            padding: 15px;
            border-bottom: 1px solid #E5E7EB;
            transition: transform 0.2s ease;
            background: linear-gradient(135deg, #F3E8FF 0%, #EDE9FE 100%);
            border-radius: 12px;
            margin-bottom: 8px;
            box-shadow: 0 2px 4px rgba(139, 92, 246, 0.1);
        }
        .user-item-current:hover {
            transform: translateX(10px);
            box-shadow: 0 4px 8px rgba(139, 92, 246, 0.2);
        }
        .rank {
            width: 50px;
            height: 50px;
            border-radius: 50%;
            background: linear-gradient(135deg, #3B82F6 0%, #1D4ED8 100%);
            color: white;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 18px;
            font-weight: bold;
            margin-right: 20px;
            box-shadow: 0 2px 4px rgba(59, 130, 246, 0.3);
            transition: transform 0.2s ease;
        }
        .rank:hover {
            transform: scale(1.1);
        }
        .rank-current {
            width: 50px;
            height: 50px;
            border-radius: 50%;
            background: linear-gradient(135deg, #EF4444 0%, #DC2626 100%);
            color: white;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 18px;
            font-weight: bold;
            margin-right: 20px;
            box-shadow: 0 2px 4px rgba(239, 68, 68, 0.3);
            transition: transform 0.2s ease;
        }
        .rank-current:hover {
            transform: scale(1.1);
        }
        .avatar {
            width: 60px;
            height: 60px;
            border-radius: 50%;
            margin: 0 20px;
            border: 3px solid #3B82F6;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .info {
            flex: 1;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .name-date {
            display: flex;
            flex-direction: column;
        }
        .nickname {
            font-size: 20px;
            color: #1F2937;
            font-weight: 500;
            line-height: 1.2;
        }
        .date {
            color: #6B7280;
            font-size: 14px;
            margin-top: 4px;
        }
        .stats {
            text-align: right;
            font-size: 18px;
            min-width: 120px;
        }
        .count {
            color: #EF4444;
            font-weight: bold;
        }
        .percentage {
            color: #22C55E;
            font-size: 16px;
        }
    </style>
</head>
<body>
    <div class="title">{{ group_name }}{% if show_group_id %}[{{ group_id }}]{% endif %}</div>
    <div class="title">{{ title }}</div>
    <div class="user-list">
        {{ user_items }}
    </div>
</body>
</html>
"""
        
        # 缓存默认模板
        async with self._cache_lock:
            self._template_cache[default_cache_key] = {
                'content': default_template,
                'template': self.jinja_env.from_string(default_template) if self.jinja_env else None
            }
        
        return default_template
    
    async def clear_cache(self):
        """清理模板缓存"""
        async with self._cache_lock:
            self._template_cache.clear()
            self.logger.info("模板缓存已清理")
    
    async def get_performance_stats(self) -> Dict[str, Any]:
        """获取性能统计信息"""
        cache_stats = await self.get_cache_stats()
        
        return {
            'cache_stats': cache_stats,
            'cached_templates': list(self._template_cache.keys()),
            'jinja2_enabled': JINJA2_AVAILABLE and self.jinja_env is not None,
            'template_path': str(self.template_path),
            'template_exists': os.path.exists(self.template_path) if self.template_path else False
        }
    
    async def optimize_for_batch_generation(self):
        """为批量生成优化配置"""
        # 预热缓存
        await self._preload_templates()
        
        # 启用更激进的缓存策略
        if self.jinja_env:
            # Jinja2环境已经配置了缓存
            self.logger.info("批量生成优化已启用")
    
    async def _load_user_item_macro_template(self):
        """加载用户条目宏模板（异步版本）"""
        try:
            macro_path = Path(__file__).parent.parent / "templates" / "user_item_macro.html"
            if os.path.exists(macro_path):
                async with aiofiles.open(macro_path, 'r', encoding='utf-8') as f:
                    macro_content = await f.read()
                
                # 创建环境并加载宏模板
                env = Environment(
                    loader=FileSystemLoader(str(macro_path.parent)),
                    autoescape=select_autoescape(['html', 'xml'])
                )
                return env.from_string(macro_content)
        except Exception as e:
            self.logger.warning(f"加载用户条目宏模板失败: {e}")
        
        return None
