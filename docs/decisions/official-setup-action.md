# Official setup action

Status: Accepted

## Context

`shoutx` publishes native executables through GitHub Releases, but consumer
workflows currently have to select an archive, download it, verify it, extract
it, and add it to `PATH`. Repeating that logic is a usability problem and a
supply-chain risk.

The CLI repository already owns the native artifact format, supported targets,
checksums, attestations, and publication transaction in
[`release.md`](../release.md). An installer must consume that contract without
becoming another authority for it. The installer is also executable code on the
runner, so its own download, extraction, logging, and release paths form a new
security boundary.

## Decision drivers

- Give users one shell-independent installation step.
- Preserve exact, reproducible CLI version selection.
- Fail closed on an unsupported runner or changed artifact contract.
- Do not weaken the digest-pinned bootstrap already used by this repository.
- Keep JavaScript dependencies and generated bundles out of the Rust CLI
  repository.
- Preserve one authoritative owner for each cross-repository fact.

## Considered options

### Keep installation snippets in each workflow

Rejected. The archive and verification logic would remain duplicated and
shell-specific.

### Put a composite action in this repository

Rejected. Download, digest, archive, and path behavior would vary with shell
utilities, and the action lifecycle would be coupled to every CLI release.

### Put a JavaScript action in this repository

Rejected. Bundled JavaScript and its dependency lifecycle would enlarge every
CLI source change and release checkout.

### Create a separate JavaScript action

