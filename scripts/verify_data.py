#!/usr/bin/env python3
"""Verify the shipped corpus offline, including IDs, coverage and hashes."""
import gzip
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from nichu.build import ensure_database, sha256
from nichu.dictionary import Dictionary
from nichu.text import ROOT


def verify():
    manifest = json.loads((ROOT / "data/manifest.json").read_text(encoding="utf-8"))
    assert sha256(ROOT / "data/dictionary.jsonl.gz") == manifest["snapshot_sha256"], "词库 SHA-256 不匹配"
    for name, digest in manifest["opencc"].items():
        assert sha256(ROOT / "data" / name) == digest, f"{name} SHA-256 不匹配"
    count = 0
    with gzip.open(ROOT / "data/dictionary.jsonl.gz", "rt", encoding="utf-8") as source:
        for line in source:
            entry = json.loads(line)
            assert entry["lang_code"] == "ja" and entry["word"], "存在非日语/空词头记录"
            count += 1
    assert count == manifest["source_records"], "快照记录数不匹配"
    ensure_database()
    dictionary = Dictionary()
    stats = dictionary.stats()["stats"]
    reference = json.loads((ROOT / "data/stats.json").read_text(encoding="utf-8"))
    assert stats == reference, "索引统计与已发布数据报告不一致；更新词库后需重新生成 stats.json"
    for query, word in [("食べる", "食べる"), ("taberu", "食べる"), ("学校", "学校"), ("neko", "猫"), ("nihongo", "日本語")]:
        results = dictionary.search(query, "exact")["results"]
        assert word in [r["word"] for r in results], f"缺少基本词条：{query}"
    with dictionary.connect() as conn:
        assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok", "SQLite 完整性检查失败"
        assert conn.execute("SELECT COUNT(*) FROM entries WHERE gloss='' OR word='' ").fetchone()[0] == 0
    print(json.dumps({"verified": True, "stats": stats}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    verify()
