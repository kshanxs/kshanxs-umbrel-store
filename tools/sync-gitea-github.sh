#!/usr/bin/env bash
# Keep main the same on Gitea (main copy) and GitHub (public copy Umbrel installs from).
# Copies whichever side is ahead to the other. If both changed, it does nothing and logs it.
# Only touches remote branches, never the local working copy.
set -euo pipefail
cd /home/umbrel/umbrel-local-apps/src
git fetch -q origin main
git fetch -q github main
G=$(git rev-parse origin/main)
H=$(git rev-parse github/main)
if [[ "$G" == "$H" ]]; then
  exit 0
elif git merge-base --is-ancestor "$G" "$H"; then
  git push -q http://localhost:8085/kshanxs/kshanxs-umbrel-store.git "$H:refs/heads/main"
  echo "Copied GitHub -> Gitea: $(git log -1 --format=%s "$H")"
elif git merge-base --is-ancestor "$H" "$G"; then
  git push -q github "$G:refs/heads/main"
  echo "Copied Gitea -> GitHub: $(git log -1 --format=%s "$G")"
else
  echo "Gitea and GitHub both have new commits; not syncing. Merge them by hand." >&2
  exit 1
fi
