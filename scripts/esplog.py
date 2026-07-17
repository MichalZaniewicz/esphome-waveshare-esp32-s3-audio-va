#!/usr/bin/env python3
"""Stream device logs over the ESPHome native API.

The dashboard log view drops the connection whenever it feels like it, which
makes chasing a boot-time I2C failure miserable. This just prints the log.

    pip install aioesphomeapi
    python esplog.py                 # 15 s of logs
    python esplog.py 60              # 60 s
    python esplog.py 60 es7210       # 60 s, only lines containing "es7210"

Host is read from the environment (default below otherwise). The API is
unencrypted by default; if you enabled encryption, drop the base64 key into a
secrets.yaml near this script (or set ESPLOG_KEY) and it is picked up
automatically:

    ESPLOG_HOST=192.168.1.42 python esplog.py
"""
import asyncio
import os
import re
import sys
from pathlib import Path

from aioesphomeapi import APIClient, LogLevel

DEFAULT_HOST = "esp32-audio-s3.local"
PORT = 6053


def find_key():
    """Pull api_encryption_key out of a nearby secrets.yaml (no yaml dependency)."""
    env = os.environ.get("ESPLOG_KEY")
    if env:
        return env
    here = Path(__file__).resolve().parent
    for folder in (here, here.parent, here.parent.parent, Path.cwd()):
        secrets = folder / "secrets.yaml"
        if not secrets.is_file():
            continue
        m = re.search(
            r'^\s*api_encryption_key\s*:\s*["\']?([A-Za-z0-9+/=]+)["\']?\s*$',
            secrets.read_text(encoding="utf-8"),
            re.MULTILINE,
        )
        if m:
            return m.group(1)
    return None


async def main():
    host = os.environ.get("ESPLOG_HOST", DEFAULT_HOST)
    duration = int(sys.argv[1]) if len(sys.argv) > 1 else 15
    log_filter = sys.argv[2].lower() if len(sys.argv) > 2 else ""

    cli = APIClient(host, PORT, None, noise_psk=find_key())
    await cli.connect(login=True)
    info = await cli.device_info()
    print(f"# connected: {info.name} @ {host}  esphome={info.esphome_version}", flush=True)

    def on_log(msg):
        line = msg.message.decode("utf-8", "replace")
        if log_filter and log_filter not in line.lower():
            return
        print(line, flush=True)

    cli.subscribe_logs(on_log, log_level=LogLevel.LOG_LEVEL_DEBUG)
    await asyncio.sleep(duration)
    print(f"# done ({duration}s)", flush=True)
    await cli.disconnect()


asyncio.run(main())
