# 词库内容许可与归属

`data/dictionary.jsonl.gz` 中的文字由**中文维基词典贡献者**提供。源页面：`https://zh.wiktionary.org/wiki/{词头}`；每个页面的历史页用于追溯作者。应用每个词条都展示来源链接，未修改的原始记录保留在压缩快照中。

来源说明：[中文维基词典版权信息](https://zh.wiktionary.org/wiki/Wiktionary:版权信息)。该站文本按 CC BY-SA 4.0 与 GFDL 双重许可提供；本项目选择 **Creative Commons Attribution-ShareAlike 4.0 International（CC BY-SA 4.0）** 分发词库和其派生索引。

许可全文：[licenses/CC-BY-SA-4.0.txt](licenses/CC-BY-SA-4.0.txt)；官方链接：https://creativecommons.org/licenses/by-sa/4.0/ 。代码的 MIT 许可不覆盖词典文本。

提取与分发来源：**Tatu Ylonen 等，Wiktextract / Kaikki.org**。

- [数据说明与下载](https://kaikki.org/zhwiktionary/rawdata.html)
- [Wiktextract 项目](https://github.com/tatuylonen/wiktextract)
- 上游研究引用：Tatu Ylonen. *Wiktextract: Wiktionary as Machine-Readable Structured Data.* LREC 2022, pp. 1317–1325。

本项目的改动：筛选日语 `lang_code=ja`；完全相同的 JSON 记录去重；JSON 键排序；压缩；生成 SQLite 索引与搜索别名；提取源 ruby、假名字段、发音字段和明确的 `词头【假名】` 读音；中文简体转换作为显示和检索视图。源文本记录不覆盖。没有添加自动翻译或自动编造的例句。

分享词库或其派生作品时，应保留贡献者归属、来源链接、许可链接／全文和改动说明，并按相同许可分享派生词库。示例署名：

> 词典内容来源于中文维基词典贡献者，经 Wiktextract / Kaikki.org 提取，由 Nichū Offline Dictionary 整理为离线索引；源文本与派生词库采用 CC BY-SA 4.0。词头来源与编辑历史见 https://zh.wiktionary.org/ 。

本项目未分发源音频文件、照片、商标图像或媒体资源。原始 JSON 可能包含源媒体 URL；应用不会主动请求这些链接。

## OpenCC

`data/TSCharacters.txt`、`data/TSPhrases.txt` 原样来自 [BYVoid/OpenCC](https://github.com/BYVoid/OpenCC)，采用 Apache-2.0。原始文件头保留来源和许可；随仓库分发 [许可证全文](licenses/OpenCC.txt)。本项目使用两张表做最长匹配并取首个候选的繁体→简体转换，不声称实现 OpenCC 的全部配置和地区用语转换。

表文件 SHA-256 记录在 `data/manifest.json`。获取日期为 2026-10-03（Asia/Tokyo）。
