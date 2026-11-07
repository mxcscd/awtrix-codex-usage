#!/usr/bin/env python3
"""Stop the AWTRIX updater and disable automatic starts; retain files and logs."""
import os
from pathlib import Path
import subprocess
import sys


def main():
    if sys.platform != "darwin":
        raise SystemExit("This service uninstaller requires macOS")
    label = "local.codex.awtrix-usage"
    service = "gui/" + str(os.getuid()) + "/" + label
    if subprocess.run(["/bin/launchctl", "print", service], capture_output=True).returncode == 0:
        subprocess.run(["/bin/launchctl", "bootout", service], check=True)
    agent = Path.home() / "Library/LaunchAgents" / (label + ".plist")
    if agent.exists():
        os.replace(agent, agent.with_suffix(".plist.disabled"))
    if subprocess.run(["/bin/launchctl", "print", service], capture_output=True).returncode == 0:
        raise SystemExit("Service still loaded; check launchctl status")
    print("Updater stopped and disabled at login. Runtime files and logs retained.")
    print("The custom clock page expires within 10 minutes after its final refresh.")


if __name__ == "__main__":
    main()
