# GitHub Actions output-surface audit

This is the 2026-10-17 source snapshot used for v1 candidate preparation, not a
new consumer guarantee or release admission. The
[design inventory](../design.md#v1-readiness) owns the resulting dispositions.

## Sources and enumeration

- [Official workflow commands](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-commands),
  checked 2026-10-17, lists the toolkit mapping, environment files, stdout
  diagnostics/control and artifact declaration/list surfaces.
- [Toolkit commands](https://github.com/actions/toolkit/blob/7e25f67e8fd17369aa21e6e816ac99654106e0dc/docs/commands.md)
  at `7e25f67e8fd17369aa21e6e816ac99654106e0dc` also describes problem matchers.
  Its retained legacy output/state snippets do not require legacy writers when
  the equivalent current command-file destinations are supported.
- Runner baseline v2.337.0 is
  `397b032cbf865e9c3ddfab89d533ec19325e1273`. `ActionCommandManager` exposes
  add-mask, debug, notice/warning/error, group/endgroup, add/remove-matcher,
  echo, legacy set-env/set-output/save-state/add-path and the internal
  repository-path operation; stop/resume is managed by the command manager.
  `FileCommandManager` covers path, env, state, output and step_summary;
  the separate artifact handlers cover artifacts and artifacts_list.
  The action/file extension registrations in `src/Runner.Common/ExtensionManager.cs`
  match this enumeration.

Every enumerated operation maps to an existing inventory row. The review found
no additional public value-writing boundary missing from that inventory.
This is a bounded surface review, not an audit of arbitrary toolkit APIs or
Runner implementation security.

## Newer Runner: verification pending

The latest release API reported [v2.338.0](https://github.com/actions/runner/releases/tag/v2.338.0),
published 2026-10-06, resolving to
`197ca027b90de199464dee3bb9ff198a1db60967`. Direct Git blob comparisons against
v2.337.0 found these four files unchanged:

| `src/Runner.Worker/` file | Git blob SHA |
| --- | --- |
| `ActionCommandManager.cs` | `4b9995fc89dd2c2b5e4115afd646f920de0bef82` |
| `FileCommandManager.cs` | `9d8bbebb42b037781456ec467693e019138f1b95` |
| `CreateArtifactsFileCommand.cs` | `da0d694d64f690fed0d8da8987271dcd80d56b0d` |
| `ArtifactsListFileCommand.cs` | `aaad5695384397acb6810164246c193b355953d5` |

The registration table file `src/Runner.Common/ExtensionManager.cs` is also
unchanged (Git blob `b0bc2fef01e997fbe40eb3a3e44190ca71aa6b05`).

Those hashes establish only the enumerated handler and registration-source
identity. They do not
establish package/runtime identity, all helper behavior, live Worker deployment,
or successful effects on v2.338.0. Existing v2.337.0 observations remain what
they were; do not relabel them as v2.338.0 verification. Verification of the new
version is pending, with no new vulnerability inferred. The next release must
complete the reviewed pin/package/source verification and fresh admission in
the [release checklist](../release.md#next-release-preparation). This review does
not change pins or add a new supported OS generation.

## Installation observation

The existing README action pin
`eb61a2361c6c0e0d37ab9cca1c50e998b4a94c24` resolves to the published
[`send/setup-shoutx` v0.1.0](https://github.com/send/setup-shoutx/releases/tag/v0.1.0),
whose API object reported `immutable: true` on 2026-10-17. Its implementation
remains owned by that repository. This validates the existing installation
reference, not installation of a future unpublished CLI version.
