# Design notes

This document records decisions and open questions while `shoutx` is being
designed. The README defines the intended product contract; this file may
describe alternatives that have not been accepted.

Security scope and trust assumptions are defined in the
[threat model](threat-model.md).

## Product boundary

`shoutx` prevents injection when CI workflows write values across output
boundaries. It provides runtime writers and context encoders rather than static
workflow analysis or attack-path discovery.

The initial provider is GitHub Actions. Provider-specific behavior is isolated
behind namespaced commands so support for other workflow engines can be added
without pretending their protocols are interchangeable.

## MVP commands

Provider-specific writers:

```text
shoutx github-actions:output [--first-line | --join-lines STRING | --multiline] NAME [VALUE]
shoutx github-actions:env    [--first-line | --join-lines STRING | --multiline] NAME [VALUE]
shoutx github-actions:path   [VALUE]
```

Reusable context encoders under consideration for v1.0:

```text
shoutx shell:arg      [VALUE]
shoutx markdown:text  [VALUE]
```

## Security invariants

1. A command protects only the interpretation boundary named by that command.
2. Validation, encoding, and resource-limit failures occur before stdout output
   begins. I/O failure after writing begins may leave partial bytes.
3. Single-line record modes never accept line breaks implicitly.
4. Lossy normalization is always explicit.
5. Multiline framing never uses a delimiter that can terminate the value.
6. NUL is rejected.
7. Raw passthrough is not provided.
8. Names and paths are validated according to their destination protocol.
9. Diagnostics never include untrusted values unless safely represented.
10. Documentation distinguishes structural encoding from authorization and
   semantic validation.
11. Documentation does not imply protection from injection that occurs before
   `shoutx` starts or after its selected boundary has been crossed.
12. Input and output are valid UTF-8, and record framing uses LF on every OS.
13. Every input path has the same documented hard size limit.

## Command model

Provider writers use `PROVIDER:DESTINATION`. Reusable encoders use
`LANGUAGE:CONTEXT`.

A value argument is used when present. Otherwise, input is read from stdin when
stdin is not a terminal. Commands fail instead of waiting for interactive input.

Encoded output is written to stdout and diagnostics to stderr. This preserves
normal Unix composition and keeps destination selection visible in the calling
workflow.

## Open questions

- Whether `shell:arg` belongs in v1.0 and which POSIX shells are covered.
- Whether `markdown:text` belongs in v1.0 and what rendering guarantees it
  can accurately make across supported surfaces.
- The exact grammar for GitHub Actions output and environment variable names.
- The precise semantics of `--first-line`, including empty first lines and line
  ending normalization.
- Whether `--join-lines STRING` is the right interface and how consecutive or
  trailing line breaks are handled.
- The hard input limit required to validate before beginning stdout output.
- Cross-platform rules for `$GITHUB_PATH`, especially Windows runners.
- Implementation language, packaging, and supported installation methods.
- Whether provider extensions are compiled in, discovered as executables, or
  loaded through another plugin mechanism.
- Compatibility and versioning rules for provider extensions.
- Whether conservative name grammars should be stricter than the GitHub Actions
  runner parser, which currently accepts any non-empty record name.

## Deferred scope

- Static workflow analysis and attack-path discovery.
- General JSON and HTML encoders.
- Arbitrary document sanitization.
- Providers other than GitHub Actions.
- A stable third-party plugin API.
