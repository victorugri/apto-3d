#!/usr/bin/env python3
"""Servidor local do Apê 3D.

Serve a pasta site/ e guarda no disco tudo o que o site salva (layouts,
alinhamento, imagens dos quadros, modelos de móveis). Assim nada se perde
ao trocar de navegador ou limpar o cache.

Uso:
    python serve.py            # abre http://localhost:8000
    python serve.py --port 9000 --no-browser
"""
import argparse
import json
import mimetypes
import re
import threading
import webbrowser
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SITE = ROOT / "site"
DATA = SITE / "data"
KV = DATA / "kv"
BLOBS = DATA / "blobs"
SAFE = re.compile(r"^[A-Za-z0-9_.:-]{1,120}$")

# O index.html é escrito sem <!doctype>/<head> (formato de artifact); aqui ele ganha o esqueleto.
HEAD = (
    "<!doctype html>\n<html lang=\"pt-BR\">\n<head>\n<meta charset=\"utf-8\">\n"
    "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1, viewport-fit=cover\">\n"
    "<style>:root{color-scheme:light}body{margin:0}[hidden]{display:none!important}</style>\n"
    "</head>\n<body>\n"
)


def pagina():
    """index.html com o esqueleto. Usado ao servir e no deploy do GitHub Pages (.github/workflows/pages.yml)."""
    return HEAD + (SITE / "index.html").read_text(encoding="utf-8") + "\n</body>\n</html>\n"

for ext, typ in {".ply": "application/octet-stream", ".spz": "application/octet-stream",
                 ".splat": "application/octet-stream", ".ksplat": "application/octet-stream",
                 ".usdz": "model/vnd.usdz+zip", ".glb": "model/gltf-binary", ".js": "text/javascript",
                 ".mjs": "text/javascript", ".json": "application/json"}.items():
    mimetypes.add_type(typ, ext)


class Handler(SimpleHTTPRequestHandler):
    def log_message(self, fmt, *args):
        if "/api/" not in (args[0] if args else ""):
            super().log_message(fmt, *args)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    # ---------- helpers ----------
    def _json(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _api_path(self):
        parts = self.path.split("?", 1)[0].split("/")
        # ['', 'api', kind, key]
        if len(parts) != 4 or parts[1] != "api":
            return None, None
        from urllib.parse import unquote
        key = unquote(parts[3])
        if not SAFE.match(key):
            return parts[2], None
        return parts[2], key

    def _read_body(self):
        n = int(self.headers.get("Content-Length") or 0)
        return self.rfile.read(n) if n else b""

    # ---------- GET ----------
    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path == "/api/ping":
            return self._json(200, {"ok": True})
        if path.startswith("/api/"):
            kind, key = self._api_path()
            if not key:
                return self._json(400, {"error": "chave inválida"})
            if kind == "kv":
                f = KV / f"{key}.json"
                body = f.read_bytes() if f.exists() else b"null"   # ainda não salvo = null
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            if kind == "blob":
                f = BLOBS / key
                if not f.exists():
                    return self._json(404, {"error": "não existe"})
                self.send_response(200)
                self.send_header("Content-Type", "application/octet-stream")
                self.send_header("Content-Length", str(f.stat().st_size))
                self.end_headers()
                with f.open("rb") as fh:
                    while chunk := fh.read(1 << 20):
                        self.wfile.write(chunk)
                return
            return self._json(404, {"error": "rota desconhecida"})
        if path in ("/", "/index.html"):
            body = pagina().encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        return super().do_GET()

    # ---------- PUT ----------
    def do_PUT(self):
        kind, key = self._api_path()
        if not key:
            return self._json(400, {"error": "chave inválida"})
        data = self._read_body()
        if kind == "kv":
            try:
                json.loads(data or b"null")
            except json.JSONDecodeError:
                return self._json(400, {"error": "JSON inválido"})
            KV.mkdir(parents=True, exist_ok=True)
            tmp = KV / f".{key}.tmp"
            tmp.write_bytes(data)
            tmp.replace(KV / f"{key}.json")
            return self._json(200, {"ok": True})
        if kind == "blob":
            BLOBS.mkdir(parents=True, exist_ok=True)
            (BLOBS / key).write_bytes(data)
            return self._json(200, {"ok": True})
        return self._json(404, {"error": "rota desconhecida"})


def main():
    ap = argparse.ArgumentParser(description="Servidor local do Apê 3D")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--host", default="127.0.0.1", help="use 0.0.0.0 para abrir no celular pela rede de casa")
    ap.add_argument("--no-browser", action="store_true")
    args = ap.parse_args()
    DATA.mkdir(parents=True, exist_ok=True)
    httpd = ThreadingHTTPServer((args.host, args.port), partial(Handler, directory=str(SITE)))
    url = f"http://localhost:{args.port}"
    print(f"Apê 3D rodando em {url}  (Ctrl+C para parar)")
    if args.host == "0.0.0.0":
        print("Acessível na rede local: use o IP deste PC no celular, ex.: http://192.168.0.10:%d" % args.port)
    if not args.no_browser:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nParado.")


if __name__ == "__main__":
    main()
