# Release design

This document defines the intended first-release packaging and publication
contract for `shoutx`. It does not authorize a release, reserve a registry
name, or describe behavior of the writers themselves. The release workflow is
a separate implementation increment and must be reviewed before the first tag
is created.

## Initial distribution scope

GitHub Releases is the initial binary distribution channel. A release contains
native executables for these Rust targets:

| Platform | Rust target | Build runner |
| --- | --- | --- |
| Linux x86-64 | `x86_64-unknown-linux-musl` | Linux x86-64 |
| Linux ARM64 | `aarch64-unknown-linux-musl` | Linux ARM64 |
| macOS x86-64 | `x86_64-apple-darwin` | macOS x86-64 |
| macOS ARM64 | `aarch64-apple-darwin` | macOS ARM64 |
| Windows x86-64 | `x86_64-pc-windows-msvc` | Windows x86-64 |

Each executable is built and smoke-tested on a native GitHub-hosted runner.
Linux uses the musl targets so the released executable does not acquire a
glibc-version dependency from the current runner image. This is a packaging
choice, not a promise that every Linux kernel, C library, or container image is
supported.

Windows ARM64 is deferred while its standard GitHub-hosted runner is in public
preview. Other architectures and package-manager channels are added only with
native test coverage and an explicit support decision.

Publishing the source package to crates.io is also deferred. Registry
publication is permanent for a version, involves separate ownership and
credential policy, and must not be an incidental side effect of publishing
GitHub release binaries. Users may still build from the repository with Cargo.

## Version and tag contract

Release versions follow SemVer as represented by Cargo, except that the initial
release process prohibits build metadata. A release tag is `vVERSION`, where
`VERSION` is exactly the `[package].version` from `Cargo.toml`; for example,
package version `0.1.0` uses tag `v0.1.0`.

The release workflow validates all of the following before any public release
is created:

- the ref is a tag with the exact `vMAJOR.MINOR.PATCH` form, including an
  optional Cargo-compatible prerelease suffix;
- neither the tag nor the Cargo version contains a `+BUILD` metadata component;
- removing the leading `v` produces exactly the Cargo package version;
- `Cargo.lock` is current and all builds use `--locked`;
- the complete CI and dependency-policy gates pass for the tagged commit; and
- the tag does not already have a published GitHub release.

A version with a prerelease component, such as `0.1.0-rc.1`, is published as a
GitHub prerelease and is excluded from GitHub's latest-release selection. A
version without that component is published as a normal release. The workflow
derives this state from the already validated Cargo version rather than from a
separate manual input.

Builds use the exact Rust toolchain selected in `rust-toolchain.toml`. The
workflow records the tag, commit, Rust version, target, and runner image in its
job output. Updating the development toolchain is a reviewed repository change;
a floating `stable` toolchain is not used for release artifacts.

## Artifact contract

Archive names are deterministic:

```text
shoutx-vVERSION-TARGET.tar.gz
shoutx-vVERSION-TARGET.zip
```

The four POSIX targets use `tar.gz`; Windows uses `zip`. Each archive has one
top-level directory named `shoutx-vVERSION-TARGET` containing only:

```text
shoutx                 # shoutx.exe on Windows
README.md
LICENSE
```

Executable names, archive paths, and archive member names are constructed from
workflow constants and the validated version, never from untrusted event text.
POSIX archives give the executable mode `0755`; documentation files use
`0644`. Archive creation must not depend on the host locale or local timezone.

The release also contains `SHA256SUMS`, with one line for each archive in
lexicographic filename order. It uses the conventional lowercase hexadecimal
digest, two ASCII spaces, filename, and LF format:

```text
HEX_DIGEST  shoutx-vVERSION-TARGET.EXT
```

`SHA256SUMS` does not include itself. Checksums are computed only after all
archives have been collected by the publication job; no build job contributes
an independently assembled partial manifest.

## Provenance

The publication job generates GitHub artifact attestations for every release
archive and for `SHA256SUMS`. Attestations bind the downloadable bytes to the
repository, workflow, commit, and triggering ref. Documentation includes both
checksum verification and `gh attestation verify` examples.

Attestation is a provenance statement, not a claim that an artifact is safe.
Checksums detect accidental or malicious byte changes only when the manifest
itself is obtained from the expected release. Consumers wanting an identity
and build-source check should verify the GitHub attestation as well.

Only the publication job receives `contents: write`, `id-token: write`, and
`attestations: write`. Matrix build jobs receive `contents: read`, do not have
release credentials, and upload their candidate archives as workflow
artifacts. Third-party actions remain pinned to full commit digests.

## Publication transaction

The workflow performs the release in these phases:

1. validate the tag, Cargo version, lockfile, and tagged commit;
2. build and test each target without publication permissions;
3. collect all expected archives and reject missing, extra, or duplicate
   filenames;
4. create and independently verify `SHA256SUMS`;
5. generate attestations for the exact files that will be uploaded;
6. create a draft GitHub release and upload the complete asset set; and
7. publish the draft only after every upload succeeds.

A failure before the final step leaves no public release. A failed draft is
retained for diagnosis or manually deleted. An automatic retry must use the
same draft rather than create a second release, remove every existing asset
from that draft, and upload the newly collected complete asset set. It must
then verify that the draft contains exactly the expected filenames and digests
before publication. This prevents an archive from an earlier, potentially
byte-different build from being paired with a new checksum manifest. A failure
after GitHub accepts the final publish operation cannot be made transactional
and requires maintainer review. The workflow never modifies or silently
replaces assets on an already published release.

Release publication is serialized so two runs cannot publish the same tag
concurrently. The workflow has a finite timeout and retains intermediate
workflow artifacts only long enough to diagnose a failed release.

## Reproducibility and support boundary

The first release contract provides repeatable inputs: a tagged commit, locked
dependencies, an exact Rust toolchain, declared target triples, and recorded
GitHub runner images. It does **not** claim bit-for-bit reproducible archives.
Runner images, platform linkers, archive tools, and embedded build metadata can
otherwise change bytes between executions. A reproducibility claim requires a
separate measured design with controlled build environments and byte-for-byte
comparison.

The release artifacts guarantee only the CLI behavior and platform scope
documented by the README and design documents. Code signing with an Apple or
Microsoft identity, installer packages, automatic update behavior, long-term
support for a particular OS release, and package-manager availability are not
part of the initial contract.

## Follow-up implementation gates

The release-workflow PR must demonstrate, without publishing a real release:

- locally testable version and artifact-name validation;
- archive-content and permission checks for every target;
- execution of each packaged binary on its native build runner;
- checksum-manifest verification after workflow-artifact transfer;
- least-privilege job permissions and full action-SHA pinning;
- a safe dry run that exercises aggregation without creating a release; and
- documented checksum and attestation verification commands.

Creating the first tag and publishing the first release remain explicit
maintainer actions after that PR is merged.
