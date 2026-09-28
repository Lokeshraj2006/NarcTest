"""
FieldProof - one-command "build APK, serve it, print a QR" helper.

What it does:
  1. Runs `flutter build apk` with LABELGUARD_API_BASE baked in so the
     app talks to your laptop's LAN backend without any code edits.
  2. Copies the resulting APK into a temp `served/` folder and starts an
     HTTP server on the port you pick (default 8080, so it doesn't
     collide with the FastAPI backend on 8000).
  3. Prints an ASCII QR code pointing at the APK download URL - scan it
     with the phone's camera, download, install (Android will ask you to
     enable "unknown sources").

Usage (from the `mobile/` folder):

    # Auto-detect LAN IP, debug APK, backend on port 8000, serve on 8080
    python scripts/build_and_serve.py

    # Everything explicit
    python scripts/build_and_serve.py --lan-ip 10.3.3.222 --backend-port 8000 \
        --serve-port 8080 --release

Requirements:
    pip install qrcode
    Flutter SDK on PATH (`flutter --version` works)
"""

from __future__ import annotations

import argparse
import http.server
import ipaddress
import shutil
import socket
import socketserver
import subprocess
import sys
from pathlib import Path


def guess_lan_ip() -> str | None:
    """Best-effort LAN IP discovery. Opens a UDP socket to a public host
    (no packets sent) and reads back the interface Windows would use."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.settimeout(0.2)
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except OSError:
        return None


def print_qr(url: str) -> None:
    try:
        import qrcode  # type: ignore
    except ImportError:
        print(
            "\n[!] The `qrcode` package isn't installed - install it with:\n"
            "    pip install qrcode\n"
            f"    Then reopen the URL yourself:\n\n    {url}\n"
        )
        return

    qr = qrcode.QRCode(border=1)
    qr.add_data(url)
    qr.make(fit=True)
    print()
    qr.print_ascii(invert=True)
    print()


def flutter(args: list[str]) -> None:
    print(f"→ flutter {' '.join(args)}")
    result = subprocess.run(["flutter", *args], check=False)
    if result.returncode != 0:
        sys.exit(
            f"flutter command failed with exit code {result.returncode}. "
            "Is Flutter on PATH and the Android scaffold generated?"
        )


def build_apk(mobile_root: Path, api_base: str, release: bool) -> Path:
    flavor = "release" if release else "debug"
    flutter([
        "build",
        "apk",
        f"--{flavor}",
        f"--dart-define=LABELGUARD_API_BASE={api_base}",
    ])
    apk = mobile_root / "build" / "app" / "outputs" / "flutter-apk" / f"app-{flavor}.apk"
    if not apk.exists():
        sys.exit(f"Expected APK at {apk} but it wasn't produced.")
    return apk


def serve(apk_path: Path, serve_dir: Path, port: int) -> None:
    served = serve_dir / "fieldproof.apk"
    served.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(apk_path, served)
    print(f"→ Serving {served} on port {port}")

    handler = http.server.SimpleHTTPRequestHandler
    handler.extensions_map.setdefault(".apk", "application/vnd.android.package-archive")

    class Handler(handler):  # type: ignore[misc]
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(serve_dir), **kwargs)

    with socketserver.TCPServer(("0.0.0.0", port), Handler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n→ Stopping APK server.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--lan-ip",
        help="Your laptop's LAN IP (default: auto-detected).",
    )
    parser.add_argument(
        "--backend-port",
        type=int,
        default=8000,
        help="Port your FastAPI backend listens on (default: 8000).",
    )
    parser.add_argument(
        "--serve-port",
        type=int,
        default=8080,
        help="Port to serve the APK download from (default: 8080).",
    )
    parser.add_argument(
        "--release",
        action="store_true",
        help="Build a --release APK instead of --debug.",
    )
    parser.add_argument(
        "--skip-build",
        action="store_true",
        help="Skip the flutter build step and serve whatever APK is already on disk.",
    )
    args = parser.parse_args()

    lan_ip = args.lan_ip or guess_lan_ip()
    if not lan_ip:
        sys.exit(
            "Could not auto-detect a LAN IP. Pass one via --lan-ip "
            "(check `ipconfig` for your Wi-Fi adapter's IPv4)."
        )
    try:
        ipaddress.ip_address(lan_ip)
    except ValueError:
        sys.exit(f"{lan_ip!r} does not look like a valid IPv4 address.")

    mobile_root = Path(__file__).resolve().parent.parent
    if not (mobile_root / "pubspec.yaml").exists():
        sys.exit(f"pubspec.yaml not found under {mobile_root} - run from mobile/.")

    api_base = f"http://{lan_ip}:{args.backend_port}"
    apk_url = f"http://{lan_ip}:{args.serve_port}/fieldproof.apk"

    print(f"\nLAN IP        : {lan_ip}")
    print(f"Backend URL   : {api_base}   (baked into the APK)")
    print(f"APK download  : {apk_url}\n")

    apk = None
    if not args.skip_build:
        apk = build_apk(mobile_root, api_base, args.release)
    else:
        flavor = "release" if args.release else "debug"
        apk = mobile_root / "build" / "app" / "outputs" / "flutter-apk" / f"app-{flavor}.apk"
        if not apk.exists():
            sys.exit(f"--skip-build was passed but no APK found at {apk}.")

    serve_dir = mobile_root / "build" / "served"
    print_qr(apk_url)
    print(
        "Scan the QR with your phone (same Wi-Fi as this laptop).\n"
        "If nothing downloads: check Windows Firewall isn't blocking\n"
        f"port {args.serve_port} - see Backend/scripts/lan_serve.py --firewall-help.\n"
    )
    serve(apk, serve_dir, args.serve_port)


if __name__ == "__main__":
    main()
