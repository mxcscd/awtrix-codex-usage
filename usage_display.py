#!/usr/bin/env python3
"""Publish authenticated Codex quota usage to an AWTRIX 3 clock over LAN."""
import argparse
import json
from pathlib import Path
import selectors
import shutil
import subprocess
import time
import urllib.request

# Layout and pace colours adapted from tolixx/claude-meter (MIT).
# See claude-meter-LICENSE for the upstream copyright and license.
GREEN, YELLOW, RED = "#3CD070", "#FFC400", "#FF3B30"
FONT = {
    "0": ("111", "101", "101", "101", "111"),
    "1": ("010", "110", "010", "010", "111"),
    "2": ("111", "001", "111", "100", "111"),
    "3": ("111", "001", "111", "001", "111"),
    "4": ("101", "101", "111", "001", "001"),
    "5": ("111", "100", "111", "001", "111"),
    "6": ("111", "100", "111", "101", "111"),
    "7": ("111", "001", "010", "010", "010"),
    "8": ("111", "101", "111", "101", "111"),
    "9": ("111", "101", "111", "001", "111"),
    "%": ("101", "001", "010", "100", "101"),
    "-": ("000", "000", "111", "000", "000"),
}


def find_codex(explicit=None):
    """Resolve this Mac's CLI without embedding a different Mac's paths."""
    if explicit:
        path = Path(explicit).expanduser().resolve()
        if not path.is_file():
            raise FileNotFoundError(f"Codex binary not found: {path}")
        return str(path)
    command = shutil.which("codex")
    if command:
        return command
    for applications in (Path('/Applications'), Path.home() / 'Applications'):
        resources = applications / 'Codex.app/Contents/Resources'
        for relative in ('codex', 'codex-cli/CodexCLI.app/Contents/MacOS/codex'):
            candidate = resources / relative
            if candidate.is_file():
                return str(candidate)
    raise FileNotFoundError("Codex CLI not found. Install Codex or pass --codex /absolute/path/to/codex")


def quota_color(used):
    return RED if used >= 80 else YELLOW if used >= 50 else GREEN


def compact_frame(usage, now=None):
    now = time.time() if now is None else now
    values = []
    for key in ("primary", "secondary"):
        window = usage.get(key) or {}
        value = window.get("usedPercent")
        values.append(None if value is None else max(0, min(100, round(value))))
    if all(value is None for value in values):
        raise RuntimeError("Codex returned no quota windows; display was not changed")
    weekly = usage.get("secondary") or {}
    elapsed = None
    if weekly.get("resetsAt") and weekly.get("windowDurationMins"):
        duration = weekly["windowDurationMins"] * 60
        elapsed = max(0, min(100, (now - (weekly["resetsAt"] - duration)) / duration * 100))
    colors = ["#606060" if value is None else quota_color(value) for value in values]
    used_week = values[1]
    if used_week is not None and elapsed is not None:
        ahead = used_week - elapsed
        colors[1] = RED if used_week >= 90 or ahead > 15 else YELLOW if ahead > 0 else GREEN
    draw = []
    # Two fixed 16-pixel cells also fit the worst case: "100% 100%".
    for cell, (used, color) in enumerate(zip(values, colors)):
        label = "--" if used is None else f"{used}%"
        x = cell * 16 + (16 - (len(label) * 4 - 1)) // 2
        for char in label:
            for y, row in enumerate(FONT[char], 1):
                for offset, pixel in enumerate(row):
                    if pixel == "1":
                        draw.append({"dp": [x + offset, y, color]})
            x += 4
    if used_week is not None:
        draw.append({"dl": [0, 7, 31, 7, "#303030"]})
        filled = round(used_week * 32 / 100)
        if filled:
            draw.append({"dl": [0, 7, filled - 1, 7, colors[1]]})
        if elapsed is not None:
            draw.append({"dp": [round(elapsed * 31 / 100), 7, "#FFFFFF"]})
    return {"draw": draw, "duration": 10, "lifetime": 600, "lifetimeMode": 0}


def read_usage(codex):
    process = subprocess.Popen(
        [codex, "app-server", "--listen", "stdio://"],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL, text=True, bufsize=1,
    )
    def send(message):
        process.stdin.write(json.dumps(message) + "\n")
        process.stdin.flush()
    selector = selectors.DefaultSelector()
    selector.register(process.stdout, selectors.EVENT_READ)
    try:
        send({"id": 1, "method": "initialize", "params": {"clientInfo": {
            "name": "awtrix_codex", "title": "AWTRIX Codex usage", "version": "1.0"
        }}})
        deadline = time.monotonic() + 40
        while time.monotonic() < deadline:
            if not selector.select(1):
                continue
            line = process.stdout.readline()
            if not line:
                raise RuntimeError("Codex app-server exited before returning usage")
            message = json.loads(line)
            if message.get("id") not in (1, 2):
                continue
            if "error" in message:
                raise RuntimeError(str(message["error"]))
            if message["id"] == 1:
                send({"method": "initialized"})
                send({"id": 2, "method": "account/rateLimits/read"})
            else:
                result = message["result"]
                usage = (result.get("rateLimitsByLimitId") or {}).get("codex")
                usage = usage or result.get("rateLimits")
                if not usage:
                    raise RuntimeError("Codex returned no quota data")
                return usage
        raise TimeoutError("Codex usage request timed out")
    finally:
        selector.close()
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()


def request(host, path, payload=None):
    data = payload if isinstance(payload, bytes) else None if payload is None else json.dumps(payload).encode()
    req = urllib.request.Request("http://" + host + path, data=data,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as response:
        return response.read().decode()


def publish(host, usage):
    # Confirm the expected API before writing anything to a device.
    stats = json.loads(request(host, "/api/stats"))
    if not isinstance(stats, dict) or "version" not in stats:
        raise RuntimeError("Target did not return AWTRIX 3 device statistics")
    frame = compact_frame(usage)
    request(host, "/api/custom?name=codex_usage", frame)
    # Remove the two pages from the previous scrolling layout, if still present.
    loop = json.loads(request(host, "/api/loop"))
    for old_name in ("codex_usage0", "codex_usage1"):
        if old_name in loop:
            request(host, "/api/custom?name=" + old_name, b"")
    print(json.dumps({"firmware": stats["version"], "layout": "compact",
                      "primary": usage.get("primary"), "secondary": usage.get("secondary")}), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", help="Clock IP address or local hostname")
    parser.add_argument("--codex", help="Optional absolute Codex CLI path")
    parser.add_argument("--inspect", action="store_true", help="Read quota only")
    args = parser.parse_args()
    if not args.inspect and not args.host:
        parser.error("Pass --host with the clock's Wi-Fi address")
    usage = read_usage(find_codex(args.codex))
    if args.inspect:
        print(json.dumps({key: usage.get(key) for key in ("primary", "secondary")}))
    else:
        publish(args.host, usage)


if __name__ == "__main__":
    main()
