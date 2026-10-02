import argparse
import json

from .build import ensure_database
from .dictionary import Dictionary, display_entry


def main():
    parser = argparse.ArgumentParser(description="日中辞典：离线命令行查询")
    parser.add_argument("query", nargs="?", default="")
    parser.add_argument("--mode", choices=["auto", "ja", "zh", "exact", "contains"], default="auto")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--entry", help="按词条 ID 查看完整详情")
    parser.add_argument("--stats", action="store_true")
    parser.add_argument("--original", action="store_true", help="保留原文中文用字")
    args = parser.parse_args()
    ensure_database()
    dictionary = Dictionary()
    if args.stats:
        result = dictionary.stats()
    elif args.entry:
        result = dictionary.entry(args.entry)
        if not result:
            parser.exit(1, "词条不存在\n")
        result = display_entry(result, "original" if args.original else "simplified")
    else:
        try:
            result = dictionary.search(args.query, args.mode, limit=args.limit)
        except ValueError as error:
            parser.error(str(error))
    if args.json or args.stats or args.entry:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"{result['total']:,} 个结果")
        from .text import simplified
        for row in result["results"]:
            preview = row["preview"] if args.original else simplified(row["preview"])
            print(f"\n{row['word']}  {row['reading']}  [{row['pos_title']}]\n{preview}\nID: {row['id']}")


if __name__ == "__main__":
    main()
