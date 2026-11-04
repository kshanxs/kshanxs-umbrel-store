# Changelog

## Unreleased

- New app: T3 Code Nightly. Runs the T3 Code server on the Umbrel host with your Claude Code
  login, pairs the browser from the Umbrel dashboard, and moves to new nightlies at 04:00

## 1.0.0

First release of kshanx's App, a community app store for umbrelOS by kshanxs.

- Apps: GP Sync 1.0.0, 9Router, CLIProxyAPI
- Every hour the store checks each app's upstream image (Docker Hub or ghcr.io) and updates
  itself: version, image (pinned by digest) and release notes
- Every change is validated before it lands
