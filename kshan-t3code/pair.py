#!/usr/bin/env python3
"""Opens T3 Code from the Umbrel dashboard.

Umbrel's app proxy checks the Umbrel login, then sends the browser here. A
browser that is already paired with T3 Code goes straight to it. Any other
browser gets a fresh one-time pairing link (valid for 2 minutes), so nobody has
to copy tokens from a terminal. Open /pair to pair again on purpose.

Listens only on 127.0.0.1: Umbrel's app gateway runs on the host and checks
the Umbrel login before it forwards anything here.
"""

import ipaddress
import json
import os
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

BIND = os.environ.get("T3_PAIR_BIND", "127.0.0.1")
PORT = int(os.environ.get("T3_PAIR_PORT", "3772"))
T3_PORT = int(os.environ.get("T3_PORT", "3773"))
T3 = os.path.join(os.environ["T3_VERSIONS"], "current", "t3")
PROXY_NETWORK = ipaddress.ip_network(os.environ.get("T3_PAIR_NETWORK", "127.0.0.0/8"))


def t3_base(headers):
    """T3 Code's own address, on the same host name the browser used for Umbrel."""
    host = headers.get("X-Forwarded-Host") or headers.get("Host") or "umbrel.local"
    hostname = urlsplit("//" + host.split(",")[0].strip()).hostname or "umbrel.local"
    if ":" in hostname:
        hostname = f"[{hostname}]"
    return f"http://{hostname}:{T3_PORT}"


def has_t3_session(headers):
    for part in headers.get("Cookie", "").split(";"):
        if part.strip().startswith("t3_session"):
            return True
    return False


def pairing_url(base):
    out = subprocess.run(
        [T3, "auth", "pairing", "create", "--ttl", "2m", "--label", "Umbrel browser",
         "--base-url", base, "--json"],
        capture_output=True, text=True, timeout=60, check=True,
    )
    return json.loads(out.stdout)["pairUrl"]


class Handler(BaseHTTPRequestHandler):
    server_version = "t3-umbrel-pair"

    def do_GET(self):
        try:
            client = ipaddress.ip_address(self.client_address[0])
        except ValueError:
            client = None
        if client is None or client not in PROXY_NETWORK:
            return self.reply(403, "Open T3 Code from your Umbrel dashboard.")

        url = urlsplit(self.path)
        if url.path not in ("/", "/pair"):
            return self.reply(404, "Not found")

        base = t3_base(self.headers)
        force = url.path == "/pair" or "pair" in parse_qs(url.query)
        if not force and has_t3_session(self.headers):
            return self.redirect(base + "/")
        try:
            return self.redirect(pairing_url(base))
        except Exception as error:  # noqa: BLE001 - show any failure to the user
            self.log_message("pairing failed: %s", error)
            return self.reply(
                503,
                "T3 Code is still starting (the first start downloads it). "
                "Reload this page in a minute.",
            )

    def redirect(self, location):
        self.send_response(302)
        self.send_header("Location", location)
        self.send_header("Cache-Control", "no-store")
        self.end_headers()

    def reply(self, code, text):
        body = (
            "<!doctype html><meta charset=utf-8><meta name=viewport content='width=device-width'>"
            "<title>T3 Code</title><body style='font:16px system-ui;margin:3rem auto;"
            f"max-width:32rem;padding:0 1rem'><p>{text}</p>"
        ).encode()
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        if code == 503:
            self.send_header("Refresh", "15")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        sys.stderr.write("pair: " + (fmt % args) + "\n")


if __name__ == "__main__":
    ThreadingHTTPServer((BIND, PORT), Handler).serve_forever()
