# Security policy

## Supported versions

Security fixes target the latest published release. Users should reproduce an
issue against that release when possible and upgrade when a fix is published.
Older releases do not receive separate security support.

## Reporting a vulnerability

Do not open a public issue for a suspected vulnerability. Use GitHub's
[private vulnerability report](https://github.com/send/shoutx/security/advisories/new)
so that the report and any remediation can be coordinated before disclosure.

Include enough information to distinguish a boundary failure from behavior
outside the documented guarantee:

- the affected `shoutx` version, operating system, runner, and shell;
- the exact command, input channel, and destination boundary;
- a minimal input and reproducible workflow or command sequence;
- the emitted bytes, parsed result, diagnostics, and exit status, as relevant;
- the security impact and any required attacker capabilities; and
- for release-integrity reports, the asset name, digest, attestation result,
  workflow run, and source commit when available.

Use synthetic values instead of real credentials or other sensitive data.
Only test repositories, runners, and accounts that you own or are authorized
to assess.

Relevant reports include, but are not limited to:

- escaping the record created by an implemented GitHub Actions writer;
- validation, encoding, or resource-limit failures that emit partial stdout;
- disclosure of attacker-controlled values or secrets through diagnostics; and
- release artifact, checksum, provenance, or workflow-integrity failures.

The documented trust assumptions and exclusions in the
[threat model](docs/threat-model.md) still apply. Examples include shell
injection that happens before `shoutx` starts, unsafe interpretation at a later
boundary, authorization of an attacker-controlled path, and I/O failure after
stdout writing has begun. Reports that show a documented exclusion has a wider
or different impact are still useful.

There is currently no bug-bounty program or guaranteed response timeline.
