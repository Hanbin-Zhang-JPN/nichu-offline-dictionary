"""Read-only, parameterized search; one connection per request."""

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from .build import DATABASE
from .text import normalize, roman_key, simplified
from .labels import POS_LABELS


class Dictionary:
    def __init__(self, path=DATABASE):
        self.path = Path(path)

    @contextmanager
    def connect(self):
        connection = sqlite3.connect(self.path.resolve().as_uri() + "?mode=ro", uri=True)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
        finally:
            connection.close()

    def stats(self):
        with self.connect() as conn:
            result = {r["key"]: json.loads(r["value"]) for r in conn.execute("SELECT * FROM metadata")}
            result["parts_of_speech"] = [dict(r) for r in conn.execute(
                "SELECT pos, MAX(pos_title) AS title, COUNT(*) AS count FROM entries GROUP BY pos ORDER BY count DESC")]
            for item in result["parts_of_speech"]:
                item["title"] = POS_LABELS.get(item["pos"], item["title"])
            return result

    def entry(self, identifier):
        with self.connect() as conn:
            row = conn.execute("SELECT payload FROM entries WHERE id=?", (identifier,)).fetchone()
            return json.loads(row[0]) if row else None

    def search(self, query="", mode="auto", pos="", examples=False, offset=0, limit=30):
        query = query.strip()
        if len(query) > 120:
            raise ValueError("搜索内容最多 120 字")
        if mode not in {"auto", "ja", "zh", "exact", "contains"}:
            raise ValueError("未知搜索模式")
        if offset < 0 or not 1 <= limit <= 100:
            raise ValueError("分页参数超出范围")
        key, filters, filter_params = normalize(query), [], []
        if pos:
            filters.append("e.pos=?")
            filter_params.append(pos)
        if examples:
            filters.append("e.examples>0")
        where = " WHERE " + " AND ".join(filters) if filters else ""
        params, branches = [], []
        if query:
            if mode != "zh":
                roman = roman_key(key)
                keys = sorted({key, roman} if roman.isascii() else {key})
                for k in keys:
                    branches.append("SELECT entry_id AS id, 0 AS rank FROM aliases WHERE key=?")
                    params.append(k)
                    if mode != "exact":
                        branches.append("SELECT entry_id AS id, 1 AS rank FROM aliases WHERE key>=? AND key<?")
                        params.extend((k, k + "\U0010ffff"))
                if mode == "contains":
                    branches.append("SELECT entry_id AS id, 2 AS rank FROM aliases WHERE instr(key,?)>0")
                    params.append(key)
            if mode in {"auto", "zh", "contains"}:
                branches.append("SELECT id, 3 AS rank FROM entries WHERE instr(gloss,?)>0")
                params.append(normalize(simplified(query)))
            cte = "WITH hits AS (" + " UNION ALL ".join(branches) + "), ranked AS (SELECT id, MIN(rank) AS rank FROM hits GROUP BY id) "
            table = "entries e JOIN ranked r ON e.id=r.id"
            order = "r.rank, CASE WHEN e.pos IN ('soft-redirect','romanization','unknown') THEN 1 ELSE 0 END, length(e.word), e.word, e.id"
        else:
            cte, table, order = "", "entries e", "e.word, e.pos, e.id"
        with self.connect() as conn:
            total = conn.execute(cte + "SELECT COUNT(*) FROM " + table + where, params + filter_params).fetchone()[0]
            rows = conn.execute(cte + "SELECT e.id,e.word,e.pos,e.pos_title,e.reading,e.roman,e.preview,e.examples FROM " + table + where + " ORDER BY " + order + " LIMIT ? OFFSET ?", params + filter_params + [limit, offset])
            return {"query": query, "total": total, "offset": offset, "limit": limit, "results": [dict(r) for r in rows]}


def display_entry(entry, script="simplified"):
    """Convert Chinese text only; source Japanese and the raw payload survive."""
    if script != "simplified":
        return entry
    result = json.loads(json.dumps(entry))
    for sense in result.get("senses", []):
        sense["glosses"] = [simplified(g) for g in sense.get("glosses", [])]
        for example in sense.get("examples", []):
            for field in ("translation", "ref"):
                if field in example:
                    example[field] = simplified(example[field])
    result["etymology_texts"] = [simplified(t) for t in result.get("etymology_texts", [])]
    result["notes"] = [simplified(t) for t in result.get("notes", [])]
    result["display_script"] = "simplified"
    return result
