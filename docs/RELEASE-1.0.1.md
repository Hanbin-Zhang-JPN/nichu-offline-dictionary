离线日中词典 v1.0.1。

包含 112,182 个不同词头、120,749 个可查询词条、147,559 个义项和 12,492 条结构化用例／引文。支持日语、假名、罗马字、源活用词形、简繁中文反查、收藏和学习记录备份。

本次修复 Windows Git 默认换行转换导致 OpenCC 词表 SHA-256 校验不一致的问题：仓库通过 `.gitattributes` 固定数据文本为 LF，并为 Windows 启动脚本保留 CRLF。自动检查更新到官方 Node 24 运行时支持的 Actions 版本。

ZIP 包附带完整数据快照和预建 SQLite 索引。解压后需要已安装的 Python 3.10+，在目录执行 `python3 -m nichu.server`；Windows 可双击 `start.bat`，macOS 可双击 `start.command`。不需要联网或安装第三方 Python 依赖。

数据源为中文维基词典的 2026-10-01 dump（Kaikki 提取日期 2026-10-02），词库采用 CC BY-SA 4.0，应用采用 MIT。字段覆盖率与范围说明见 README 和数据报告。`SHA256SUMS` 提供 ZIP 校验值。
