# 更新日志

## 未发布

### ♻️ 渲染链路重构
- **仅保留 AstrBot T2I**：排行榜、个人统计、里程碑和定时推送直接调用 T2I 的 `/generate` HTML 接口生成图片 URL，不再启动本地 Chromium。
- **画布尺寸修复**：截图前成对传递模板宽高和 `normal` 设备缩放，消除远端服务忽略单独宽度、回退默认视口造成的右侧灰色填充。
- **轻量依赖**：移除 Playwright、Pillow 以及本地截图/裁切/临时文件清理逻辑。

## v2.1.9 (2026-07-11)

### ✨ 新功能
- **指定日期发言榜**：支持查询指定单日或日期区间的发言榜，可使用“发言榜 2026年6月1日”或“2026年5月30日-2026年6月1日发言榜”等格式

### 🐛 Bug 修复
- **后台命令列表显示优化**：指定日期自然语言查询改由消息监听器识别，不再将完整正则表达式显示为命令名，同时保持原有查询语法可用

## v2.1.8 (2026-07-11)

### 🐛 Bug 修复
- **定时昨日榜支持补全**：补齐 `yesterday` 及“昨日榜/昨日/昨天”的类型解析、昨日日期范围和榜单标题，修复定时任务启动时报“无效的排行榜类型: yesterday”的问题
- **定时空数据回退修正**：仅今日榜在无数据时回退昨日，周榜、月榜等其他类型不再错误回退；今日榜回退后同步使用昨日榜标题
- **拆分后事件监听修复**：恢复 `extract_group_message_snapshot` 导入，修复自动消息监听时报 `NameError` 的问题
- **AstrBot Handler 绑定兼容性**：插件类保持直接继承 `Star`，在注册前装配拆分后的功能方法，修复消息监听和排行榜命令参数数量不匹配的问题

### ♻️ 代码重构
- 将 Web 面板、消息统计和排行榜渲染能力拆分到三个功能模块，降低 `main.py` 体积，同时保留 AstrBot 处理函数集中注册

## v2.1.7 (2026-07-10)

### 🐛 Bug 修复
- **AstrBot v4.26.5 T2I 渲染兼容性**：调用 `Star.html_render()` 时显式传入空模板数据，修复排行榜使用 t2i 模式时报 `missing 1 required positional argument: 'data'` 并回退 Playwright 的问题

- **T2I 自适应画布**：复用 Playwright 的容器宽度规则，支持 PNG/JPEG 两级渲染、本地结果校验与右侧空白裁切，保持排行榜内容的自然高度

## v2.1.6 (2026-06-29)

### 🐛 Bug 修复
- **Chromium 自动安装漏装系统依赖**：`install chromium` 成功后现在也强制执行 `install-deps`，修复 Docker/Linux 环境下二进制已安装但缺 `libnspr4.so` 等库导致浏览器无法启动的问题

## v2.1.5 (2026-06-27)

### ✨ 新功能
- **渲染方式配置**：新增 `render_mode` 配置项（playwright / t2i / text），可选本地浏览器渲染或 AstrBot 官方文转图服务
- **双向降级链**：图片模式下 playwright 和 t2i 互相作为 fallback，均失败自动降级纯文字
- **降级消息提示**：渲染降级时在聊天中告知用户当前状态

### 🐛 Bug 修复
- **Changelog 未更新**

## v2.1.4 (2026-06-21)

### ✨ 新功能
- **自动安装 Chromium 浏览器**：图片生成失败时自动运行 `playwright install chromium`，无需手动操作
- **图片失败消息提醒**：浏览器安装失败时，在聊天中提示用户并自动降级为文字排行

### 🎨 主题统一
- **卡通风格覆盖个人面板**：新建 `personal_stats_cartoon_light.html` 和 `personal_stats_cartoon_dark.html`
- `generate_personal_stats_image()` 现在根据主题自动选择模板

