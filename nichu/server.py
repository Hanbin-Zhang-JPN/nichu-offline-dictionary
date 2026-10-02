"""Loopback-only offline HTTP interface. No third-party requests."""

import argparse
import json
import sys
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from .build import DATABASE, ensure_database
from .dictionary import Dictionary, display_entry
from .text import ROOT, simplified

ASSETS = {"/": ("index.html", "text/html; charset=utf-8"),
          "/app.js": ("app.js", "text/javascript; charset=utf-8"),
          "/style.css": ("style.css", "text/css; charset=utf-8"),
          "/icon.svg": ("icon.svg", "image/svg+xml"),
          "/guide": ("guide.html", "text/html; charset=utf-8")}


def handler_for(dictionary):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            parsed = urlparse(self.path)
            expected = {f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}"}
            if self.headers.get("Host") not in expected:
                self.send_error(403, "Use localhost or 127.0.0.1")
                return
            try:
                if parsed.path in ASSETS:
                    filename, mime = ASSETS[parsed.path]
                    self.respond((ROOT / "web" / filename).read_bytes(), mime)
                    return
                args = {k: v[0] for k, v in parse_qs(parsed.query).items()}
                script = args.get("script", "simplified")
                if script not in {"simplified", "original"}:
                    raise ValueError("script 必须为 simplified 或 original")
                if parsed.path == "/api/stats":
                    data = dictionary.stats()
                elif parsed.path == "/api/search":
                    data = dictionary.search(args.get("q", ""), args.get("mode", "auto"),
                        args.get("pos", ""), args.get("examples") == "1",
                        int(args.get("offset", "0")), int(args.get("limit", "30")))
                    if script == "simplified":
                        for row in data["results"]:
                            row["preview"] = simplified(row["preview"])
                            row["pos_title"] = simplified(row["pos_title"])
                elif parsed.path.startswith("/api/entry/"):
                    entry = dictionary.entry(parsed.path.rsplit("/", 1)[-1])
                    if entry is None:
                        self.respond_json({"error": "词条不存在"}, 404)
                        return
                    data = display_entry(entry, script)
                else:
                    self.respond_json({"error": "页面不存在"}, 404)
                    return
                self.respond_json(data)
            except (ValueError, TypeError) as error:
                self.respond_json({"error": str(error)}, 400)
            except Exception as error:
                print(f"服务错误：{error}", file=sys.stderr)
                self.respond_json({"error": "本地词库读取失败，请查看终端"}, 500)

        def respond_json(self, data, status=200):
            self.respond(json.dumps(data, ensure_ascii=False).encode(), "application/json; charset=utf-8", status)

        def respond(self, body, mime, status=200):
            self.send_response(status)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Content-Security-Policy", "default-src 'self'; connect-src 'self'; script-src 'self'; style-src 'self'; img-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_args):
            pass

    return Handler


def main():
    parser = argparse.ArgumentParser(description="启动完全离线的日中词典")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("端口必须在 1–65535 之间")
    if not DATABASE.exists():
        print("首次启动：正在从随仓库附带的快照建立本地索引（无需联网）…", flush=True)
    stats = ensure_database()
    if stats:
        print(f"索引就绪：{stats['entries']:,} 个词条", flush=True)
    try:
        server = ThreadingHTTPServer(("127.0.0.1", args.port), handler_for(Dictionary()))
    except OSError as error:
        parser.exit(1, f"启动失败：{error}。可使用 --port 8766 更换端口。\n")
    url = f"http://127.0.0.1:{args.port}"
    print(f"日中辞典已启动：{url}\n按 Ctrl+C 关闭。查询、收藏和历史记录均留在本机。", flush=True)
    if not args.no_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
