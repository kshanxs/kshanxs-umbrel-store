#!/bin/bash
# T3 Code Nightly for Umbrel.
#
# Runs on the Umbrel host as user umbrel (the app container starts it with
# nsenter), so T3 Code's agents see the same files, tools and Claude Code login
# as a normal terminal. It installs the newest nightly, keeps T3 Code and the
# pairing helper running, and moves to a newer nightly at 04:00-05:00.
set -u

APP_DIR="$1"
DATA_DIR="$APP_DIR/data"
VERSIONS="$DATA_DIR/versions"
PORT=3773
REPO=pingdotgg/t3code
CHECK_EVERY=10800  # seconds between checks for a new nightly

export T3CODE_HOME="$DATA_DIR/t3"
export T3_VERSIONS="$VERSIONS"
export PATH="$HOME/.local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"

log() { printf '%s t3-umbrel: %s\n' "$(date '+%F %T')" "$*"; }

case "$(uname -m)" in
  x86_64 | amd64) ARCH=x64 ;;
  aarch64 | arm64) ARCH=arm64 ;;
  *) log "unsupported CPU $(uname -m)"; exit 1 ;;
esac

mkdir -p "$VERSIONS" "$T3CODE_HOME"

# Newest nightly version, from the npm registry (no GitHub rate limit).
latest_nightly() {
  curl -fsS -m 30 https://registry.npmjs.org/-/package/t3/dist-tags |
    python3 -c 'import json,sys; print(json.load(sys.stdin).get("nightly",""))'
}

current_version() { readlink "$VERSIONS/current" 2>/dev/null; }

# Download, verify and unpack one version into $VERSIONS/<version>.
install_version() {
  local v="$1" dir="$VERSIONS/$1" tmp asset base want got
  [ -x "$dir/t3" ] && return 0
  asset="t3-$v-linux-$ARCH.tar.gz"
  base="https://github.com/$REPO/releases/download/v$v"
  tmp="$(mktemp -d "$VERSIONS/.download-XXXXXX")" || return 1
  log "downloading $v"
  if curl -fsSL -m 1800 -o "$tmp/$asset" "$base/$asset" &&
    curl -fsSL -m 60 -o "$tmp/SHA256SUMS" "$base/SHA256SUMS"; then
    want="$(awk -v f="$asset" '$2 == f || $2 == "*" f { print $1 }' "$tmp/SHA256SUMS")"
    got="$(sha256sum "$tmp/$asset" | cut -d' ' -f1)"
    if [ -n "$want" ] && [ "$want" = "$got" ] &&
      mkdir "$tmp/x" && tar -xzf "$tmp/$asset" -C "$tmp/x" &&
      [ -x "$tmp/x/t3-$v-linux-$ARCH/t3" ]; then
      mv "$tmp/x/t3-$v-linux-$ARCH" "$dir"
      rm -rf "$tmp"
      log "installed $v"
      return 0
    fi
    log "checksum or unpack failed for $v"
  else
    log "download failed for $v"
  fi
  rm -rf "$tmp"
  return 1
}

# Point "current" at a version and keep only it and the one before.
use_version() {
  local v="$1" old
  old="$(current_version)"
  ln -sfn "$v" "$VERSIONS/current"
  rm -f "$DATA_DIR/pending-version"
  [ -n "$old" ] && [ "$old" != "$v" ] && log "switched $old -> $v"
  for d in "$VERSIONS"/*/; do
    d="$(basename "$d")"
    case "$d" in "$v" | "$old" | current) continue ;; esac
    rm -rf "${VERSIONS:?}/$d"
  done
}

# `t3` in the terminal talks to this server (t3 pair, t3 thread, ...).
install_cli() {
  local cli="$HOME/.local/bin/t3"
  if [ -e "$cli" ] && ! grep -q 'T3 Code Nightly Umbrel app' "$cli" 2>/dev/null; then
    return 0  # someone else's t3, leave it alone
  fi
  mkdir -p "$HOME/.local/bin"
  cat > "$cli.tmp" <<CLI
#!/bin/sh
# Added by the T3 Code Nightly Umbrel app.
export T3CODE_HOME="$T3CODE_HOME"
exec "$VERSIONS/current/t3" "\$@"
CLI
  chmod 755 "$cli.tmp" && mv "$cli.tmp" "$cli"
}

# First start (or app restart): move to the newest nightly right away.
v="$(latest_nightly)"
if [ -n "$v" ] && install_version "$v"; then
  use_version "$v"
fi
until [ -x "$VERSIONS/current/t3" ]; do
  log "no T3 Code installed yet, retrying in 60 s"
  sleep 60
  v="$(latest_nightly)" && [ -n "$v" ] && install_version "$v" && use_version "$v"
done
install_cli

# Background: fetch new nightlies; they are switched to at 04:00-05:00.
(
  while sleep "$CHECK_EVERY"; do
    v="$(latest_nightly)"
    if [ -n "$v" ] && [ "$v" != "$(current_version)" ] && install_version "$v"; then
      echo "$v" > "$DATA_DIR/pending-version"
      log "nightly $v is ready, switching at 04:00"
    fi
  done
) &
UPDATER_PID=$!

# Background: pairing helper behind Umbrel's login.
(
  while true; do
    python3 "$APP_DIR/pair.py"
    log "pairing helper stopped, restarting in 5 s"
    sleep 5
  done
) &
HELPER_PID=$!

SERVER_PID=
stop_all() {
  log "stopping"
  [ -n "$SERVER_PID" ] && kill -TERM "$SERVER_PID" 2>/dev/null
  pkill -TERM -P "$HELPER_PID" 2>/dev/null
  kill -TERM "$UPDATER_PID" "$HELPER_PID" 2>/dev/null
  wait
  exit 0
}
trap stop_all TERM INT

while true; do
  cd "$HOME" || exit 1
  log "starting T3 Code $(current_version) on port $PORT"
  "$VERSIONS/current/t3" serve --port "$PORT" --lan --no-browser "$HOME" &
  SERVER_PID=$!
  while kill -0 "$SERVER_PID" 2>/dev/null; do
    sleep 60 & wait $!
    pending="$(cat "$DATA_DIR/pending-version" 2>/dev/null)"
    if [ -n "$pending" ] && [ -x "$VERSIONS/$pending/t3" ] && [ "$(date +%H)" = 04 ]; then
      use_version "$pending"
      log "restarting for the new nightly"
      kill -TERM "$SERVER_PID" 2>/dev/null
    fi
  done
  wait "$SERVER_PID"
  log "T3 Code exited with $?, restarting in 5 s"
  SERVER_PID=
  sleep 5
done
