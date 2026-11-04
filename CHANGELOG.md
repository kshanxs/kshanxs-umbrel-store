# Changelog

## 1.0.0

First release of kshanx's App, a community app store for umbrelOS by kshanxs.

- Apps: GP Sync 1.0.0, 9Router, CLIProxyAPI
- Every hour the store checks each app's upstream image (Docker Hub or ghcr.io) and updates
  itself: version, image (pinned by digest) and release notes
- Every change is validated before it lands
