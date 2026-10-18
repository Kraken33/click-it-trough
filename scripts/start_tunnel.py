#!/usr/bin/env python3
"""
Intelligent USB Port Forwarding Tunnel for WebDriverAgent (iOS 15 - 18+).
Supports both modern iOS 17/18+ CoreDevice RSD IPv6 tunnels and legacy USBMUX.
"""

import asyncio
import json
import os
import socket
import subprocess
import sys
from typing import Optional, Tuple


def get_ios17_tunnel_ip() -> Optional[Tuple[str, str, str]]:
    """
    Queries pymobiledevice3 remote browse to find connected iOS 17+ devices
    and their active CoreDevice tunnel IPv6 address.
    Returns (name, udid, tunnel_ip) or None.
    """
    venv_python = sys.executable
    venv_dir = os.path.dirname(venv_python)
    pm3_bin = os.path.join(venv_dir, "pymobiledevice3")

    if not os.path.exists(pm3_bin):
        pm3_bin = "pymobiledevice3"

    try:
        res = subprocess.run(
            [pm3_bin, "remote", "browse"],
            capture_output=True,
            text=True,
            timeout=6,
        )
        if res.returncode != 0 or not res.stdout.strip():
            return None

        devices = json.loads(res.stdout)
        # Prioritize physically connected USB devices over wireless/remote devices
        devices.sort(
            key=lambda d: bool(d.get("connectionState", {}).get("value", {}).get("attachedPhysically", False)),
            reverse=True,
        )

        for dev in devices:
            tunnel_ip = dev.get("tunnelDeviceAddress")
            if tunnel_ip:
                # Fast TCP check to ensure WDA is actually alive on this IP
                try:
                    s = socket.create_connection((tunnel_ip, 8100), timeout=1.5)
                    s.close()
                except Exception:
                    continue

                name = dev.get("name", "iPhone")
                udid = dev.get("udid", "unknown")
                return name, udid, tunnel_ip

        # Fallback if port check didn't pass: return first device with an IP
        for dev in devices:
            tunnel_ip = dev.get("tunnelDeviceAddress")
            if tunnel_ip:
                name = dev.get("name", "iPhone")
                udid = dev.get("udid", "unknown")
                return name, udid, tunnel_ip
    except Exception as e:
        print(f"DEBUG: Error browsing remote devices: {e}", file=sys.stderr)

    return None


async def pipe(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    try:
        while not reader.at_eof():
            data = await reader.read(65536)
            if not data:
                break
            writer.write(data)
            await writer.drain()
    except Exception:
        pass
    finally:
        try:
            writer.close()
            await writer.wait_closed()
        except Exception:
            pass


async def handle_connection(client_reader: asyncio.StreamReader, client_writer: asyncio.StreamWriter, target_ip: str, target_port: int):
    try:
        target_reader, target_writer = await asyncio.open_connection(target_ip, target_port)
    except Exception as e:
        client_writer.close()
        return

    await asyncio.gather(
        pipe(client_reader, target_writer),
        pipe(target_reader, client_writer),
        return_exceptions=True,
    )


async def run_forwarder(local_port: int, target_ip: str, target_port: int):
    server = await asyncio.start_server(
        lambda r, w: handle_connection(r, w, target_ip, target_port),
        "127.0.0.1",
        local_port,
        reuse_address=True,
    )
    print(f"✅ Tunnel active! Listening on http://127.0.0.1:{local_port} -> [{target_ip}]:{target_port}")
    print("Press Ctrl+C to stop the tunnel.")
    async with server:
        await server.serve_forever()


def main():
    local_port = 8100
    if len(sys.argv) > 1:
        try:
            local_port = int(sys.argv[1])
        except ValueError:
            pass

    print(f"🔍 Detecting connected iOS devices for WDA tunnel on port {local_port}...")

    # 1. Try iOS 17+ CoreDevice tunnel
    tunnel_info = get_ios17_tunnel_ip()
    if tunnel_info:
        name, udid, tunnel_ip = tunnel_info
        print(f"📱 Found iOS 17/18+ Device: {name} (UDID: {udid})")
        print(f"🌐 CoreDevice Tunnel Address: [{tunnel_ip}]")

        try:
            asyncio.run(run_forwarder(local_port, tunnel_ip, 8100))
        except KeyboardInterrupt:
            print("\n🔌 Tunnel stopped.")
        return

    # 2. Fallback to legacy usbmux forward for iOS 16 and older
    print("⚠️ No CoreDevice tunnel found. Falling back to legacy usbmux forward...")
    venv_dir = os.path.dirname(sys.executable)
    pm3_bin = os.path.join(venv_dir, "pymobiledevice3")
    if not os.path.exists(pm3_bin):
        pm3_bin = "pymobiledevice3"

    try:
        subprocess.run([pm3_bin, "usbmux", "forward", str(local_port), "8100"])
    except KeyboardInterrupt:
        print("\n🔌 Tunnel stopped.")


if __name__ == "__main__":
    main()