### 🧹 规范清理
- 删除 v1.0 旧格式 `config.yaml` 和 `example_config.json`（无代码引用）
- 移除未使用的 `bleach>=6.0.0` 依赖
- `_conf_schema.json` theme 选项精简为 5 项（删除已废弃的 bubble 主题）
- `image_generator.py` 清理 3 处 bubble 主题映射遗留
- `personal_stats.html` 补充 Content-Security-Policy meta 标签

### 🐛 Bug 修复
- **Chromium 残留文件清理**：`_cleanup_stale_temp_files()` 现在同时清理 Chromium 锁文件（之前 `isdir()` 跳过了文件类型的 `.org.chromium.Chromium.*`）

## v2.1.3 (2026-06-16)

### 🐛 Bug 修复
- **修复里程碑卡片「击败活跃群友百分比」计算错误**：此前传入模板的 `percentage` 实际是「发言占比」（个人发言数 ÷ 全群总发言数），却被显示为「击败了群内 X% 的活跃群友」，二者含义完全不同（例如排名第 1 但仅占全群 8% 发言时会错显为「击败 8%」）。现改为基于群内排名计算真实百分位：新增 `_calc_beat_percentage()`，按 `(活跃群友数 - 排名) / (活跃群友数 - 1) × 100` 计算，排名第 1 → 100%、末位 → 0%，自动推送与 `发言榜里程碑` 命令两条路径均已修正。

## v2.1.1 (2026-06-05)

### 🐛 Bug 修复
- **修复 `_cleanup_stale_temp_files` 遗漏 Chromium 临时目录清理**：启动清理仅匹配 `playwright-*`/`playwright_*`/`msgstats_pw_*` 三种前缀，遗漏了 Chromium 原生 user data dir（`org.chromium.Chromium.*`）、artifacts（`playwright-artifacts-*`）、chromium dev profile（`playwright_chromiumdev_profile-*`）和 PulseAudio socket（`pulse-*`），导致容器 OOM/kill -9/断电等异常终止后这些空目录永久残留。

## v2.1.0 (2026-06-04)

### 🐛 Bug 修复
- **修复指令触发后额外调用 LLM 浪费 Tokens**（#38）：插件注册了 `EventMessageType.ALL` 全量监听器会使每条消息 `is_wake=True`，导致 `今日发言榜` 等指令推送榜单后，框架仍会默认再调用一次 LLM 进行 AI 回复（napcat/aiocqhttp 平台尤为明显）。已修复：在全量监听器跳过命令消息时关闭默认 LLM，并参考 `astrbot_plugin_wzl_mcstatuspro` 在排行榜指令完成后追加 `event.stop_event()`，彻底终止后续事件传播；该处理不影响插件自身用于生成头衔的 LLM 请求。

## v2.0.7 (2026-05-29)

### 🎨 样式优化
- **修复卡通主题标题换行错位**：`cartoon_light` / `cartoon_dark` 主题在日期 `]` 处断行，让日期与「发言榜单」分两行显示，避免「发言榜」与「单」被拦腰拆开。

## v2.0.6 (2026-05-23)

### ✨ 新功能
- **新增 Pages 字体管理**：发言统计面板支持上传 `.ttf` / `.otf` / `.woff` / `.woff2` / `.ttc` 字体文件、选择当前字体、删除已上传字体和一键恢复默认字体；选择结果会同步写入 `font_path` 配置，Web 配置面板可同步查看。

## v2.0.5 (2026-05-23)

### ✨ 新功能
- **新增自定义字体配置**：支持通过 `font_path` 配置生成图片所用字体，路径可填写绝对路径或相对路径，排行榜、个人统计卡片和里程碑卡片均会优先使用该字体。

### 🔧 性能优化
- **优化自定义字体加载**：字体文件改为 base64 内嵌并等待浏览器字体加载完成后截图，提升 Playwright 渲染稳定性；同时按字体路径、修改时间和文件大小缓存字体 CSS，避免并发生成图片时重复读取和编码字体文件。

## v2.0.4 (2026-05-23)

