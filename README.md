![:name](https://count.getloli.com/@astrbot_plugin_message_stats?name=astrbot_plugin_message_stats&theme=green&padding=7&offset=0&align=top&scale=1&pixelated=1&darkmode=auto&prefix=0)

# AstrBot 群发言统计插件

> 🤖 **此插件由AI辅助生成**

一个功能强大的AstrBot群消息统计插件，支持自动统计群成员发言次数并生成排行榜。

![Preview](https://s41.ax1x.com/2026/05/22/pmpwlSx.png) 

## 🚀 安装说明

### 方式一：直接下载
1. 下载插件压缩包 `astrbot_plugin_message_stats.zip`
2. 解压到AstrBot插件目录：`/AstrBot/data/plugins/`
3. 重启AstrBot

### 方式二：Git克隆
```bash
cd /AstrBot/data/plugins/
git clone https://github.com/xiaoruange39/astrbot_plugin_message_stats.git
```

## 📖 使用方法

### 基础命令

#### 查看排行榜
- `#发言榜` - 查看总发言排行榜
- `#今日发言榜` - 查看今日发言排行榜  
- `#本周发言榜` - 查看本周发言排行榜
- `#本月发言榜` - 查看本月发言排行榜
- `#本年发言榜` - 查看本年发言排行榜
- `#去年发言榜` - 查看去年发言排行榜
- `#昨日发言榜` - 查看昨日发言排行榜（别名：`#昨天发言榜`、`#昨日排行`）

#### 管理命令
- `#设置发言榜数量 [数量]` - 设置排行榜显示人数（1-100）
- `#设置发言榜图片 [模式]` - 设置显示模式（1=图片，0=文字）
- `#清除发言榜单` - 清除本群发言统计数据

#### 个人统计命令
- `#查看发言` - 查看自己或指定群成员的发言统计（支持@和QQ号）
- `#查询发言` - `#查看发言` 的别名
- `#我的发言` - `#查看发言` 的别名

#### 缓存管理命令
- `#刷新发言榜群成员缓存` - 手动刷新群成员缓存
- `#发言榜缓存状态` - 查看缓存状态

#### 定时功能命令
- `#发言榜定时状态` - 查看定时任务状态
- `#手动推送发言榜` - 手动推送排行榜
- `#设置发言榜定时时间 [时间]` - 设置定时推送时间
- `#设置发言榜定时群组 [群号]` - 添加定时推送群组
- `#设置发言榜定时群组 [群号1] [群号2]` - 添加多个定时推送群组
- `#删除发言榜定时群组 [群号]` - 删除定时推送群组
- `#启用发言榜定时` - 启用定时推送
- `#禁用发言榜定时` - 禁用定时推送
- `#设置发言榜定时类型 [类型]` - 设置定时推送类型

### 使用示例

```
#发言榜
总发言排行榜
发言总数: 156
━━━━━━━━━━━━━━
第1名：小明·45次（占比28.85%）
第2名：小红·32次（占比20.51%）
第3名：小刚·28次（占比17.95%）
```

```
#设置发言榜数量 10
排行榜显示人数已设置为 10 人！
```

```
#设置发言榜图片 1
排行榜显示模式已设置为 图片模式！
```

```
#设置发言榜定时时间 20:00
定时推送时间已设置为 20:00
```

## ⚙️ 配置说明

### 插件配置

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `theme` | string | `default` | 排行榜主题风格：`default`（手绘卡通浅色）、`cartoon_light`（手绘卡通浅色）、`cartoon_dark`（手绘卡通深色）、`liquid_glass`（液态玻璃）、`liquid_glass_dark`（液态玻璃暗色） |
| `font_path` | string | `` | 自定义图片字体路径，支持绝对路径或相对插件目录的相对路径；留空使用主题默认字体，路径无效时自动回退默认字体 |
| `auto_theme_switch` | bool | `false` | 是否根据时间自动切换主题（浅色/深色），启用后会覆盖手动设置的 theme |
| `theme_switch_light_time` | string | `06:00` | 浅色主题开始时间，格式 HH:MM |
| `theme_switch_dark_time` | string | `18:00` | 深色主题开始时间，格式 HH:MM |
| `rand` | int | `20` | 排行榜显示人数（1-100） |
| `render_mode` | string | `t2i` | 排行榜图片渲染方式：`t2i`（AstrBot 文转图服务，按模板宽度截图且不启动本地 Chromium）或 `text`（纯文字）。T2I 失败时回退文字模式 |
| `t2i_endpoint` | string | `` | 可选的 T2I 服务端点；留空继承 AstrBot 全局 `t2i_endpoint`。本机服务示例：`http://localhost:8999/text2img` |
| `detailed_logging_enabled` | bool | `true` | 是否开启详细日志记录 |
| `timer_enabled` | bool | `false` | 是否启用定时推送排行榜功能 |
| `timer_push_time` | string | `09:00` | 定时推送时间（支持 HH:MM 或 cron 格式） |
| `timer_target_groups` | list | `[]` | 定时推送目标群组ID列表（支持群号或 unified_msg_origin 格式） |
| `timer_rank_type` | string | `daily` | 定时推送排行榜类型：`daily`/`total`/`weekly`/`monthly`/`yearly`/`lastyear` |
| `milestone_enabled` | bool | `false` | 发言里程碑推送，用户发言达到里程碑次数时自动推送排行榜 |
| `milestone_targets` | list | `[666, 1000, 2333, 5000, 6666, 10000, 23333]` | 触发推送的发言次数里程碑列表 |
| `blocked_users` | list | `[]` | 屏蔽用户列表 |
| `blocked_groups` | list | `[]` | 屏蔽群聊列表 |
| `tg_bot_token` | string | `` | Telegram Bot Token，填写后可获取TG用户真实头像 |
| `dc_bot_token` | string | `` | Discord Bot Token，填写后可获取DC用户真实头像 |
| `llm_enabled` | bool | `false` | 启用 LLM 发言头衔分析，定时推送排行榜时生成个性化头衔 |
| `llm_provider_id` | string | `` | LLM Provider ID，留空使用默认 |
| `llm_system_prompt` | text | 默认提示词 | 头衔生成提示词模板，可自定义风格和颜色 |
| `llm_max_retries` | int | `2` | LLM 调用失败时的重试次数 |
| `llm_min_daily_messages` | int | `0` | 每日发言次数最小值，低于此值不生成头衔 |
| `llm_enable_on_manual` | bool | `false` | 手动查询排行榜时也调用LLM分析（会产生Token消耗） |

### 配置方式
1. 通过AstrBot Web面板配置（推荐）
2. 通过命令配置
3. 编辑配置文件：`data/config.json`

### 自定义字体

在 Web 面板的 `font_path` 中填写字体文件路径即可让排行榜、个人统计卡片和里程碑卡片优先使用该字体。支持 `.ttf`、`.otf`、`.woff`、`.woff2`、`.ttc` 字体文件。

- 留空：使用当前主题模板的默认字体。
- Pages 上传：在发言统计面板的“字体管理”中上传字体后会自动启用，并同步写入 `font_path`，Web 配置面板也能看到当前路径。
- 绝对路径：例如 `C:\\Windows\\Fonts\\msyh.ttc`。
- 相对路径：相对插件目录查找，也会尝试插件目录下的 `fonts/` 和插件数据目录下的 `resources/fonts/`。
- Pages 管理：可在面板中选择已上传字体、删除字体或恢复默认；删除当前使用字体时会自动回退默认字体。
- 路径无效或读取失败：记录 warning 后自动回退默认字体，不影响图片生成。
- 字体文件修改后会根据路径、修改时间和文件大小自动刷新缓存。

## 📁 文件结构

```
astrbot_plugin_message_stats/
├── main.py                 # 主程序文件
├── metadata.yaml          # 插件元数据
├── README.md              # 说明文档
├── requirements.txt       # 依赖包
├── config.yaml           # 配置文件
├── example_config.json   # 配置示例
├── _conf_schema.json     # 配置架构（Web面板配置定义）
├── data/                 # 数据目录
│   ├── config.json       # 用户配置
│   └── cmd_config.json   # 命令配置
├── templates/            # 模板目录
│   ├── __init__.py
│   ├── rank_template.html # 排行榜默认模板
│   ├── rank_template_cartoon_light.html # 手绘卡通浅色主题
│   ├── rank_template_cartoon_dark.html # 手绘卡通深色主题
│   ├── rank_template_liquid_glass.html # 液态玻璃主题模板
│   └── rank_template_liquid_glass_dark.html # 液态玻璃暗色主题模板
└── utils/                # 工具模块
    ├── __init__.py
    ├── data_manager.py   # 数据管理
    ├── data_stores.py    # 数据存储
    ├── date_utils.py     # 日期工具
    ├── file_utils.py     # 文件工具
    ├── image_generator.py # 图片生成
    ├── models.py         # 数据模型
    ├── platform_helper.py # 跨平台兼容辅助
    ├── timer_manager.py  # 定时管理
    └── validators.py     # 数据验证
```

## 🌐 跨平台支持

本插件现已支持以下平台：
- **QQ（OneBot）** - 完整功能支持
- **Telegram** - 完整功能支持
- **Discord** - 完整功能支持
- **飞书（Lark/Feishu）** - 完整功能支持

## 📝 更新日志

### 未发布

- ✅ 图片渲染直接调用兼容 T2I 的 `/generate` HTML 接口，移除本地 Chromium 截图链路
- ✅ T2I 直接返回图片 URL，并成对传递视口宽高以固定模板画布，避免服务忽略宽度后产生右侧灰色填充
- ✅ 删除 Playwright 与 Pillow 依赖，不再生成或裁切本地临时图片

### v2.1.5 (2026-06-27)
- ✅ 新增 `render_mode` 渲染方式配置（playwright / t2i / text）
- ✅ 双向降级链：图片模式下 playwright 和 t2i 自动互相降级
- ✅ 降级消息提示

### v2.0.6 (2026-05-23)
- ✅ Pages 面板新增字体上传、选择、删除和恢复默认
- ✅ Pages 字体选择与 Web 配置 `font_path` 同步

### v2.0.5 (2026-05-23)
- ✅ 新增自定义字体配置（font_path）
- ✅ 优化自定义字体渲染稳定性与并发缓存

### v2.0.4 (2026-05-23)
- ✅ 修复里程碑自动推送群名缺失

### v2.0.3 (2026-05-22)
- ✅ 新增 #昨日发言榜 命令
- ✅ 新增 #查看发言 命令（个人专属统计卡片）
- ✅ 戳一戳计入发言统计
- ✅ 启动时清理残留临时文件

### v2.0.2 (2026-05-21)
- ✅ 手绘卡通主题（cartoon_light/cartoon_dark）

### v2.0.1 (2026-05-21)
- ✅ 修复 #设置发言榜数量 命令报错
- ✅ 修复 WebUI 排行榜输出模式选项不可选

### v1.9.1 (2026-05-07)
- ✅ 跨平台真实头像获取
- ✅ i18n 国际化文件全面优化
- ✅ 新增 tg_bot_token/dc_bot_token 配置
- ✅ LLM 头衔持久化

### v1.9.0 (2026-05-05)
- ✅ 新增插件Pages页面
- ✅ 新增群组数据删除功能(Pages页面)
- ✅ 群名称持久化缓存
- ✅ 多项错误修复

### v1.8.7 (2026-05-04)
- ✅ LLM 头衔配色大师

### v1.8.2 (2026-05-03)
- ✅ 优化浏览器资源占用
- ✅ 修复数据丢失问题
- ✅ 新增发言里程碑推送
- ✅ 新增更新日志文档

### v1.7.4 (2026-01-02)
- ✅ 屏蔽群聊列表配置
- ✅ 本年/去年发言榜指令

### v1.6.5 (2025-11-24)
- ✅ 指令别名支持
- ✅ 昵称同步修复
- ✅ 屏蔽用户列表配置

### v1.6.0 (2025-11-05)
- ✅ 完善定时推送
- ✅ 增强缓存管理

### v1.0 (2025-11-02)
- ✅ 完整功能发布

### v0.9 (之前版本)
- 基础消息统计与排行榜

## 🤝 贡献指南

欢迎提交Issue和Pull Request！

## 📄 许可证

本项目采用 MIT 许可证。

## 👨‍💻 作者

**xiaoruange39**
- GitHub: [@xiaoruange39](https://github.com/xiaoruange39)
- 插件开发：AstrBot生态贡献者
- QQ群：[QQ群](https://qm.qq.com/q/8kdJ2Bzf6S)

## 🙏 致谢

感谢以下项目和插件的参考：
- [AstrBot框架](https://astrbot.app/) - 强大的多平台聊天机器人框架
- [yunzai-plugin-example](https://github.com/KaedeharaLu/yunzai-plugin-example) - 原始插件基础架构参考

---

**如果这个插件对您有帮助，请给个⭐支持一下！**
