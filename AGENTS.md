# Repository guidance

## Product boundary

`shoutx` provides runtime primitives at explicitly named output boundaries. It
does not trace attack paths through an entire workflow and does not make a value
safe for later parsers or operations.

- Treat values reaching `shoutx` as data. Direct `${{ ... }}` expansion into a
  workflow `run:` block is a static-analysis concern outside this project.
- Provider writers use `PROVIDER:DESTINATION`; reusable encoders use
  `LANGUAGE:CONTEXT`.
- Do not add raw passthrough or a context-independent escape command.
- Require an explicit interface for lossy normalization.
- Complete validation, encoding, and resource-limit checks before beginning
  stdout output. Do not promise transactional recovery from an I/O failure
  after writing begins.
- Record framing does not authorize attacker-selected paths, commands,
  processes, or other resources.

Read `README.md`, `docs/design.md`, `docs/threat-model.md`, and
`docs/test-plan.md` before changing observable behavior. Resolve contradictions
between them rather than choosing one silently. Specify security-relevant CLI
behavior before implementing it. `docs/implementation-plan.md` records the
intended architecture and sequencing but does not override the product
contract.

For GitHub Actions behavior, verify claims against current official GitHub
documentation and the repository-pinned `actions/runner` implementation. Do
not infer one destination's behavior solely from a shared local parser model.

## Implementation constraints

- Keep the executable native and dependency-light. New dependencies require a
  concrete security or portability benefit and corresponding lockfile and
  license review.
- Preserve byte-level process-I/O behavior and platform-specific error
  handling. Avoid lossy conversion of process arguments or input.
- Keep destination policy explicit even when implementations share parsing,
  validation, or record-construction code.
- Do not expose a documented command until its contract and implementation are
  complete.
- Do not add a Japanese README or other translated README to the public
  repository.

Rust development uses the toolchain pinned in `rust-toolchain.toml`. The MSRV
is declared separately in `Cargo.toml` and must remain covered by CI. `mise` is
optional and currently pins only the .NET SDK used by the runner differential
suite.

## Verification

Run checks proportional to the change. For Rust changes, the normal local
baseline is:

```sh
cargo fmt --all -- --check
cargo test --all-targets
cargo clippy --all-targets -- -D warnings
```

Changes affecting GitHub Actions record parsing or compatibility also require:

```sh
mise install
scripts/test-runner-oracle.sh
```

`mise` is not required for ordinary Cargo work. If `cargo-deny` is installed,
dependency changes should also run:

```sh
cargo deny --all-features --locked check advisories bans licenses sources
```

Tests for validation, normalization, encoding, randomness, or size failures
must assert that stdout is empty. Test the exact stdout bytes, stderr policy,
and exit status where the CLI contract is involved.

## Change workflow

- Keep pull requests focused and explain any security-contract consequence.
- Let CI and configured review complete before merging; resolve completed
  review threads.
- Do not merge without explicit maintainer direction.
- After merging, delete the local and remote work branch and update `main`.
- Documentation-only changes, including this file, should leave the expensive
  CI jobs skipped through the change detector in `.github/workflows/ci.yml`.
