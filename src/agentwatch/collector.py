import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Tuple


class TraceHandler(BaseHTTPRequestHandler):
    def _set_response(self, code: int = 200) -> None:
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()

    def do_POST(self) -> None:
        if self.path != "/traces":
            self._set_response(404)
            self.wfile.write(b"{\"error\": \"not found\"}")
            return

        length = int(self.headers.get('content-length', 0))
        body = self.rfile.read(length)
        try:
            payload = json.loads(body.decode('utf-8'))
        except Exception:
            self._set_response(400)
            self.wfile.write(b"{\"error\": \"invalid json\"}")
            return

        # Append traces to a local JSONL file for inspection
        with open('agentwatch_traces.jsonl', 'a', encoding='utf-8') as fh:
            fh.write(json.dumps(payload, ensure_ascii=False) + '\n')

        self._set_response(200)
        self.wfile.write(b"{\"status\": \"ok\"}")


def run_collector(host: str = '127.0.0.1', port: int = 9000) -> None:
    server_address: Tuple[str, int] = (host, port)
    httpd = HTTPServer(server_address, TraceHandler)
    print(f"AgentWatch collector running on http://{host}:{port}/traces")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print('Shutting down')
        httpd.server_close()


if __name__ == '__main__':
    run_collector()
