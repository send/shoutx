#!/usr/bin/env bash

set -euo pipefail

readonly version="0.2.0"
readonly target="x86_64-unknown-linux-musl"
readonly archive="shoutx-v${version}-${target}.tar.gz"
readonly archive_sha256="2fc86f8c69b1fafb0e372337023d478f1a6b7b9074962918bc5beb29429adeb2"
readonly install_dir="${RUNNER_TEMP:?RUNNER_TEMP must be set}/shoutx-bootstrap/bin"

work_dir=$(mktemp -d "${RUNNER_TEMP}/shoutx-bootstrap.XXXXXX")
trap 'rm -rf "$work_dir"' EXIT

curl --fail --location --silent --show-error \
  --output "$work_dir/$archive" \
  "https://github.com/send/shoutx/releases/download/v${version}/${archive}"

printf '%s  %s\n' "$archive_sha256" "$work_dir/$archive" | sha256sum --check --status
tar -xzf "$work_dir/$archive" -C "$work_dir"

install -d "$install_dir"
install -m 0755 \
  "$work_dir/shoutx-v${version}-${target}/shoutx" \
  "$install_dir/shoutx"

test "$("$install_dir/shoutx" --version)" = "shoutx $version"
