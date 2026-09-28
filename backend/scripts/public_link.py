"""
FieldProof - public link for the PDF QR code (demo helper).

Other phones (mobile data, other Wi-Fi) cannot reach this laptop directly, so this:
  1. starts a tiny VERIFY-ONLY gateway on 127.0.0.1:8001 that forwards ONLY
     GET /v/<id>, GET /verify/<id> and GET /verify/pubkey to the real API on :8000
     (login, tests, kits, images and the dashboard are NOT reachable);
  2. opens a secure tunnel with Pinggy (a.pinggy.io) using Windows' built-in ssh over
     port 443 (works on college Wi-Fi that blocks port 22; no download, no account)
     -> https://<random>.pinggy-free.link  (free links expire after 60 min; we reconnect)
  3. writes that address to backend/qr_base_url.txt, which the PDF report uses for its QR.

Run (keep the window open while you demo):
    backend\\venv\\Scripts\\python.exe backend\\scripts\\public_link.py
Stop with Ctrl+C. The link changes every time you restart it -> re-download the PDF.
"""
from __future__ import annotations

import re
import subprocess
import sys
import threading
import time
from pathlib import Path

import httpx
import uvicorn
from fastapi import FastAPI, Response

BACKEND = Path(__file__).resolve().parents[1]
URL_FILE = BACKEND / "qr_base_url.txt"
API = "http://127.0.0.1:8000"
GATEWAY_PORT = 8001

gw = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
_client = httpx.Client(timeout=20)


def _forward(path: str) -> Response:
    r = _client.get(API + path)
    return Response(r.content, status_code=r.status_code,
                    media_type=r.headers.get("content-type", "text/plain"))


@gw.get("/v/{test_id}")
def verify_page(test_id: int):
    return _forward(f"/v/{test_id}")


@gw.get("/verify/pubkey")
def pubkey():
    return _forward("/verify/pubkey")


@gw.get("/verify/{test_id}")
def verify_json(test_id: int):
    return _forward(f"/verify/{test_id}")


@gw.get("/")
def home():
    return Response("FieldProof verify gateway - scan a record QR code.", media_type="text/plain")


def run_gateway() -> None:
    uvicorn.run(gw, host="127.0.0.1", port=GATEWAY_PORT, log_level="warning")


def main() -> None:
    threading.Thread(target=run_gateway, daemon=True).start()
    time.sleep(1.5)
    cmd = ["ssh", "-p", "443", "-o", "StrictHostKeyChecking=accept-new", "-o", "ServerAliveInterval=30",
           "-o", "ExitOnForwardFailure=yes", "-R", f"0:127.0.0.1:{GATEWAY_PORT}", "a.pinggy.io"]
    try:
        while True:  # free Pinggy links end after 60 min -> reconnect and publish the new link
            print("Opening secure tunnel via Pinggy (port 443) ...", flush=True)
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                    stdin=subprocess.DEVNULL, text=True, encoding="utf-8", errors="replace")
            found = None
            for line in proc.stdout:
                m = re.search(r"https://[a-z0-9.-]+\.pinggy[a-z.-]*\.(?:link|net|online)", line)
                if m and not found:
                    found = m.group(0)
                    URL_FILE.write_text(found, encoding="utf-8")
                    print(f"\nPUBLIC LINK READY: {found}", flush=True)
                    print(f"PDF QR codes now point to {found}/v/<test id>  (re-download PDFs)", flush=True)
                    print("Keep this window open during the demo. Ctrl+C to stop.\n", flush=True)
            proc.wait()
            print("Tunnel closed - reconnecting in 5 s (the link will change) ...", flush=True)
            time.sleep(5)
    except KeyboardInterrupt:
        pass
    finally:
        if URL_FILE.exists():
            URL_FILE.unlink()
        sys.exit(0)


if __name__ == "__main__":
    main()
