import gzip
import json
import tempfile
import unittest
from pathlib import Path

from nichu.build import build
from nichu.dictionary import Dictionary, display_entry
from nichu.text import normalize, readings, romaji, ruby_reading, simplified

FIXTURES = [
    {"word": "学校", "lang_code": "ja", "pos": "noun", "pos_title": "名詞",
     "forms": [{"form": "学校", "tags": ["canonical"], "ruby": [["学", "がっ"], ["校", "こう"]]}, {"form": "校", "raw_tags": ["量詞"]}],
     "senses": [{"glosses": ["學校；學習的場所"], "examples": [{"text": "学校へ行く。", "translation": "去學校。"}]}]},
    {"word": "食べる", "lang_code": "ja", "pos": "verb", "pos_title": "動詞",
     "forms": [{"form": "食べる", "tags": ["canonical"], "ruby": [["食", "た"]]}, {"form": "食べた", "hiragana": "たべた", "roman": "tabeta", "tags": ["past"]}],
     "senses": [{"glosses": ["吃"]}]},
    {"word": "東京", "lang_code": "ja", "pos": "name", "pos_title": "專有名詞",
     "forms": [{"form": "東京", "tags": ["canonical"], "ruby": [["東", "とう"], ["京", "きょう"]]}],
     "senses": [{"glosses": ["日本的一座城市"]}]},
    {"word": "未定義", "lang_code": "ja", "pos": "unknown", "senses": [{"tags": ["no-gloss"]}]},
    {"word": "excluded", "lang_code": "en", "pos": "noun", "senses": [{"glosses": ["excluded"]}]},
]


class NormalizationTests(unittest.TestCase):
    def test_unicode_and_kana(self):
        self.assertEqual(normalize(" ＴＡＢＥＲＵ "), "taberu")
        self.assertEqual(normalize("ｶﾞｯｺｳ"), "がっこう")
        self.assertEqual(normalize("学校"), "学校")

    def test_ruby_preserves_okurigana(self):
        self.assertEqual(ruby_reading(FIXTURES[1]["forms"][0]), "たべる")
        self.assertEqual(readings(FIXTURES[1]), ["たべる"])

    def test_romanization(self):
        for kana, expected in [("がっこう", "gakkou"), ("キャット", "kyatto"), ("コーヒー", "koohii"), ("しんよう", "shin'you"), ("マッチ", "matchi")]:
            self.assertEqual(romaji(kana), expected)

    def test_legacy_reading_is_extracted_only_from_named_heading(self):
        entry = {"word": "冷却", "senses": [{"glosses": ["冷却【れいきゃく】\n冷却处理。別語【べつご】"]}]}
        self.assertEqual(readings(entry), ["れいきゃく"])

    def test_chinese_conversion_does_not_touch_japanese(self):
        self.assertEqual(simplified("學習貓的發音"), "学习猫的发音")
        e = dict(FIXTURES[0], word="學校")
        self.assertEqual(display_entry(e)["word"], "學校")
        self.assertEqual(display_entry(e)["senses"][0]["examples"][0]["text"], "学校へ行く。")
        self.assertEqual(e["senses"][0]["glosses"][0], "學校；學習的場所")


class DictionaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory()
        cls.snapshot = Path(cls.directory.name) / "fixture.jsonl.gz"
        cls.database = Path(cls.directory.name) / "fixture.sqlite3"
        with gzip.open(cls.snapshot, "wt", encoding="utf-8") as f:
            for entry in FIXTURES:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        cls.stats = build(cls.snapshot, cls.database, verify=False)
        cls.dictionary = Dictionary(cls.database)

    @classmethod
    def tearDownClass(cls):
        cls.directory.cleanup()

    def words(self, query, **kwargs):
        return [r["word"] for r in self.dictionary.search(query, **kwargs)["results"]]

    def test_excludes_undefined_and_non_japanese(self):
        self.assertEqual(self.stats["entries"], 3)
        self.assertEqual(self.stats["without_definition"], 1)
        self.assertEqual(self.words("未定義"), [])

    def test_japanese_kana_romaji_equivalence(self):
        for q in ["学校", "がっこう", "ガッコウ", "ｶﾞｯｺｳ", "gakkou", "GAKKŌ"]:
            self.assertEqual(self.words(q, mode="exact"), ["学校"], q)

    def test_source_inflection_japanese_and_romaji(self):
        for q in ["食べた", "たべた", "tabeta"]:
            self.assertEqual(self.words(q, mode="exact"), ["食べる"])
        self.assertEqual(self.dictionary.entry(self.dictionary.search("食べる")["results"][0]["id"])["readings"], ["たべる"])

    def test_does_not_index_counter_as_word_form(self):
        self.assertEqual(self.words("校", mode="exact"), [])

    def test_chinese_reverse_both_scripts(self):
        for query in ["学习", "學習"]:
            self.assertEqual(self.words(query, mode="zh"), ["学校"])
        self.assertEqual(self.words("学习", mode="ja"), [])

    def test_macron_and_long_vowel(self):
        for query in ["toukyou", "tokyo", "TŌKYŌ"]:
            self.assertEqual(self.words(query, mode="exact"), ["東京"])

    def test_prefix_and_contains(self):
        self.assertEqual(self.words("食べ", mode="ja"), ["食べる"])
        self.assertEqual(self.words("べる", mode="contains"), ["食べる"])
        self.assertEqual(self.words("べる", mode="exact"), [])

    def test_filters_and_pagination(self):
        self.assertEqual(self.words("", pos="verb"), ["食べる"])
        self.assertEqual(self.words("", examples=True), ["学校"])
        first = self.dictionary.search("", limit=1)
        second = self.dictionary.search("", offset=1, limit=1)
        self.assertEqual(first["total"], 3)
        self.assertNotEqual(first["results"][0]["id"], second["results"][0]["id"])

    def test_literal_query_cannot_inject_sql_or_like_wildcards(self):
        for query in ["' OR 1=1 --", "%", "_", "<img src=x onerror=alert(1)>"]:
            self.assertEqual(self.words(query), [])
        self.assertEqual(self.stats["entries"], self.dictionary.search("")["total"])

    def test_invalid_parameters(self):
        for kwargs in [{"limit": 0}, {"limit": 101}, {"offset": -1}, {"mode": "bad"}]:
            with self.assertRaises(ValueError):
                self.dictionary.search("", **kwargs)
        with self.assertRaises(ValueError):
            self.dictionary.search("a" * 121)

    def test_id_stability_on_rebuild_and_raw_payload(self):
        before = self.dictionary.search("")
        build(self.snapshot, self.database, verify=False)
        self.assertEqual(before, self.dictionary.search(""))
        raw = self.dictionary.entry(self.dictionary.search("学校")["results"][0]["id"])
        self.assertIn("ruby", raw["forms"][0])
        self.assertIn("zh.wiktionary.org", raw["source_url"])
        self.assertIsNone(self.dictionary.entry("missing"))

    def test_checksum_rejects_invalid_snapshot(self):
        with self.assertRaisesRegex(ValueError, "校验失败"):
            build(self.snapshot, self.database)
        self.assertEqual(self.dictionary.search("")["total"], 3)


if __name__ == "__main__":
    unittest.main()
