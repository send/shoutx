# Documentation map

Each kind of project information has one authoritative home. Other documents
link to that source instead of copying its requirements. If a change would
make two files independently normative for the same fact, move the fact to the
appropriate owner and replace the duplicate with a link.

| Information | Authoritative source |
| --- | --- |
| Product boundary, applicability profile, and accepted cross-cutting invariants | [`design.md`](design.md) |
| Adversary, trust assumptions, assets, and attack inventory | [`threat-model.md`](threat-model.md) |
| Observable CLI behavior for one destination | [`commands/`](commands/) |
| Rationale, alternatives, and reconsideration conditions | [`decisions/`](decisions/) |
| Versioned observations about external parsers and runtimes, including minimal retained evidence projections | [`compatibility/`](compatibility/) and its [`evidence/`](compatibility/evidence/) subdirectory |
| Shared verification policy | [`test-plan.md`](test-plan.md) |
| Release eligibility, compatibility maintenance/incident response, and publication policy | [`release.md`](release.md) |
| Artifact contract consumed by integrations | [`release.md`](release.md) |
| Intended implementation architecture and finite next-increment handoff | [`implementation-plan.md`](implementation-plan.md) |
| Completed implementation sequence | [`implementation-history.md`](implementation-history.md) |
| User-facing overview and examples | [`../README.md`](../README.md) |

The repository README is not a second command specification. It summarizes
available behavior and links to the normative command and release documents.
Compatibility notes record evidence, not product guarantees. Decision records
explain why a contract was chosen, but the resulting observable behavior lives
only in the command specification.

Cross-repository integrations record their adoption rationale and security
constraints in [`decisions/`](decisions/). Once an integration repository
exists, its observable interface and implementation-specific behavior are
owned there; this repository continues to own only the `shoutx` artifact and
CLI contracts that integration consumes.

When a decision changes, add or update the relevant decision record first,
then change the authoritative contract. Historical rationale should not be
copied into `design.md`, the threat model, or each affected command.
