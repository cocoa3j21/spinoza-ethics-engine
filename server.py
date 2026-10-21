"""
幾何学的哲学推論・探索エンジン Web UI サーバ
標準ライブラリ http.server を用いた堅牢・軽量な REST API & 静的ファイルサーバ
"""
import os
import sys
import json
import urllib.parse
from typing import Any
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
import webbrowser
import argparse

# Windows コンソールでの UTF-8 文字化け・絵文字エラー防止
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

# パス追加
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.append(CURRENT_DIR)

from engine.web_service import PhilosophyWebService

class PhilosophyRequestHandler(SimpleHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    web_service: PhilosophyWebService = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=os.path.join(CURRENT_DIR, "web"), **kwargs)

    def handle_one_request(self):
        try:
            super().handle_one_request()
        except (ConnectionResetError, BrokenPipeError):
            self.close_connection = True

    def _send_json(self, data: Any, status_code: int = 200):
        body = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(body)

    def _read_json_body(self) -> dict:
        content_length = int(self.headers.get("Content-Length", 0))
        if content_length > 0:
            raw_body = self.rfile.read(content_length).decode("utf-8")
            return json.loads(raw_body)
        return {}

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        try:
            if path == "/api/systems":
                systems = self.web_service.get_systems_list()
                self._send_json({"status": "success", "data": systems})
                return

            if path.startswith("/api/system/"):
                system_id = path.split("/api/system/")[1]
                graph = self.web_service.get_graph(system_id)
                self._send_json({"status": "success", "data": graph})
                return

            if path == "/api/system":
                system_id = query.get("id", ["Spinoza"])[0]
                graph = self.web_service.get_graph(system_id)
                self._send_json({"status": "success", "data": graph})
                return

            if path == "/api/benchmark":
                bench = self.web_service.get_benchmark()
                self._send_json({"status": "success", "data": bench})
                return

            if path == "/api/insights":
                system_id = query.get("system", ["Descartes"])[0]
                scenario_id = query.get("scenario", [None])[0]
                insights = self.web_service.get_insights(system_id, scenario_id)
                self._send_json({"status": "success", "data": insights})
                return

            if path == "/api/research/spinoza":
                res = self.web_service.get_research_spinoza()
                self._send_json(res)
                return

            if path == "/api/research/geometry":
                res = self.web_service.get_research_geometry()
                self._send_json(res)
                return

            if path.startswith("/api/"):
                self._send_json({"status": "error", "message": f"API endpoint not found: {path}"}, status_code=404)
                return

        except Exception as e:
            self._send_json({"status": "error", "message": str(e)}, status_code=500)
            return

        # 静的ファイルサーブ (web/配下)
        super().do_GET()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        try:
            data = self._read_json_body()

            if path in ("/api/toggle", "/api/toggle-premise"):
                system_id = data.get("system", "Spinoza")
                node_id = data.get("node_id")
                active = data.get("active")
                if active is not None:
                    res = self.web_service.toggle_premise(system_id, node_id, active)
                else:
                    new_val = data.get("value", "TRUE")
                    res = self.web_service.toggle_node(system_id, node_id, new_val)
                self._send_json({"status": "success", "data": res})
                return

            if path == "/api/what-if":
                system_id = data.get("system", "Spinoza")
                node_id = data.get("node_id")
                assume_val = data.get("value", "FALSE")
                res = self.web_service.what_if(system_id, node_id, assume_val)
                self._send_json({"status": "success", "data": res})
                return

            if path == "/api/frontier":
                system_id = data.get("system", "Spinoza")
                target_id = data.get("target_id")
                res = self.web_service.find_frontier(system_id, target_id)
                self._send_json({"status": "success", "data": res})
                return

            if path == "/api/clash":
                system_id = data.get("system", "Spinoza")
                res = self.web_service.inject_kant(system_id)
                self._send_json({"status": "success", "data": res})
                return

            if path == "/api/approve_defs":
                system_id = data.get("system", "Spinoza")
                res = self.web_service.approve_all_definitions(system_id)
                self._send_json({"status": "success", "data": res})
                return

            if path == "/api/reset":
                system_id = data.get("system")
                self.web_service.reset_system(system_id)
                target = system_id or "Spinoza"
                res = self.web_service.get_graph(target)
                self._send_json({"status": "success", "data": res})
                return

            self._send_json({"status": "error", "message": f"Endpoint not found: {path}"}, status_code=404)

        except Exception as e:
            self._send_json({"status": "error", "message": str(e)}, status_code=500)

def run_server(port: int = 8000, open_browser: bool = False):
    PhilosophyRequestHandler.web_service = PhilosophyWebService(CURRENT_DIR)

    # ポートの競合回避
    server = None
    for p in range(port, port + 10):
        try:
            server = ThreadingHTTPServer(("127.0.0.1", p), PhilosophyRequestHandler)
            server.daemon_threads = True
            port = p
            break
        except OSError:
            continue

    if not server:
        print(f"[Error] Could not bind to any port in range {port}-{port+9}")
        sys.exit(1)

    url = f"http://127.0.0.1:{port}"
    print("=" * 60)
    print(" [Philosophy Geometric Engine Server]")
    print(f" URL: {url}")
    print(" 終了するには Ctrl+C を押してください")
    print("=" * 60)

    if open_browser:
        webbrowser.open(url)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nサーバーを停止しました。")
    finally:
        server.server_close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Philosophy Geometric Engine Web Server")
    parser.add_argument("--port", type=int, default=8000, help="Port to listen on (default: 8000)")
    parser.add_argument("--open", action="store_true", help="Open browser automatically")
    args = parser.parse_args()

    run_server(port=args.port, open_browser=args.open)
