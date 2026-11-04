# T3 Code Nightly for Umbrel

Runs the [T3 Code](https://t3.codes) server (nightly track) on your Umbrel so you can
use Claude Code and other coding agents from a browser, the T3 Code desktop app or
the phone app.

## How it works

- The `server` container is privileged and only runs `nsenter` to start
  [`run.sh`](run.sh) **on the Umbrel host as the `umbrel` user**. Agents therefore see
  the same home folder, tools and Claude Code login as an Umbrel terminal.
- `run.sh` downloads the newest nightly from GitHub (checksum verified) into
  `data/versions`, keeps the current and previous version, and runs
  `t3 serve --lan` on port **3773** (local network and Tailscale only).
  New nightlies are fetched every 3 hours and switched to between 04:00 and 05:00.
- Opening the app from the Umbrel dashboard goes through Umbrel's login to
  [`pair.py`](pair.py), which pairs the browser with a one-time link and opens T3 Code.
  Open `/pair` on the app's address to pair again.
- T3 Code data lives in `~/umbrel/app-data/kshan-t3code/data/t3`.
- A `t3` command is added to `~/.local/bin` (if none is there), so `t3 pair`,
  `t3 thread ...` and other commands work in an Umbrel terminal.

## Requirements

Claude Code installed on the Umbrel (`~/.local/bin/claude`) and signed in once.

## Security

Anyone paired with T3 Code can run commands on your Umbrel as `umbrel`. Pair only
your own devices, and revoke old ones in T3 Code under **Settings → Sharing & access**.
