"""Editeur des cartes. `python -m world3.editor` ouvre la page dans le navigateur.

Le jeu lit contenu.json au lancement. Enregistrer ici, puis relancer la partie.
"""

from __future__ import annotations

import json
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from .content import document, save_contenu

PAGE = Path(__file__).with_name("editor_page.html")
HOST = "127.0.0.1"
PORT = 8765


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        return

    def _send(self, code, body, content_type):
        data = body if isinstance(body, bytes) else body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/api/contenu":
            self._send(200, json.dumps(document(), ensure_ascii=False), "application/json; charset=utf-8")
            return
        if path in ("/", "/index.html"):
            self._send(200, PAGE.read_text(encoding="utf-8"), "text/html; charset=utf-8")
            return
        self._send(404, "introuvable", "text/plain; charset=utf-8")

    def do_PUT(self):
        path = urlparse(self.path).path
        if path != "/api/contenu":
            self._send(404, "introuvable", "text/plain; charset=utf-8")
            return
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length)
        try:
            doc = json.loads(raw.decode("utf-8"))
            save_contenu(doc)
        except (json.JSONDecodeError, TypeError, ValueError, OSError) as exc:
            self._send(400, str(exc), "text/plain; charset=utf-8")
            return
        self._send(200, json.dumps({"ok": True}, ensure_ascii=False), "application/json; charset=utf-8")


def main(argv=None):
    del argv
    if not PAGE.exists():
        raise SystemExit(f"page manquante : {PAGE}")
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    url = f"http://{HOST}:{PORT}/"
    print(f"Editeur : {url}")
    print("Enregistrer ecrit contenu.json. Relancez le jeu pour le voir.")
    webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print()
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
