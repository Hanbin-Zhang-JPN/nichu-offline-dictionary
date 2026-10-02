# 本地只读 API

默认服务地址：`http://127.0.0.1:8765`。所有 API 为 GET，JSON UTF-8，无写入与上传接口。Host 必须为本地地址和实际服务端口。

## `GET /api/stats`

返回 `manifest`、`stats` 和 `parts_of_speech`（`pos`、`title`、`count`）。

## `GET /api/search`

| 参数 | 默认值 | 说明 |
| --- | --- | --- |
| `q` | 空 | 查询字符串；最多 120 字。空查询浏览全部词条 |
| `mode` | `auto` | `auto` / `ja` / `zh` / `exact` / `contains` |
| `pos` | 空 | 按源结构化词性代码筛选，例如 `noun` / `verb` |
| `examples` | `0` | `1` 仅保留有结构化用例的词条 |
| `offset` | `0` | 非负分页偏移 |
| `limit` | `30` | 每页 1–100 条 |
| `script` | `simplified` | `simplified` / `original`，控制中文预览用字 |

返回结构：

```json
{
  "query": "学校",
  "total": 1,
  "offset": 0,
  "limit": 30,
  "results": [{
    "id": "47de72d5b2282d2174c05c01",
    "word": "学校",
    "pos": "noun",
    "pos_title": "名词",
    "reading": "がっこう · がっこー",
    "roman": "gakkou · gakkoo",
    "preview": "学校",
    "examples": 0
  }]
}
```

示例对应 `q=学校&mode=exact`；实际其他模式结果数会不同。参数应使用 URL 编码。

## `GET /api/entry/{id}`

返回完整源词条字段，以及派生字段 `id`、`readings`、`romaji`、`source_url`。可选 `script=original` 保留源中文文字（仍包含派生字段）。默认 `simplified` 仅转换中文释义、中文例句翻译、引文出处、用法说明与语源文本，日语词头和例句保持原文。

找不到词条返回 404；非法参数返回 400；未知路径返回 404。API 错误返回 `{"error": "说明"}`；非法 Host 返回 403。原始源文件在 `data/dictionary.jsonl.gz` 中，HTTP 不开放源快照或 SQLite 文件下载。
