#!/usr/bin/env python3
"""Install the AWTRIX updater as a per-user macOS login service."""
import argparse
import os
from pathlib import Path
import plistlib
import shutil
import subprocess
import sys

from usage_display import find_codex

LABEL = "local.codex.awtrix-usage"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", required=True, help="Clock IP or local hostname, without http://")
    parser.add_argument("--codex", help="Optional absolute path to the Codex CLI")
    parser.add_argument("--interval", type=int, default=120, help="Refresh seconds (minimum 60)")
    parser.add_argument("--dry-run", action="store_true", help="Show the job without writing or starting it")
    args = parser.parse_args()
    if sys.platform != "darwin":
        parser.error("The login service installer requires macOS; the updater can run manually elsewhere")
    if args.interval < 60:
        parser.error("--interval must be at least 60 seconds")
    if not args.host or any(c in args.host for c in '/?#@ \t\r\n'):
        parser.error("--host must be an IP or local hostname, optionally followed by :port")
    codex = find_codex(args.codex)
    source = Path(__file__).resolve().parent
    runtime = Path.home() / "Library/Application Support/CodexAWTRIX"
    agent = Path.home() / "Library/LaunchAgents" / (LABEL + ".plist")
    job = {
        "Label": LABEL,
        "ProgramArguments": [sys.executable, str(runtime / "usage_display.py"),
                             "--host", args.host, "--codex", codex],
        "WorkingDirectory": str(runtime),
        "StartInterval": args.interval,
        "RunAtLoad": True,
        "ProcessType": "Background",
        "StandardOutPath": str(runtime / "usage-display.log"),
        "StandardErrorPath": str(runtime / "usage-display-error.log"),
    }
    if args.dry_run:
        print(plistlib.dumps(job).decode())
        return
    domain = "gui/" + str(os.getuid())
    loaded = subprocess.run(["/bin/launchctl", "print", domain + "/" + LABEL],
                            capture_output=True).returncode == 0
    if loaded:
        subprocess.run(["/bin/launchctl", "bootout", domain + "/" + LABEL], check=True)
    runtime.mkdir(parents=True, exist_ok=True)
    agent.parent.mkdir(parents=True, exist_ok=True)
    for name in ("usage_display.py", "claude-meter-LICENSE", "LICENSE"):
        original = source / name
        target = runtime / name
        if original.resolve() != target.resolve():
            temporary = target.with_suffix(target.suffix + ".new")
            shutil.copy2(original, temporary)
            os.replace(temporary, target)
    temporary = agent.with_suffix(".plist.new")
    temporary.write_bytes(plistlib.dumps(job))
    os.replace(temporary, agent)
    subprocess.run(["/bin/launchctl", "bootstrap", domain, str(agent)], check=True)
    print(f"Installed {LABEL}; refresh interval {args.interval} seconds")
    print(f"Logs: {runtime}")
    print("Verify the first update in usage-display.log and check usage-display-error.log.")


if __name__ == "__main__":
    main()
