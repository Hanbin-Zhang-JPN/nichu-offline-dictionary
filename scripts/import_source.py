#!/usr/bin/env python3
"""Extract every ja record from a local Kaikki Chinese-edition dump."""

import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from nichu.build import sha256
from nichu.text import ROOT


def extract(source, dump_date, extraction_date):
    target = ROOT / "data" / "dictionary.jsonl.gz"
    temporary = target.with_suffix(".tmp")
    records, count = set(), 0
    opener = gzip.open if source.suffix == ".gz" else open
    try:
        with opener(source, "rt", encoding="utf-8") as incoming, open(temporary, "wb") as output:
            with gzip.GzipFile(fileobj=output, mode="wb", filename="", mtime=0, compresslevel=9) as compressed:
                for line in incoming:
                    raw = json.loads(line)
                    if raw.get("lang_code") != "ja":
                        continue
                    normalized = json.dumps(raw, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
                    digest = hashlib.sha256(normalized).digest()
                    if digest in records:
                        continue
                    compressed.write(normalized + b"\n")
                    records.add(digest)
                    count += 1
        if count < 1000:
            raise ValueError("来源日语词条少于 1000；拒绝覆盖词库")
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)
    manifest = {
        "edition": "zhwiktionary", "language": "ja", "gloss_language": "zh",
        "dump_date": dump_date, "extraction_date": extraction_date,
        "source_url": "https://kaikki.org/zhwiktionary/raw-wiktextract-data.jsonl.gz",
        "source_info_url": "https://kaikki.org/zhwiktionary/rawdata.html",
        "source_sha256": sha256(source), "snapshot_sha256": sha256(target),
        "source_records": count, "license": "CC-BY-SA-4.0",
        "attribution": "中文维基词典贡献者；Wiktextract / Kaikki.org（Tatu Ylonen 等）",
        "modifications": "筛选 lang_code=ja；JSON 键排序与完全重复记录去重；构建本地检索索引；中文简体显示为派生视图，原始记录保留。",
        "opencc": {name: sha256(ROOT / "data" / name) for name in ("TSCharacters.txt", "TSPhrases.txt")},
    }
    (ROOT / "data" / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"已提取 {count:,} 条日语记录；快照 {target.stat().st_size / 1024**2:.1f} MiB")
    print("运行 python3 -m nichu.build 重建索引。")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--dump-date", required=True, help="源 Wikimedia dump 日期 YYYY-MM-DD")
    parser.add_argument("--extraction-date", required=True, help="Kaikki 实际提取日期 YYYY-MM-DD")
    args = parser.parse_args()
    extract(args.source, args.dump_date, args.extraction_date)
