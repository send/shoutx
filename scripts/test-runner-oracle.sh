#!/bin/sh
set -eu

root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
runner_commit=397b032cbf865e9c3ddfab89d533ec19325e1273
runner_dir="$root/target/runner-oracle/actions-runner"
corpus="$root/target/runner-oracle/corpus.json"
path_corpus="$root/target/runner-oracle/path-corpus.json"
mask_corpus="$root/target/runner-oracle/mask-corpus.json"
staging_dir=

cleanup() {
  if [ -n "$staging_dir" ]; then
    rm -rf -- "$staging_dir"
  fi
}
trap cleanup EXIT HUP INT TERM

case "$(uname -s)-$(uname -m)" in
  Linux-x86_64) runtime=linux-x64 ;;
  Linux-aarch64 | Linux-arm64) runtime=linux-arm64 ;;
  Darwin-x86_64) runtime=osx-x64 ;;
  Darwin-arm64) runtime=osx-arm64 ;;
  *) echo "error: unsupported local oracle platform" >&2; exit 1 ;;
esac

if [ -n "${SHOUTX_RUNNER_SOURCE:-}" ]; then
  actual_commit=$(git -C "$SHOUTX_RUNNER_SOURCE" rev-parse HEAD)
  if [ "$actual_commit" != "$runner_commit" ]; then
    echo "error: runner checkout is not the pinned commit" >&2
    exit 1
  fi
  staging_dir=$(mktemp -d "${TMPDIR:-/tmp}/shoutx-runner-oracle.XXXXXX")
  runner_dir="$staging_dir/actions-runner"
  mkdir "$runner_dir"
  git -C "$SHOUTX_RUNNER_SOURCE" archive HEAD | tar -x -C "$runner_dir"
elif [ ! -d "$runner_dir/.git" ]; then
  mkdir -p "$(dirname -- "$runner_dir")"
  git clone --filter=blob:none --no-checkout https://github.com/actions/runner.git "$runner_dir"
  git -C "$runner_dir" fetch --depth 1 origin "$runner_commit"
  git -C "$runner_dir" checkout --detach "$runner_commit"
fi

if [ -d "$runner_dir/.git" ]; then
  actual_commit=$(git -C "$runner_dir" rev-parse HEAD)
  if [ "$actual_commit" != "$runner_commit" ]; then
    echo "error: runner checkout is not the pinned commit" >&2
    exit 1
  fi
fi

dotnet_command=$(command -v dotnet 2>/dev/null || true)
case "$dotnet_command" in
  */mise/shims/dotnet)
    dotnet_bin=$(mise -C "$root" which dotnet)
    dotnet_run() { "$dotnet_bin" "$@"; }
    ;;
  ?*)
    dotnet_run() { "$dotnet_command" "$@"; }
    ;;
  *)
    if ! command -v mise >/dev/null 2>&1; then
      echo "error: install .NET 8.0.424 directly or with mise" >&2
      exit 1
    fi
    dotnet_bin=$(mise -C "$root" which dotnet)
    dotnet_run() { "$dotnet_bin" "$@"; }
    ;;
esac

cd "$root"
mkdir -p "$(dirname -- "$corpus")"
SHOUTX_CORPUS_PATH="$corpus" \
  cargo test --test runner_differential_fixture export_runner_corpus -- --ignored
SHOUTX_PATH_CORPUS_PATH="$path_corpus" \
  cargo test --test path_runner_fixture export_path_corpus -- --ignored
SHOUTX_MASK_CORPUS_PATH="$mask_corpus" \
  cargo test --test mask_runner_fixture export_mask_corpus -- --ignored
cp tests/runner-oracle/ShoutxDifferentialL0.cs \
  "$runner_dir/src/Test/L0/Worker/ShoutxDifferentialL0.cs"
(
  cd "$runner_dir/src"
  actual_sdk=$(dotnet_run --version)
  if [ "$actual_sdk" != 8.0.424 ]; then
    echo "error: expected .NET SDK 8.0.424, got $actual_sdk" >&2
    exit 1
  fi
  DOTNET_CLI_TELEMETRY_OPTOUT=1 dotnet_run build Test/Test.csproj \
    --configuration Release \
    -p:PackageRuntime="$runtime" \
    -p:NuGetAudit=false
  SHOUTX_CORPUS="$corpus" SHOUTX_PATH_CORPUS="$path_corpus" SHOUTX_MASK_CORPUS="$mask_corpus" DOTNET_CLI_TELEMETRY_OPTOUT=1 \
    dotnet_run test Test/Test.csproj \
    --configuration Release \
    --no-build \
    --no-restore \
    --filter 'FullyQualifiedName~ShoutxDifferentialL0'
)
