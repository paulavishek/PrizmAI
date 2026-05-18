#!/usr/bin/env python3
"""
PrizmAI Webhook Test Receiver
Run this alongside your Django dev server to catch and inspect webhook deliveries.
Usage: python webhook_receiver.py [--port 9000] [--secret your-hmac-secret]
"""
import argparse
import hashlib
import hmac
import json
import sys
import time
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from collections import deque

SECRET = None
deliveries = deque(maxlen=100)

RESET  = "\033[0m"
BOLD   = "\033[1m"
GREEN  = "\033[92m"
YELLOW = "\033[93m"
RED    = "\033[91m"
CYAN   = "\033[96m"
GRAY   = "\033[90m"

def verify_signature(body: bytes, header_sig: str) -> tuple[bool, str]:
    if not SECRET:
        return True, "skipped (no secret configured)"
    if not header_sig:
        return False, "missing X-PrizmAI-Signature header"
    try:
        mac = hmac.new(SECRET.encode(), body, hashlib.sha256).hexdigest()
        expected = f"sha256={mac}"
        ok = hmac.compare_digest(expected, header_sig)
        return ok, "valid" if ok else f"MISMATCH — got {header_sig}, expected {expected}"
    except Exception as e:
        return False, f"error: {e}"

class WebhookHandler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass  # silence default access log

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)
        ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]

        sig_header = self.headers.get("X-PrizmAI-Signature", "")
        sig_ok, sig_msg = verify_signature(body, sig_header)

        try:
            payload = json.loads(body)
            parse_ok = True
        except Exception:
            payload = {}
            parse_ok = False

        event = payload.get("event", "unknown")
        delivery_id = payload.get("delivery_id", "?")

        # Decide response based on path (simulate failure endpoints)
        if self.path == "/fail":
            self.send_response(500)
            self.end_headers()
            self.wfile.write(b"Internal Server Error")
            status = 500
        elif self.path == "/timeout":
            time.sleep(15)
            self.send_response(200)
            self.end_headers()
            status = "timeout-sim"
        elif self.path == "/401":
            self.send_response(401)
            self.end_headers()
            status = 401
        else:
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'{"ok": true}')
            status = 200

        record = {
            "ts": ts,
            "event": event,
            "delivery_id": delivery_id,
            "sig_ok": sig_ok,
            "sig_msg": sig_msg,
            "status": status,
            "path": self.path,
            "payload": payload,
            "parse_ok": parse_ok,
            "raw": body.decode(errors="replace"),
        }
        deliveries.append(record)

        # ── pretty-print to terminal ──────────────────────────────────────────
        color = GREEN if sig_ok and parse_ok and status == 200 else RED
        print(f"\n{BOLD}{color}{'─'*60}{RESET}")
        print(f"  {BOLD}{ts}{RESET}  {CYAN}{event}{RESET}  delivery={GRAY}{delivery_id}{RESET}  path={self.path}")
        print(f"  Signature: {'✓ ' + sig_msg if sig_ok else '✗ ' + sig_msg}")
        print(f"  Status sent: {status}")
        if parse_ok and payload:
            data = payload.get("data", {})
            for k, v in data.items():
                if isinstance(v, dict):
                    print(f"  data.{k}: {json.dumps(v)}")
                else:
                    print(f"  data.{k}: {v}")
        else:
            print(f"  {RED}⚠ body not valid JSON{RESET}: {record['raw'][:120]}")
        print(f"{color}{'─'*60}{RESET}")

    def do_GET(self):
        # /log — return all deliveries as JSON for the test dashboard
        if self.path == "/log":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps(list(deliveries), default=str).encode())
        else:
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"PrizmAI webhook receiver running. POST here, GET /log for history.")

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.end_headers()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=9000)
    parser.add_argument("--secret", type=str, default=None,
                        help="HMAC secret to verify signatures (optional)")
    args = parser.parse_args()
    SECRET = args.secret

    server = HTTPServer(("0.0.0.0", args.port), WebhookHandler)
    print(f"{BOLD}{GREEN}PrizmAI Webhook Receiver{RESET}")
    print(f"  Listening on  http://localhost:{args.port}/")
    print(f"  Failure sims  /fail (500) · /timeout · /401")
    print(f"  Log endpoint  http://localhost:{args.port}/log")
    print(f"  Secret        {'set ✓' if SECRET else 'not set — signature check skipped'}")
    print()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print(f"\n{YELLOW}Receiver stopped.{RESET}")