### 🐛 Bug 修复
- **修复里程碑自动推送群名缺失**：自动触发里程碑卡片时优先读取已持久化的群名缓存，避免无事件对象场景下只显示 `群{group_id}`。

## v2.0.3 (2026-05-22)

### ✨ 新功能
- **新增 `#昨日发言榜` 命令**：支持查看昨日发言排行榜，别名 `#昨天发言榜` / `#昨日排行` / `#昨日水群榜` / `#昨日B话榜`
- **新增 `#查看发言` 命令**：支持查询自己或群内其他成员的发言统计，生成 Liquid Glass 毛玻璃风格的个人专属统计卡片（支持深浅色自适应）
- **戳一戳计入发言统计**：通过 `@filter.on_astrbot_loaded()` 钩子订阅底层 `on_notice` 事件，别人戳 Bot 时自动计入发言统计（仅 aiocqhttp 平台）

### 🎨 样式优化
- **个人卡片采用 Liquid Glass 毛玻璃配色**：`backdrop-filter: blur(16px)` 半透明卡片，浅色/深色模式自动适配，排名移至右上角独立圆角方块

### 🐛 Bug 修复
- **修复 LLM 头衔重新生成逻辑**：改用总发言增量代替当前周期发言数判断阈值，避免每次查榜重复触发 LLM 生成
- **修复个人卡片模板渲染失败**：修复 `jinja_env.get_template` 因缺少 FileSystemLoader 而报错的问题

### 🧹 代码清理
- **启动时清理残留临时文件**：新增 `_cleanup_stale_temp_files()`，插件初始化时自动清理超过10分钟的历史临时图片文件

## v2.0.2 (2026-05-21)

### ✨ 新功能
- **手绘卡通主题系列**：`premium_light` / `premium_dark` 替换为 `cartoon_light` / `cartoon_dark` 两款手绘卡通风格排行榜主题，采用 ZCOOL KuaiLe 卡通字体、不规则圆角、粗边框阴影偏移、星星装饰等手绘元素

## v2.0.1 (2026-05-21)

### 🐛 Bug 修复
- **修复 `#设置发言榜数量` 命令报错**：`MAX_RANK_COUNT` 类常量缺失导致 `self.MAX_RANK_COUNT` 触发 `AttributeError`，现已补全
- **修复 WebUI 排行榜输出模式选项不可选**：`_conf_schema.json` 中 `if_send_pic` 使用了不支持的 `value`/`label` 对象格式且 `default` 类型不匹配，改用标准 `options` 数组格式

## v2.0.0 (2026-05-20)

### ✨ 新功能
- **Premium 高级主题系列**：新增 `premium_light` / `premium_dark` 两款毛玻璃质感排行榜主题，支持七彩渐变标题、发光阴影、阶梯式前三名放大效果、发言占比填充条等高级视觉特性
- **自动主题切换双向映射**：`_get_auto_theme()` 新增 `light_theme_map` 深→浅映射表，`premium_dark` / `liquid_glass_dark` 在浅色时段自动切回对应的浅色版本，实现与 `liquid_glass` 一致的双向对称切换
- **Header 排版全面升级**：标题字号 32px → 40px，发言总数 36px → 44px，标签样式增强，Header 内边距和间距优化，垂直居中更完美

### 🐛 Bug 修复
- **修复表情包/语音/图片不计数**：`auto_message_listener` 使用 `if not message_str or ...` 判断导致非文本消息（`message_str` 为空）被直接跳过统计，改为 `if message_str and ...` 后只跳过命令消息，表情包/语音/图片等非文本消息正常计数
- **修复定时触发时多重发送问题**：将 `utils/timer_manager.py` 的文件锁机制修改为跨进程唯的 UUID，彻底解决了当插件存在多个实例时，锁失效导致发送重复图片的问题
- **去除多余的排行榜前缀标题**：移除了 `main.py` 和 `timer_manager.py` 生成标题时如"今日"、"本周"等前缀字样，消除与日期的重复

## v1.9.8 (2026-05-10)

### 🐛 Bug 修复

