#!/usr/bin/env python3
"""Serve build/site (the WebAssembly TX-2) over HTTP or HTTPS. Standard library only.

The machine runs entirely in the browser; this only serves static files.
iOS 27 WebKit runs JS and WebAssembly without JIT on plain-http pages
(https://bugs.webkit.org/show_bug.cgi?id=324968): give --cert/--key for phones.
"""
import argparse, functools, ssl
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

class Handler(SimpleHTTPRequestHandler):
    extensions_map = {**SimpleHTTPRequestHandler.extensions_map, '.wasm': 'application/wasm',
                      '.js': 'text/javascript', '.tape': 'application/octet-stream', '.json': 'application/json'}
    def end_headers(self):
        self.send_header('Cache-Control', 'no-cache')
        self.send_header('X-Content-Type-Options', 'nosniff')
        super().end_headers()

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--host', default='127.0.0.1')
    p.add_argument('--port', type=int, default=8002)
    p.add_argument('--dir', type=Path, default=ROOT / 'build/site')
    p.add_argument('--cert', type=Path, help='PEM certificate: serve HTTPS')
    p.add_argument('--key', type=Path, help='PEM private key for --cert')
    a = p.parse_args()
    if not (a.dir / 'index.html').exists():
        raise SystemExit('Build first: make site')
    server = ThreadingHTTPServer((a.host, a.port), functools.partial(Handler, directory=str(a.dir)))
    scheme = 'http'
    if a.cert:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(a.cert, a.key)
        server.socket = context.wrap_socket(server.socket, server_side=True)
        scheme = 'https'
    print(f'TX-2: {scheme}://{a.host}:{a.port}/', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass

if __name__ == '__main__':
    main()
