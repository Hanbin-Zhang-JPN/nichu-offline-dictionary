"""Build an atomic SQLite search index from the bundled licensed snapshot."""

import gzip
import hashlib
import json
import os
import re
import sqlite3
from collections import Counter
from contextlib import closing
from pathlib import Path

from .text import ROOT, normalize, readings, romaji, roman_key, simplified
from .labels import POS_LABELS

SNAPSHOT = ROOT / "data" / "dictionary.jsonl.gz"
DATABASE = ROOT / "data" / "dictionary.sqlite3"


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def build(snapshot=SNAPSHOT, database=DATABASE, verify=True):
    snapshot, database = Path(snapshot), Path(database)
    manifest = json.loads((ROOT / "data" / "manifest.json").read_text(encoding="utf-8"))
    if verify and sha256(snapshot) != manifest["snapshot_sha256"]:
        raise ValueError("词库校验失败；请恢复 data/dictionary.jsonl.gz 后重试")
    if verify:
        for name, expected in manifest["opencc"].items():
            if sha256(ROOT / "data" / name) != expected:
                raise ValueError(f"转换词表校验失败：{name}")
    database.parent.mkdir(parents=True, exist_ok=True)
    temporary = database.with_name(database.name + f".{os.getpid()}.tmp")
    stats, words = Counter(), set()
    try:
        with closing(sqlite3.connect(temporary)) as conn, conn:
            conn.executescript("""
                PRAGMA journal_mode=OFF;
                CREATE TABLE entries (
                    id TEXT PRIMARY KEY, word TEXT NOT NULL, pos TEXT NOT NULL,
                    pos_title TEXT NOT NULL, reading TEXT NOT NULL, roman TEXT NOT NULL,
                    preview TEXT NOT NULL, gloss TEXT NOT NULL, examples INTEGER NOT NULL,
                    payload TEXT NOT NULL
                );
                CREATE TABLE aliases (key TEXT NOT NULL, entry_id TEXT NOT NULL,
                    PRIMARY KEY (key, entry_id)) WITHOUT ROWID;
                CREATE INDEX entries_pos ON entries(pos, word);
                CREATE INDEX entries_word ON entries(word);
                CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            """)
            with gzip.open(snapshot, "rt", encoding="utf-8") as source:
                for line in source:
                    raw = json.loads(line)
                    if raw.get("lang_code") != "ja":
                        continue
                    stats["source_records"] += 1
                    senses = [s for s in raw.get("senses", []) if any(s.get("glosses", []))]
                    if not senses:
                        stats["without_definition"] += 1
                        continue
                    identifier = hashlib.sha256(line.strip().encode()).hexdigest()[:24]
                    kana = readings(raw)
                    roman = [romaji(r) for r in kana]
                    glosses = [g for s in senses for g in s["glosses"]]
                    examples = sum(len(s.get("examples", [])) for s in senses)
                    payload = dict(raw, id=identifier, readings=kana, romaji=roman,
                                   source_url="https://zh.wiktionary.org/wiki/" + raw["word"] + "#日語")
                    conn.execute("INSERT OR IGNORE INTO entries VALUES (?,?,?,?,?,?,?,?,?,?)", (
                        identifier, raw["word"], raw.get("pos", "unknown"),
                        POS_LABELS.get(raw.get("pos"), raw.get("pos_title", "未标注词性")), " · ".join(kana), " · ".join(roman),
                        "；".join(glosses)[:240], normalize(simplified("\n".join(glosses))),
                        examples, json.dumps(payload, ensure_ascii=False, separators=(",", ":"))))
                    aliases = {normalize(raw["word"]), *map(normalize, kana)}
                    for r in roman:
                        aliases.update((normalize(r), roman_key(r)))
                    for form in raw.get("forms", []):
                        if set(form.get("tags", [])) & {"classifier", "counter"} or any(t in {"量詞", "量词"} for t in form.get("raw_tags", [])):
                            continue
                        for field in ("form", "hiragana", "roman"):
                            if form.get(field):
                                value = re.sub(r"[⁰¹²³⁴⁵⁶⁷⁸⁹]+$", "", form[field])
                                aliases.add(normalize(value))
                                if field == "roman":
                                    aliases.add(roman_key(value))
                    conn.executemany("INSERT OR IGNORE INTO aliases VALUES (?,?)",
                                     ((a, identifier) for a in aliases if a))
                    words.add(raw["word"])
                    stats["entries"] += 1
                    stats["senses"] += len(senses)
                    stats["examples"] += examples
                    stats["with_reading"] += bool(kana)
                    stats["with_examples"] += bool(examples)
                    stats["with_etymology"] += bool(raw.get("etymology_texts"))
                    stats["with_sounds"] += bool(raw.get("sounds"))
            stats["headwords"] = len(words)
            stats["entries"] = conn.execute("SELECT COUNT(*) FROM entries").fetchone()[0]
            stats["aliases"] = conn.execute("SELECT COUNT(*) FROM aliases").fetchone()[0]
            conn.execute("INSERT INTO metadata VALUES ('manifest', ?)", (json.dumps(manifest),))
            conn.execute("INSERT INTO metadata VALUES ('stats', ?)", (json.dumps(stats),))
            conn.execute("PRAGMA user_version=1")
            conn.execute("ANALYZE")
        os.replace(temporary, database)
    finally:
        temporary.unlink(missing_ok=True)
    return dict(stats)


def ensure_database():
    """Rebuild automatically when the bundled source manifest changes."""
    expected = json.loads((ROOT / "data" / "manifest.json").read_text(encoding="utf-8"))
    current = None
    if DATABASE.exists():
        try:
            with closing(sqlite3.connect(DATABASE.resolve().as_uri() + "?mode=ro", uri=True)) as conn:
                row = conn.execute("SELECT value FROM metadata WHERE key='manifest'").fetchone()
                current = json.loads(row[0]) if row else None
        except (sqlite3.Error, ValueError):
            pass
    if current != expected:
        return build()
    return None


if __name__ == "__main__":
    print(json.dumps(build(), ensure_ascii=False, indent=2))
