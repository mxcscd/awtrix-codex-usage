# Codex usage on an AWTRIX pixel clock

A compact Codex quota display for the **Ulanzi TC001 running AWTRIX 3**.
Tested on AWTRIX **0.98**. No firmware changes are made by these scripts.

```text
        9%       10%
       5-hour   weekly
  [weekly usage bar + white time marker]
```

Both numbers show **percent used**, not remaining. Five-hour usage is green below
50%, amber below 80%, and red at 80% or above. Weekly colour compares usage with
elapsed time: green behind pace, amber ahead, and red when more than 15 percentage
points ahead or at least 90% used. The white pixel marks how much of the weekly
window has passed. Missing windows show `--`. The 3×5 font fits `100% 100%`
without scrolling. Other clock pages remain in rotation.

## Mechanism

Every two minutes, a macOS LaunchAgent runs the Python updater. It starts the local
Codex app-server over stdio, initializes it, and calls `account/rateLimits/read`.
Codex handles authentication using the account signed in on **this Mac**. The
updater renders the quota data and POSTs drawing commands to the clock's local
AWTRIX HTTP API. It makes no inference requests.

The clock receives only display commands. The updater does not read, copy, or
upload `auth.json`, prompts, code, or chat history. It uses Python's standard
library and requires no pip packages, API key, MQTT broker, or Home Assistant.

## Set up on a new Mac

1. Install Python **3.9+** and Codex CLI or the Codex desktop app. Sign in to Codex
   with the account and workspace whose quota you want displayed. With the CLI,
   use `codex login`. A company account must expose compatible quota windows;
   API-key-only authentication does not provide ChatGPT subscription quotas.
2. Connect the clock and Mac to a network where the Mac can reach the clock's
   HTTP interface. USB-C powers the clock; display data travels over Wi-Fi. Open
   `http://CLOCK_IP/api/stats` to confirm reachability. Note the clock's address.
3. Clone this repository, or use GitHub's **Code → Download ZIP** and extract it.
4. From the repository directory, check your account's usage without contacting
   or changing the clock:

   ```sh
   python3 usage_display.py --inspect
   ```

5. Send one update, replacing the example address with your clock's address:

   ```sh
   python3 usage_display.py --host 192.168.1.50
   ```

6. Install automatic refresh on this Mac:

   ```sh
   python3 install.py --host 192.168.1.50
   ```

The installer detects the current user's paths, Python executable, and Codex CLI.
If discovery fails, pass `--codex /absolute/path/to/codex` to either script.
It searches PATH and standard system/user Codex app locations. Sign in normally
on the new Mac; **do not transfer authentication files from the old Mac**.

Preview the login-service configuration without writing or starting anything:

```sh
python3 install.py --host 192.168.1.50 --dry-run
```

## Background service and verification

The updater is deployed outside Documents to avoid macOS background-service
restrictions on that folder:

- Runtime: `~/Library/Application Support/CodexAWTRIX/`
- Login service: `~/Library/LaunchAgents/local.codex.awtrix-usage.plist`
- Logs: `usage-display.log` and `usage-display-error.log` inside the runtime folder

Check the first successful refresh:

```sh
tail -n 3 "$HOME/Library/Application Support/CodexAWTRIX/usage-display.log"
tail -n 10 "$HOME/Library/Application Support/CodexAWTRIX/usage-display-error.log"
launchctl print "gui/$(id -u)/local.codex.awtrix-usage"
```

The job runs briefly and exits between refreshes; `not running` is normal when
its last exit code is `0`. The Mac must be awake, signed in, and able to reach the
clock. Pages expire after **10 minutes** without a refresh so stale data disappears.
No separate Codex conversation or model turn is created.

To change the clock address, Codex path, or interval, rerun `install.py` with the
new arguments. `--interval` defaults to 120 seconds and must be at least 60.
To apply source updates, rerun the installer; the service uses a deployed copy.

## Stop or move to another Mac

```sh
python3 uninstall.py
```

This unloads the updater and renames its login-service file to `.plist.disabled`.
It retains runtime files and logs. Stop the old Mac's updater before enabling
another account on a new Mac; otherwise both Macs can overwrite the same page.
To resume on a Mac, rerun `install.py`.

## Limitations

- AWTRIX 3 API only; AWTRIX NG uses a different API.
- The clock must have an accessible HTTP API without authentication configured.
- Displays the `codex` quota bucket returned by Codex, not API billing or a
  company-wide spending dashboard. Some account types may return no quota data.
- Agent activity indicators, hooks, sounds, and reset countdown pages are not included.
- No firmware images, personal device backups, credentials, or machine-specific
  launch-service files are included in this repository.

## Credits

Layout and weekly pace colours are adapted from
[tolixx/claude-meter](https://github.com/tolixx/claude-meter), under the MIT license;
see [claude-meter-LICENSE](claude-meter-LICENSE). The Codex account reader and
portable installer are provided here under [MIT](LICENSE).

References:

- [Codex app-server protocol](https://learn.chatgpt.com/docs/app-server)
- [AWTRIX 3 API](https://github.com/Blueforcer/awtrix3/blob/main/docs/api.md)
