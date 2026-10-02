"""Deterministic normalization; Japanese spelling is never simplified."""

import re
import unicodedata
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def normalize(text):
    text = unicodedata.normalize("NFKC", text).lower().strip()
    return "".join(chr(ord(c) - 0x60) if "ァ" <= c <= "ヶ" else c for c in text)


@lru_cache(maxsize=1)
def conversion_tables():
    tables = {}
    for name in ("TSCharacters.txt", "TSPhrases.txt"):
        for line in (ROOT / "data" / name).read_text(encoding="utf-8").splitlines():
            if line and not line.startswith("#"):
                key, values = line.split("\t", 1)
                tables[key] = values.split()[0]
    return tables, max(map(len, tables))


@lru_cache(maxsize=8192)
def simplified(text):
    tables, size = conversion_tables()
    out, i = [], 0
    while i < len(text):
        for n in range(min(size, len(text) - i), 0, -1):
            part = text[i:i + n]
            if part in tables:
                out.append(tables[part])
                i += n
                break
        else:
            out.append(text[i])
            i += 1
    return "".join(out)


_ROWS = [
    ("あいうえお", "a i u e o"), ("かきくけこ", "ka ki ku ke ko"),
    ("がぎぐげご", "ga gi gu ge go"), ("さしすせそ", "sa shi su se so"),
    ("ざじずぜぞ", "za ji zu ze zo"), ("たちつてと", "ta chi tsu te to"),
    ("だぢづでど", "da ji zu de do"), ("なにぬねの", "na ni nu ne no"),
    ("はひふへほ", "ha hi fu he ho"), ("ばびぶべぼ", "ba bi bu be bo"),
    ("ぱぴぷぺぽ", "pa pi pu pe po"), ("まみむめも", "ma mi mu me mo"),
    ("やゆよ", "ya yu yo"), ("らりるれろ", "ra ri ru re ro"),
    ("わゐゑをん", "wa wi we wo n"), ("ぁぃぅぇぉゔ", "a i u e o vu"),
]
_KANA = {c: r for chars, romans in _ROWS for c, r in zip(chars, romans.split())}
for kana, stem in {"き": "ky", "ぎ": "gy", "し": "sh", "じ": "j", "ち": "ch", "に": "ny", "ひ": "hy", "び": "by", "ぴ": "py", "み": "my", "り": "ry"}.items():
    for small, vowel in zip("ゃゅょ", "auo"):
        _KANA[kana + small] = stem + vowel
_KANA.update(dict(zip(
    "ふぁ ふぃ ふぇ ふぉ てぃ でぃ とぅ どぅ しぇ じぇ ちぇ うぃ うぇ うぉ ゔぁ ゔぃ ゔぇ ゔぉ てゅ でゅ".split(),
    "fa fi fe fo ti di tu du she je che wi we wo va vi ve vo tyu dyu".split())))


def romaji(text):
    text, result, i, geminate = normalize(text), "", 0, False
    while i < len(text):
        c = text[i]
        if c == "っ":
            geminate = True
            i += 1
            continue
        if c == "ー":
            result += result[-1] if result and result[-1] in "aeiou" else ""
            i += 1
            continue
        pair = text[i:i + 2]
        syllable = _KANA.get(pair, _KANA.get(c, c))
        i += 2 if pair in _KANA else 1
        if geminate and syllable[0] not in "aeioun":
            result += "t" if syllable.startswith("ch") else syllable[0]
        geminate = False
        if result.endswith("n") and c != "ん" and syllable[0] in "aeiouy":
            result += "'"
        result += syllable
    return result


def roman_key(text):
    text = unicodedata.normalize("NFKD", text.lower())
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r"[\s'’\-]", "", text)
    return re.sub(r"aa|ii|uu|ee|oo|ou", lambda m: m[0][0], text)


def ruby_reading(form):
    word, start, out = form.get("form", ""), 0, []
    for base, reading in form.get("ruby", []):
        at = word.find(base, start)
        if at < 0:
            return ""
        out.extend((word[start:at], reading))
        start = at + len(base)
    out.append(word[start:])
    return "".join(out)


def readings(entry):
    found = []
    candidates = [entry["word"]]
    for form in entry.get("forms", []):
        if "canonical" in form.get("tags", []) or (form.get("ruby") and form.get("form") == entry["word"]):
            candidates.append(ruby_reading(form))
        if set(form.get("tags", [])) & {"hiragana", "katakana"}:
            candidates.append(form.get("form", ""))
    for sound in entry.get("sounds", []):
        candidates.append(sound.get("other", ""))
    # Older pages embed explicit readings in definition text. Match this word's
    # heading only; never guess a reading from another word in the definition.
    for sense in entry.get("senses", []):
        for gloss in sense.get("glosses", []):
            candidates.extend(re.findall(re.escape(entry["word"]) + r"【([ぁ-ゖァ-ヶー・\s]+)】", gloss))
    for candidate in candidates:
        if candidate and re.fullmatch(r"[ぁ-ゖァ-ヶー・\s]+", candidate):
            candidate = re.sub(r"\s", "", candidate)
            if candidate not in found:
                found.append(candidate)
    return found
