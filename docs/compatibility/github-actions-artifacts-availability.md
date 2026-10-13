# GitHub Actions artifact declaration availability

This note owns hosted-runner observations, not a supported shoutx command.
The [artifact decision](../decisions/github-actions-artifacts.md) owns adoption
rationale; the [command contract](../commands/github-actions-artifacts.md) and
[design profile](../design.md#artifact-consumer-scope) own behavior and scope.

## Writer integration observations

On 2026-10-14 JST, [CI run 38439704470][writer-run] at producer commit
`6b514f4a8618188fc3203858e0cf75c69a74c4cf` completed both `Declare file and OCI
subjects through shoutx` and `Verify artifact subjects in following step`
successfully on all four profile rows:

| Hosted label / architecture | Job |
| --- | --- |
| `ubuntu-22.04` / x64 | [115442827214](https://github.com/send/shoutx/actions/runs/38439704470/job/115442827214) |
| `ubuntu-24.04` / x64 | [115442827229](https://github.com/send/shoutx/actions/runs/38439704470/job/115442827229) |
| `macos-15` / arm64 | [115442827296](https://github.com/send/shoutx/actions/runs/38439704470/job/115442827296) |
| `windows-2025` / x64 | [115442827237](https://github.com/send/shoutx/actions/runs/38439704470/job/115442827237) |

The [versioned fixture][writer-fixture] executes the built shoutx binary,
appends two file declarations (plain and Unicode names) and three opaque OCI
declarations (SHA-256/384/512), then compares the entire next-step schema-1
list against independently expected names, kinds, and digests. No opt-in is
forced. Missing variables, zero-byte lists, missing/extra subjects, or changed
fields fail. The same jobs also passed the pinned Runner handler comparison.
These are completed-step observations, not a claim that the entire CI run or
latest-head review had completed at recording time. Current-head CI and review
remain separate PR gates. No registry object or file authorization is verified.

[writer-run]: https://github.com/send/shoutx/actions/runs/38439704470
[writer-fixture]: https://github.com/send/shoutx/blob/6b514f4a8618188fc3203858e0cf75c69a74c4cf/tests/workflow-smoke/hosted_artifacts.py

## Probe and observations

Both attempts ran the same [workflow source at
`b9b0f6ab040f386e652aa2c7a16c5e374fe541e1`][source], with `contents: read`,
without checkout, third-party actions, or forced feature flags. It writes a
known UTF-8 file, appends its explicit `file://` declaration, and in a subsequent
step requires a nonempty artifact list, schema version 1, exactly one subject,
and the expected basename, `file` kind, and SHA-256 digest. A missing/empty list
or any mismatch fails. The workflow file is no longer on main; the second
attempt was a re-run of the historical run, not a test of current main.

| Attempt | Observation date (JST) | Result |
| --- | --- | --- |
| [1][attempt1] | 2026-09-28 | All three jobs failed: variables existed but the later list file had zero bytes. |
| [2][attempt2] | 2026-10-14 (2026-10-13 16:40 UTC) | All three declaration and verification steps passed. |

Attempt 2 used Runner 2.337.0 on these hosted images:

| Label | Image | Image version | Successful job |
| --- | --- | --- | --- |
| `ubuntu-latest` | `ubuntu-24.04` | `20261004.327.1` | [115417623392][linux] |
| `macos-latest` | `macos-26-arm64` | `20260907.0351.1` | [115417623399][mac] |
| `windows-latest` | `windows-2025-vs2026` | `20260925.250.1` | [115417623103][windows] |

This is positive evidence of actual file-declaration processing on the sampled
hosts, not just environment-variable exposure. It does not establish rollout
to every repository, runner image/architecture, self-hosted installation, or
future run. It does not test OCI declarations, shoutx encoding, adversarial
inputs, or the candidate's remaining acceptance cases. Image and runner
versions come from job setup logs; assertion success comes from the completed
verification steps, not from searching logs for echoed script text.

The adoption consequence and any required implementation checks are owned by
the [artifact decision](../decisions/github-actions-artifacts.md). These
observations do not broaden shoutx's existing compatibility profile.

[source]: https://github.com/send/shoutx/blob/b9b0f6ab040f386e652aa2c7a16c5e374fe541e1/.github/workflows/artifacts-availability-probe.yml
[attempt1]: https://github.com/send/shoutx/actions/runs/36331651232/attempts/1
[attempt2]: https://github.com/send/shoutx/actions/runs/36331651232/attempts/2
[linux]: https://github.com/send/shoutx/actions/runs/36331651232/job/115417623392
[mac]: https://github.com/send/shoutx/actions/runs/36331651232/job/115417623399
[windows]: https://github.com/send/shoutx/actions/runs/36331651232/job/115417623103
