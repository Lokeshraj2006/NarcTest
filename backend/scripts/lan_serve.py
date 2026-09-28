"""
FieldProof - Backend LAN-serve helper.

Launches uvicorn bound to 0.0.0.0 (not localhost) so a phone on the same
Wi-Fi as this machine can reach the API. Also prints the firewall rule
you need on Windows to let the phone through.

Usage (from the Backend/ folder):

    # Start the API on 0.0.0.0:8000 with reload enabled
    python scripts/lan_serve.py

    # Different port / disable reload
    python scripts/lan_serve.py --port 8001 --no-reload

    # Only print the Windows Firewall command, don't start the server
    python scripts/lan_serve.py --firewall-help
"""

from __future__ import annotations

import argparse
import socket
import subprocess
import sys
import textwrap


def guess_lan_ip() -> str | None:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.settimeout(0.2)
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except OSError:
        return None


def firewall_help(port: int) -> str:
    rule_name = f"FieldProof-API-{port}"
    return textwrap.dedent(
        f"""
        Windows Firewall - allow inbound TCP on port {port}
        =====================================================

        Open an **Administrator** PowerShell / Command Prompt and run:

            netsh advfirewall firewall add rule ^
                name="{rule_name}" ^
                dir=in action=allow ^
                protocol=TCP localport={port}

        To remove the rule later:

            netsh advfirewall firewall delete rule name="{rule_name}"

        If you can't get admin: on private networks (Wi-Fi marked "Private"
        in Windows Settings), inbound TCP is often already allowed for
        Python. If a Windows Defender prompt appears the first time uvicorn
        binds the port, click "Allow" for private networks.
        """
    ).strip()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument(
        "--no-reload",
        action="store_true",
        help="Disable uvicorn --reload (recommended for demo builds).",
    )
    parser.add_argument(
        "--firewall-help",
        action="store_true",
        help="Only print the Windows Firewall netsh command and exit.",
    )
    args = parser.parse_args()

    if args.firewall_help:
        print(firewall_help(args.port))
        return

    lan_ip = guess_lan_ip() or "<your-LAN-IP>"
    print("\n" + "=" * 60)
    print(f"  FieldProof API - LAN mode")
    print("=" * 60)
    print(f"  Bind    : {args.host}:{args.port}")
    print(f"  Reach   : http://{lan_ip}:{args.port}  (from phone or other LAN devices)")
    print(f"  Docs    : http://{lan_ip}:{args.port}/docs")
    print("=" * 60)
    print()
    print(firewall_help(args.port))
    print()

    cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "app.main:app",
        "--host",
        args.host,
        "--port",
        str(args.port),
    ]
    if not args.no_reload:
        cmd.append("--reload")

    print(f"→ Launching: {' '.join(cmd)}\n")
    try:
        subprocess.run(cmd, check=False)
    except KeyboardInterrupt:
        print("\n→ Backend stopped.")


if __name__ == "__main__":
    main()