- **修复 `#设置发言榜数量` 命令报错**：`MAX_RANK_COUNT` 类常量缺失导致 `self.MAX_RANK_COUNT` 触发 `AttributeError`，现已补全
- **修复 WebUI 排行榜输出模式选项不可选**：`_conf_schema.json` 中 `if_send_pic` 使用了不支持的 `value`/`label` 对象格式且 `default` 类型不匹配，改用标准 `options` 数组格式

## v1.9.7 (2026-05-10)

### ✨ 新功能

- **Web 面板全新 UI 升级**：发言统计面板新增 Dock 栏时段切换（总/日/周/月/年）、群组迷你折线图（近7天发言趋势）、群组按总发言数排序、切换动画优化

### 🐛 Bug 修复

- **LLM 头衔频繁触发**：`llm_title` 存为空字符串 `""` 时被 `not u.llm_title` 误判为无头衔，导致每次都重新生成。已修复：改用 `bool(u.llm_title and u.llm_title.strip())` 判断有效头衔
- **`page_stats` API 群组列表顺序随机**：已修复：按总发言数降序排序

## v1.9.4 (2026-05-09)


### 🐛 Bug 修复

- **定时/手动推送排行榜类型硬编码**：`_push_to_group()` 中硬编码 `RankType.DAILY`，导致用户在 WebUI 设置的 `timer_rank_type` 配置完全无效。已修复：改为读取 `config.timer_rank_type`，定时推送和手动推送均可使用用户配置的排行榜类型。
- **`#手动推送发言榜` 群组ID格式解析错误**：当 `timer_target_groups` 中存储 `Amy:GroupMessage:1081839722` 格式时，`manual_push()` 直接传入 `_push_to_group()` 导致 `get_group_data()` 校验失败。已修复：统一添加 unified_msg_origin 格式的群组 ID 提取逻辑。
- **LLM 头衔生成重复调用浪费 Tokens**：`_push_to_group()` 中先对全体用户调用 `llm_analyzer.analyze_users()` 后才筛选已有持久化头衔的用户，导致每次推送都浪费一次 LLM 调用。已修复：先筛选出无头衔用户，只对这部分用户调用 LLM。

### 🧹 代码清理

- **移除冗余 `pydantic` 依赖**：插件中未使用 pydantic，且 AstrBot 框架已自带，`requirements.txt` 中已移除。
- **`metadata.yaml` 添加 `astrbot_version` 声明**：添加 `astrbot_version: ">=4.16"`，确保版本兼容性检查。

## v1.9.3 (2026-05-07)

### 🔐 安全改进

- **管理命令增加管理员权限限制**：为发言榜配置、清空数据、刷新缓存、手动推送和定时推送管理命令添加 `@filter.permission_type(filter.PermissionType.ADMIN)`，避免普通群成员修改配置或清除统计数据。

## v1.9.2 (2026-05-07)

### 🐛 Bug 修复

- **临时文件泄漏全面修复**：`_check_milestone()`、`show_my_milestone()`、`_push_to_group()` 三处清理代码不在 try/finally 中，send_message 抛异常时跳过清理导致 tmp 文件残留。已修复：全部改用 try/finally 确保清理。
- **异常关闭时 tmp 文件残留**：插件被 kill -9/OOM/断电时 finally 不会执行。已修复：新增 `_cleanup_stale_temp_files()`，启动时扫描清理。
- **删除冗余的 `_calculate_daily_rank` 方法**：与 `_calculate_period_rank_optimized` 逻辑重复，统一走批量优化路径。
- **`image_generator.py` 缺少 `await`**：`_load_user_item_macro_template()` 调用缺少 `await`，导致用户条目宏模板无法正确加载。
- **`data_manager.py` 不完整语句**：`cleanup_old_data()` 方法中 `except (ValueError, TypeError): self` 为无意义语句。
- **`image_generator.py` `await` 在同步方法中**：`_generate_user_item_html_safe()` 是同步方法，错误地使用了 `await`，导致插件加载报错 `await outside async function`。
- **Web 面板头衔为空**：`page_stats` API 读取了运行时字段 `display_title`，持久化存储的是 `llm_title`，Web 页面直接读文件时头衔为空。
- **Web 面板头衔颜色缺失**：`page_stats` 未返回 `title_color` 字段，前端用固定 CSS 颜色渲染，与排行榜图片不一致。
- **Web 设置中 llm_system_prompt 为空**：用户保存配置后空值被持久化，升级插件也不会被 schema 默认值覆盖。