Accepted. The action is published in
[`send/setup-shoutx`](https://github.com/send/setup-shoutx). The separate repository owns
the action interface, implementation, and release lifecycle, while this
repository continues to own the CLI release artifacts it consumes.

## Decision

Create an official JavaScript action in a separate repository. Use the Node 24
action runtime supplied by a compatible GitHub Actions runner. Do not invoke
the caller's default shell or system `tar`, `unzip`, or PowerShell.

The action repository defines its public
[`action.yml`](https://github.com/send/setup-shoutx/blob/eb61a2361c6c0e0d37ab9cca1c50e998b4a94c24/action.yml).
See the [installation example](../../README.md#installation) for concrete pins;
the interface shape is:

```yaml
- uses: send/setup-shoutx@ACTION_REF
  with:
    shoutx-version: '0.3.0'
    checksums-sha256: EXPECTED_SHA256SUMS_SHA256
    github-token: ${{ github.token }}
```

This record owns the cross-repository security constraints below. The action
repository's `action.yml`, README, security documentation, and tests own its exact
input names, outputs, diagnostics, limits, and exit behavior. If they diverge,
the action repository must still satisfy this record or this record must be
superseded first. It may implement a compatibility mapping for the subset it
installs, but that mapping does not redefine what CLI releases publish.

### Version and artifact selection

- Require one exact CLI version. Accept a canonical Cargo SemVer without a
  leading `v`, surrounding whitespace, or build metadata. Accept a prerelease
  only when written in full. Reject `latest`, wildcards, ranges, partial
  versions, branches, and arbitrary tags. Bound the input before parsing.
- Initially support the release range assigned to setup-action artifact
  contract revision 1 in [`release.md`](../release.md). Older releases remain
  manually installable but are not covered because they predate compile-time
  stable-surface isolation and immutable-release enforcement.
- Fix the source repository as `send/shoutx` with GitHub repository ID
  `1381947214`. Require both identities to match before release lookup. Do not
  expose a repository, download authority, mirror, archive name, executable
  name, or manifest override.
- Map the actual Node process OS and architecture to a target in revision 1 and
  cross-check them against `RUNNER_OS` and `RUNNER_ARCH`. Reject disagreement,
  an unknown value, or an unsupported combination before network access. This
  detects inconsistent process and runner metadata; it does not detect
  transparent host emulation.
- Future compatible CLI releases require no action release. An incompatible
  artifact-contract revision requires a coordinated action release before the
  CLI release. Every revision change must alter an installer-consumed field so
  an older action fails closed on the expected asset, manifest, layout, or
  version check; there is no separate revision marker in the archive.

The first version supports ordinary GitHub-hosted jobs on the native runner
matrix declared by the CLI release. Container jobs, GitHub Enterprise Server,
Actions Runner Controller, and self-hosted environments are not guaranteed
until their runtime, network, filesystem, and platform-detection behavior has
separate evidence.

### Download and integrity

1. Query the public GitHub release API for the exact derived tag. Require the
   repository ID and full name to match, the returned tag to match, the release
   to be published and immutable, and the selected archive plus `SHA256SUMS`
   to be unique uploaded assets with SHA-256 digests.
2. Construct the exact archive name and GitHub Release URLs from the validated
   version, revision-1 mapping, fixed repository identity, and returned assets.
3. Download the archive and `SHA256SUMS` over HTTPS into a directory created
   atomically with restrictive permissions below the validated runner temporary
   directory. Bound response size, redirects, retries, and elapsed time.
4. Start only from the fixed GitHub API and deterministically derived Release
   URLs, require API-returned browser download URLs to equal those derived
   URLs, require HTTPS on each redirect, and do not depend on a fixed final CDN
   hostname.
5. Hash `SHA256SUMS` and compare it with the release API's asset digest. If the
   caller supplies an expected `SHA256SUMS` SHA-256, also require that
   workflow-local constraint to match. The expected digest can only narrow
   acceptance; it cannot select another release or bypass API, manifest, or
   archive verification.
6. Strictly parse every non-empty manifest line using the revision-1 grammar.
   Require safe relative filenames and unique entries, tolerate unrelated
   well-formed release assets, and require exactly one entry for the selected
   archive.
7. Hash the archive and require both the manifest entry and the release API's
   asset digest to match.
8. Inspect and extract according to the logical-member contract in
   [`release.md`](../release.md), rejecting metadata forms excluded by that
   revision before resolving the permitted logical members. Reject the complete
   archive before making an executable available. Extract only the executable
   and impose fixed executable permissions rather than trusting archive mode
   bits.
9. Run the extracted executable by absolute path with closed stdin, captured
   stdout and stderr, a timeout, an output bound, and a minimal fixed
   environment that retains only OS-required runtime variables. Require the
   exact stable `--version` bytes for the selected version. This is a
   consistency check, not proof that the executable is trustworthy.
10. Validate the generated absolute installation directory with constraints at
   least as strict as the CLI's
   [`github-actions:path`](../commands/github-actions-path.md) contract. Add
   only the executable's directory to `GITHUB_PATH`, and only after every check
   succeeds.

The manifest detects corruption and mismatched assets, but it is not an
independent signature because it comes from the same release. For future
immutable releases, GitHub locks the tag and assets at publication. For the
stronger workflow-local guarantee used by shoutx's own bootstrap, the expected
manifest digest remains necessary. Artifact attestations remain an independently
verifiable provenance mechanism; the first action must not claim to verify
them unless token, identity, offline, and failure behavior is designed and
tested.

The action may accept a GitHub token for release metadata availability. Send
it only to the fixed `https://api.github.com` origin, never to a redirect or
asset download, and never print or persist it. The token needs only public
metadata access; no token is required for integrity. Without a token, API
availability is best-effort and can fail closed under GitHub's unauthenticated
rate limit. The action must not silently install without the immutable and
asset-digest checks.

### Action output boundary

A JavaScript action's stdout and stderr are both connected to the GitHub runner
workflow-command parser. Action-controlled writes must never forward downloaded
bytes, HTTP response bodies, child output, archive contents, user inputs,
environment values, temporary paths, or exception objects to either stream. A
minimal launcher installs warning, exception, and rejection handlers before it
loads the rest of the bundle; recoverable failures set a failing exit status
and emit only a fixed ASCII failure line.

Require `GITHUB_PATH`, and `GITHUB_OUTPUT` if the action declares outputs, to
name validated absolute environment files before writing. Do not use toolkit
fallbacks that emit legacy stdout commands when a required variable is absent.
All informational and failure text is fixed ASCII; rejected values are never
interpolated. Tests must include hostile protocol-like content in every
rejected external field on both streams.

A bundle parse failure, fatal Node abort, or runner-generated diagnostic can
write outside those handlers. The action does not claim to sanitize output it
cannot execute early enough to control. Release tests exercise launcher load
failure where feasible, suppress ordinary Node warning rendering, and show
that all action-generated failure paths remain fixed and single-line.

### Trust assumptions

The action trusts the runner process, its Node runtime, operating-system APIs,
temporary-directory root, TLS implementation and trust store, GitHub Release
service, and the selected `send/shoutx` publication authority.
A caller-provided expected digest remains trusted workflow
configuration and limits what those download paths can substitute.

The first version does not honor proxy environment variables and rejects known
Node options that disable or replace TLS verification. Supporting an explicit
proxy requires a later design for credentials, trust roots, redirect handling,
and diagnostic secrecy.

Run setup before untrusted steps. A prior process with the same runner identity
can alter environment, trust settings, temporary files, or the job itself;
defending a compromised runner or malicious preceding step is out of scope.
The installed binary remains writable by later steps running as the same OS
identity; setup does not protect it after handoff.
The released action must not offer an environment-controlled production URL
override. A test-only HTTP seam must be dependency-injected, unreachable from
action inputs and process environment, and absent or fixed to production in
the reviewed bundle.

### Temporary storage and caching

Do not use `actions/cache`, the runner tool cache, or another persistent cache
in the first stable version. A writable cache surviving jobs or repositories
adds a poisoning boundary. Keep the verified installation in a fresh
runner-temporary directory for the job; repeated action invocations may
download again. Add caching only after a separate design binds every reused
byte to an exact digest and demonstrates a measured benefit.

### Action and CLI release policy

- Build, test, and bundle JavaScript in the action repository. Release tags
  contain the reviewed bundle and lockfile; workflows do not install npm
  dependencies at runtime.
- Enable GitHub immutable releases before publishing the action. Publish full
  SemVer releases. A moving major tag may exist separately for convenience,
  but recommend a full commit SHA for security-sensitive workflows and a full
  SemVer release tag for users who prefer immutable names. Never recommend the
  default branch.
- Keep action and CLI versions independent. Ordinary compatible CLI releases
  do not move an existing action tag. Incompatible artifact-contract changes
  require a new action version rather than silently widening an old one.
- Pin every third-party action used by the action repository to a full commit
  SHA. Isolate release permissions to the release job and keep them minimal.
- Do not maintain a remote revocation or floating denylist. A removed asset
  fails download; an explicitly selected vulnerable immutable release remains
  selectable until the workflow changes its exact version or digest. Publish
  security advisories and fixed releases through the normal channels.

After the action has an immutable release, this repository should dogfood a
full action commit SHA, an exact CLI version, and the expected `SHA256SUMS`
digest.
Retain at least one bootstrap path that builds or tests the checked-out CLI
without the setup action so an installer failure cannot prevent repair.

The initial adoption uses the action only in the release workflow's metadata
job. Its pins are maintained in that workflow. The normal CI change detector
retains the existing digest-pinned shell bootstrap, and the release-gates job
builds and tests the checked-out CLI without depending on the metadata job or
the setup action. Do not replace these independent repair paths as part of
routine action-version updates.

## Verification requirements

Derive the action's native matrix from CLI artifact contract revision 1 and
cover every supported OS and architecture. Before the first release, verify:

- exact version parsing, length bounds, and rejection of floating forms;
- platform cross-checks and fail-closed unsupported combinations;
- fixed-authority URL and archive-name derivation;
- bounded redirects, retries, rate-limit failures, timeouts, truncation, and
  response sizes;
- authenticated fixed-origin API requests and tokenless rate-limit failure,
  with no token on redirects or asset downloads;
- immutable release metadata, API asset digests, strict manifest parsing, and
  optional expected-manifest-digest matching;
- adversarial archives, including traversal, absolute paths, links, devices,
  duplicate and case-colliding paths, pax and GNU path overrides, global pax
  headers, ZIP local/central-name disagreement, ZIP64, encryption, Unix-mode
  symlinks, unexpected members, trailing data, and expansion limits;
- corrupt, truncated, wrong-platform, and wrong-version executables;
- closed stdin, process timeout, captured bounded output, and fixed diagnostics;
- exact version, output-file, PATH, and subsequent-step behavior on native
  GitHub-hosted runners; and
- absence of a production URL override and untrusted workflow-command output.

Release gates rebuild the bundled JavaScript from the tagged lockfile and
require a byte-for-byte match with the committed bundle. Security tests must
exercise the same production client and archive modules shipped in that bundle;
only the transport dependency is replaced by the unreachable test seam.
Process-level tests of the shipped entry point cover its handlers and
environment-file failures without replacing the fixed production endpoints;
the real-release tests cover its successful network path. These layers do not
simulate hostile transport through the literal shipped entry-point bytes.

At least one end-to-end test must install an actual supported `send/shoutx`
release on each native runner. Synthetic fixtures must be independently
constructed rather than generated solely by the parser or extractor under
test. Dependency review, static analysis, bundled-JavaScript review, and an
independent review of the threat model, extraction, redirect handling, and
release workflow are release gates.

## Consequences

- Users get a short, shell-independent installation step with exact CLI
  selection and an optional platform-independent manifest digest pin.
- JavaScript dependencies and bundles stay outside the Rust CLI repository.
- Initial runs always download, even if an earlier job installed that version.
- Existing v0.1.0 and v0.2.0 releases are outside the supported action contract.
- The separate repository becomes another security and maintenance surface.

## Reconsideration conditions

Revisit this decision if download cost becomes material, GitHub provides a
native verified-tool installer, portable attestation verification becomes
practical, or supported enterprise or self-hosted deployments require another
source. Add caching only with a digest-bound design. Broaden version syntax
only for a concrete use case that preserves reproducible selection.

## Evidence

- GitHub supports `runs.using: node24` in action metadata.
- GitHub's release API exposes the immutable state and asset SHA-256 digests;
  the asset endpoint documents that a request may return content or a redirect.
- GitHub immutable releases lock the associated tag and assets, apply only to
  releases published after the setting is enabled, and fit the existing
  draft-upload-publish workflow.
- The v0.2.0 native archives contain the three documented logical files, while
  their tar and ZIP directory-entry and metadata representations differ. The
  installer contract therefore uses logical members rather than byte-level
  archive headers.
- The current repository bootstrap pins both an exact release and archive
  digest; dogfooding through the action must preserve an equivalent additional
  constraint by pinning the manifest digest.

External observations were checked on 2026-09-30. The normative CLI artifact
contract remains [`release.md`](../release.md); evolving observations belong in
the future action repository.

## References

- [GitHub action metadata syntax](https://docs.github.com/en/actions/reference/workflows-and-actions/metadata-syntax)
- [GitHub workflow commands: adding a system path](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-commands#adding-a-system-path)
- [GitHub release asset REST API](https://docs.github.com/en/rest/releases/assets)
- [GitHub immutable releases](https://docs.github.com/en/code-security/concepts/supply-chain-security/immutable-releases)
- [Enabling immutable releases](https://docs.github.com/en/code-security/how-tos/secure-your-supply-chain/establish-provenance-and-integrity/prevent-release-changes)
- [GitHub action release management](https://docs.github.com/en/actions/how-tos/create-and-publish-actions/manage-custom-actions)
- [GitHub Actions security guidance](https://docs.github.com/en/code-security/tutorials/secure-your-organization/protect-against-threats)
