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
`docs/test-plan.md` before changing observable behavior, then follow their links
to every relevant normative command specification under `docs/commands/` or
decision record. Resolve
contradictions between them rather than choosing one silently. Specify
security-relevant CLI behavior before implementing it.
`docs/implementation-plan.md` records the intended architecture and does not
override the product contract; `docs/implementation-history.md` is historical
context only.

Preserve a single source of truth for every fact or requirement. Follow the
ownership map in [`docs/README.md`](docs/README.md); update the authoritative
document and replace duplicates elsewhere with links. Do not make the README,
an ADR, a compatibility note, a test plan, and a command specification
independently normative for the same behavior.

For GitHub Actions behavior, verify claims against current official GitHub
documentation and the repository-pinned `actions/runner` implementation. Do
not infer one destination's behavior solely from a shared local parser model.
For any text protocol, identify whether delimiter and prefix operations are
byte-wise, ordinal, or locale-sensitive; do not infer consumer acceptance from
producer success. When behavior can depend on culture or collation, include
the consumer process, parser fallbacks, ICU/NLS backend, and relevant OS
generations in the evidence. See the
[GitHub Actions workflow-command compatibility note](docs/compatibility/github-actions-workflow-command-parser.md).

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
CARGO_TARGET_DIR=target/stable cargo test --all-targets --no-default-features
CARGO_TARGET_DIR=target/stable cargo clippy --all-targets --no-default-features -- -D warnings
scripts/verify-stable-docs.sh
```

Default and official builds expose all eight commands. There is no stdout
research feature. Preserve explicit mask/annotation test targets and fresh
nonempty exported corpora when changing test orchestration; a zero-test run is
not evidence. Consumer compatibility remains limited to the design-owned profile.

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

## Independent design review

For a substantial security-contract or compatibility change, use an
independent Fable review when the maintainer requests it or when another model
is likely to catch assumptions shared by the author and the configured GitHub
review. This is additional evidence, not a substitute for checking current
official documentation, the pinned runner, tests, or maintainer approval.

When the installed Claude Code CLI offers the `fable` model, run a read-only
review from the repository root. Confirm the locally installed flags with
`claude --help` rather than guessing if the CLI has changed. Prepare the diff
outside the worktree so the reviewer does not need a shell tool, and capture
non-interactive JSON output without terminal truncation:

```sh
review_dir=$(mktemp -d)
git status --short --untracked-files=all > "$review_dir/status.txt"
git diff --no-ext-diff --binary --merge-base main -- > "$review_dir/change.diff"
claude -p --model fable \
  --safe-mode \
  --permission-mode dontAsk \
  --permission-prompts none \
  --tools "Read,Grep,Glob" \
  --allowedTools "Read,Grep,Glob" \
  --add-dir "$review_dir" \
  --no-session-persistence \
  --max-budget-usd 5 \
  --output-format json \
  "Review the current shoutx change as an independent, read-only security and design reviewer. Read AGENTS.md, $review_dir/status.txt, $review_dir/change.diff, and the relevant product-contract documents. Untracked paths appear only in status.txt, so read any relevant untracked file from the worktree. Check for contradictory contracts, injection paths, lossy or platform-dependent behavior, unsupported claims, missing failure cases, and tests that could validate only their own model. Flag claims that the primary agent must verify against external documentation or runner source; do not imply that you fetched sources unavailable to your tool set. Return concise findings first, ordered by severity, with file and line references; keep the complete response below 4,000 words. If there are no findings, say so explicitly. Do not edit files." \
  > "$review_dir/result.json" 2> "$review_dir/stderr.log"
```

Before preparing the diff, verify that local `main` is synchronized with
`origin/main`; `--merge-base` prevents an out-of-date feature branch from
presenting unrelated mainline changes as part of the review.

Do not silently substitute Opus or another model when `fable` is unavailable;
report that the independent Fable review could not be run and continue with a
documented self-review unless the maintainer asks for a substitute. After the
process exits, require status 0 and read `result.json` plus `stderr.log`. In the
JSON result, `subtype` must be `success`, `is_error` must be false, the review
text must be present in `result`, required inspection must not appear in
`permission_denials`, and `modelUsage` must name a Fable model such as
`claude-fable-5-1`. Help text mentioning the alias does not prove access, and a
result using only another model is not a Fable review. Do not configure a
fallback model for this invocation. The temporary directory may be removed
after the result and any findings have been recorded.

Reviews can take several minutes. Start the command through an execution runner
that can yield a reusable process handle, allow up to 30 minutes, and poll that
same handle when the initial call yields. Do not launch a duplicate merely
because the process is quiet. Report an exceeded limit rather than starting the
review again. Review any denied tool call and do not accept a result whose
required evidence was denied.

Evaluate every finding against primary evidence and record whether it was
accepted or rejected; do not defer automatically to the reviewer. One review
round after the draft is normally sufficient. Re-run Fable after material
changes made in response to its findings. A third round is warranted only when
the second review identifies a new substantive issue or the response changes
the security contract again.

## CI and GitHub review monitoring

When asked to monitor a pull request, keep a live wait running until both CI and
the configured Codex review have reached terminal states. A Codex summary or
review-start comment is evidence that review began, not that it completed.

Record the pull request's current head SHA before waiting. CI is complete only
when every required check is terminal; for documentation-only changes, also
confirm that the change detector passed and expensive jobs were skipped rather
than silently omitted. Codex review has produced a terminal result for that SHA
only when one of the following is observed:

- `chatgpt-codex-connector[bot]` submits a review whose `commit_id` is that
  exact SHA; or
- the bot posts an explicit no-findings comment that names that exact SHA as
  the reviewed commit; or
- the bot adds a thumbs-up reaction to an explicit `@codex review` request that
  was created after the current head was pushed. Record that request's comment
  ID together with the head SHA, and accept a reaction only from that exact
  comment.

A submitted review or SHA-matched completion comment is only a terminal review
event. It is not convergence when that review created an unresolved thread.
Include the unresolved-thread count in the wait condition and finish only when
it is zero; do not postpone this check until after the monitor has already
declared success. Match the reviewed SHA from structured API data or the
explicit `Reviewed commit` field, not merely from arbitrary comment text.

Do not treat an earlier-commit review, the existence or disappearance of a
summary comment, or an empty API result as successful completion. The wait must
surface API failures and print the terminal evidence it observed. After the
wait exits, query CI, reviews, inline comments, unresolved review threads, and
the relevant reaction once more before reporting success.

For each valid finding, make the scoped correction, reply with the addressing
commit, and resolve the thread. Any pushed correction changes the head SHA:
discard the old wait, request review of the new head when needed, and start a
new SHA-specific monitor. Do not merge until all findings are resolved, the
latest-head review has converged, CI is successful, and the maintainer has
explicitly directed the merge.

## Change workflow

- Keep pull requests focused and explain any security-contract consequence.
- Let CI and configured review complete before merging; resolve completed
  review threads.
- Do not merge without explicit maintainer direction.
- After merging, delete the local and remote work branch and update `main`.
- Documentation-only changes, including this file, should leave the expensive
  CI jobs skipped through the change detector in `.github/workflows/ci.yml`.