### 🔧 性能优化

- **`_is_blocked_user/group` 改用 set 缓存**：将屏蔽用户/群聊列表预缓存为 `set`，O(n) 列表遍历 → O(1) 集合查找。
- **`_check_milestone` 里程碑 set 缓存**：将 `milestone_targets` 缓存为 `_milestone_set`，避免每次创建 O(n) 的 set。
- **切换为 orjson**：替换标准库 `json` 为 `orjson`，序列化/反序列化性能提升 2-5 倍。

### 🧹 代码简化与清理

- **简化命令方法的异常处理**：将 `_record_message_stats`、`set_rank_count` 等方法的 11 个 `except` 子句合并为统一的 `except Exception`，代码缩减 60+ 行。
- **删除未使用的 `_handle_command_exception` 方法**：该公共异常处理方法从未被调用，已删除。
- **清理重复的局部 import**：删除 `_load_unified_msg_origins`、`_save_unified_msg_origins`、`_load_group_names`、`_save_group_names` 中的 `import json`，以及 `_check_milestone` 中的 `import aiofiles`。
- **`_conf_schema.json` 类型统一**：`if_send_pic` 配置项改用 `{value, label}` 格式，默认值改为 int 类型 0/1。

### ✅ 新增测试

- **添加单元测试**：新增 `test_plugin.py`，覆盖数据模型、验证器、缓存状态等核心逻辑。

## v1.9.1 (2026-05-07)

- 跨平台真实头像获取（TG Bot API / Discord CDN）
- i18n 国际化文件全面优化
- 新增 `tg_bot_token` / `dc_bot_token` 配置项
- 新增 `aiohttp>=3.9.0` 依赖
- LLM 头衔持久化，重启后保留
- LLM 头衔稳定不变，新增用户才触发 LLM
- 头像跨平台支持（QQ qlogo / TG/DC 彩色文字回退）
- 定时任务改用文件锁防止重复推送
- 国际化文案覆盖问题修复

## v1.9.0 (2026-05-05)


- Web 数据管理面板大升级
- 群组数据删除功能
- 群名称持久化缓存
- 多项 Bug 修复
- Web 面板支持跟随系统深色/浅色模式

## v1.8.8 (2026-05-05)

- 放宽排行榜昵称显示限制
- 修复图片生成失败时 tmp 文件积累
- 修复手动查询里程碑后 tmp 文件不清理
- unified_msg_origin 持久化

## v1.8.7 (2026-05-04)

- LLM 头衔配色大师
- 修复定时推送头衔颜色丢失
- 修复 LLM 头衔不显示的问题
- 修复头衔显示为字典字符串
- 修复头衔颜色硬编码
- 修复头衔徽章垂直不对齐
- LLM 分析范围与排行榜显示人数绑定
- 修复 Fallback 渲染路径忽略头衔颜色
- 优化 Web 面板配置文案

## v1.8.5 (2026-05-04)

- 修复 `_handle_command_exception` 缺少 yield
- 修复昵称双重 HTML 转义
- 修复 TG 负数用户 ID 崩溃
- 修复定时推送没有数据
- 修复群组锁清理条件缺陷
- dirty_cache 添加大小上限

## v1.8.2 (2026-05-03)

- 修复数据丢失问题
- 修复今日发言榜无法使用
- 浏览器懒加载与高并发支持
- 按天聚合字典存储优化
- 延迟批量写入优化
- 发言里程碑推送
- 新增更新日志文档
- 紧凑 JSON 格式，文件体积减少约 50%
