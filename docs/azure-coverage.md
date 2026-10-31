# Azure Pipelines practical coverage

Status: proposed coverage assessment, 2026-10-25. This is the authoritative
Azure coverage proposal delegated by the design index, not a command contract
or implementation authorization. Release preparation remains on hold.

The existing writers cover basic non-secret variable exchange, diagnostics,
PATH setup, scoped mask registration, dynamic secret-variable assignment and
build metadata. They are useful, but do not yet cover all valuable
script-to-Agent output boundaries. Completing
these implementations is not evidence of practical surface completeness.

## How to read the assessment

- **Covered** means an existing writer and its linked contract/evidence cover
  the named use, not every Azure option or deployment.
- **Add value** means there is a plausible ordinary script use with external
  data crossing a named protocol boundary. It is a candidate, not a shipped CLI
  or a guarantee that lossless representation has already been established.
- **Outside** means an explicit product/profile disposition, not a declaration
  that the operation is safe or has no injection risk.
- **Pending** is used when a missing fact prevents a coverage disposition.
  Acceptance details deferred to a candidate's contract do not by themselves
  prevent recognizing that a useful boundary exists.

The attacker controls data such as tool results, generated names, diagnostic
text or manifest paths, not the workflow's intended operation. For `##vso`
requests, naive interpolation can cross a physical-line boundary or a property
delimiter and change operations or fields. A typed writer can constrain those
boundaries; it cannot authorize the selected resource or make subsequent use
safe. Literal escape fidelity and downstream field restrictions also matter.
These are threat scenarios for raw composition, not newly discovered exploits
in the current accepted shoutx output.

Formatter requests use `##[...]`, a distinct surface. Their candidate designs
must establish which bytes the actual consumer treats as structure and which
as text, including interaction with other command processing on the same stream;
checking line boundaries alone is insufficient. Do not assume that `##vso`
percent decoding or GitHub encoding applies.
No formatter implementation or safe arbitrary-stream wrapper is proposed here.

## Existing scope and evidence

The [Azure profile](design.md#azure-pipelines-profile) owns implementation and
release status as well as OS, shell and Agent conditions.
The [compatibility record](compatibility/azure-pipelines.md) owns
the pinned parser and finite hosted observations; those results must not be
extended to candidate handlers merely because they share a parser.
The [command guide](command-protection.md#azure-pipelines) explains current use.

## Task command coverage

The first column follows the official logging-command surface [1]. Alternatives
are ways to accomplish the use case, not certifications of their security or
claims of identical effects. Caller duties apply equally to those alternatives.

| Surface and disposition | Use and typical input | Boundary, responsibility and reason / alternative |
| --- | --- | --- |
| `task.setvariable`, non-secret — **Covered** | Pass tool results to later tasks; output/read-only flags | Name/property/line injection is handled by the [variable contract](commands/azure-pipelines.md). Callers authorize names, mappings and subsequent use; Azure owns scope, collisions and restrictions. YAML variables suffice for values known before execution. |
| `task.setvariable`, `isSecret=true` — **Covered**, unreleased | Pass a runtime-issued token or derived credential to a later task | The dedicated [secret-variable contract](commands/azure-pipelines-secret-variable.md) owns exact assignment, prior-mask ordering, rejection policy and scoped confidentiality. Caller owns acquisition, names, mappings, permitted consumers and lifetime; Azure owns secret storage/mapping. Prefer UI, variable groups or Key Vault for provisioned secrets [2]. See the [hosted admission](compatibility/azure-pipelines.md#secret-variable-hosted-admission); mask registration alone does not assign a variable. |
| `task.logissue`, warning/error — **Covered** | Report tool diagnostics with file, position and code | The [issue contract](commands/azure-pipelines.md) protects command and property identity. Callers authorize severity/content and propagate failure; Azure owns retention/rendering. Existing issue writers are the supported alternative to raw concatenation. |
| `task.prependpath` — **Covered** | Expose a trusted tool installation directory to later tasks | The [PATH contract](commands/azure-pipelines.md#path) prevents extra commands and additional incoming PATH entries. Caller authorizes directory/executable trust; Azure owns ordering and equivalence. Fixed task/tool-install configuration can avoid dynamic PATH writes. |
| `task.setsecret` — **Covered** | Register a securely acquired value or selected lines for later logs | The [mask contract](commands/azure-pipelines-mask.md) and profile cover exact registration and scoped later redaction. Callers own timing, representations and overmasking; not secret-variable assignment or retrospective cleanup. Existing secret configuration is an alternative for provisioned values. |
| `task.setprogress` — **Add value**, lower priority | Long-running tools report a percentage and operation text derived from work items | A typed numeric percentage and encoded text can prevent text from adding commands/properties. Caller owns truthful progress; Agent/UI owns display. Fixed progress text or ordinary diagnostics may suffice, but are not equivalent progress UI. A finite writer is separable from timeline management. |
| `task.complete` — **Outside** for fixed result control; **Add value**, lower priority for external operation text | Finish a task with a trusted result and possibly tool-derived operation text | A fixed trusted status has no data field to protect. A text-bearing variant would need a typed result plus text framing; text must not select status or another command. Caller owns failure policy and shell exit propagation. Exit codes plus pipeline continue-on-error policy cover ordinary failure and some partial-success uses [1], not every explicit timeline effect. No lifecycle orchestration is proposed. |
| `task.logdetail` — **Outside** current ordinary-script coverage | Custom task authors maintain timeline IDs, parent relationships and progress | Names/text could cross command/property boundaries. Caller owns GUID relationships and truthful state; Azure owns timeline presentation. No ordinary-script requirement for custom nested timeline records is identified here, unlike common log grouping; this is the exclusion reason, not the mere existence of caller duties. Prefer task-author APIs and reconsider with a concrete reusable script use case. |
| `task.setendpoint` — **Outside** current scope | Custom tasks change an authorized service connection URL/auth/data field | A writer could frame fields, but cannot authorize destination changes or credential recipients. This is job-scoped service-connection mutation, not ordinary value export. Use configured service connections or a purpose-built trusted task. Reconsider only with an explicit endpoint-mutation use case and credential boundary; high privilege alone is not proof that framing has no value. |
| `task.uploadsummary` — **Add value** | A report generator supplies a Markdown file path | Protect the selected upload command and path, not Markdown content or authorization to read/publish that file. Caller owns path identity, races and sensitive content; Azure owns upload/rendering. A normal artifact can distribute a report but is not an equivalent summary UI. Unlike GitHub summary-file content, Azure's path is itself a logging-command data boundary. |
| `task.uploadfile` — **Add value** | Attach a caller-approved diagnostic file to task logs | Protect path/command structure; caller authorizes disclosure and file identity, Azure performs upload. Artifact publishing is an alternative distribution channel, not the same task-log attachment. No file-reading/upload engine belongs in shoutx. |
| `task.addattachment` — **Add value**, lower priority | An extension chooses an attachment type/name and generated file | Names, type and path can inject properties/commands if concatenated. Typed framing can protect selected fields; caller authorizes extension/type, file and publication, Azure owns attachment access. Prefer the summary shorthand for summaries; extension-specific tasks are an alternative for other types. |

## Formatter coverage

These seven formats are listed separately from task commands in [1]. None is
claimed covered merely because the current warning/error writers create issues.

| Surface and disposition | Use and typical input | Boundary, responsibility and reason / alternative |
| --- | --- | --- |
| `group` — **Add value** | Group a build phase with a tool-derived title | A raw title newline can introduce a new control line; the formatter boundary note above requires checking other command interpretation too. A candidate must keep the title in its chosen formatter operation. Caller owns group lifetime and body output; log grouping does not neutralize body commands. A static title is a simpler alternative when no dynamic data is needed. |
| `endgroup` — **Add value** only as group's fixed companion | Close the caller's group | No untrusted value; fixed terminator completes the typed interface, not an independent injection-prevention feature. Caller balances groups. A trusted literal is an alternative. |
| `debug` — **Add value** | Display tool-derived diagnostic text | Constrain physical control-line injection and verify actual formatter behavior without importing task-command escapes. Caller authorizes disclosure, Azure owns debug visibility. Ordinary logs are not a safe fallback for untrusted command-looking text. |
| `section` — **Add value**, lower priority | Display a dynamic phase/section label | Same formatter boundary questions as group, including the cross-protocol check above, without claiming lifetime management. Caller owns truthful labels; UI owns presentation. Fixed section labels or group titles may suffice. |
| `warning` / `error` — **Outside** as separate initial formatter writers | Mark ordinary log lines without selecting timeline issue semantics | Dynamic text has a framing risk, but existing typed `task.logissue` writers cover diagnostic reporting. They are a use-case alternative, not a wire/UI-equivalent implementation. Reconsider if log-only warnings/errors without issue creation are required. |
| `command` — **Outside** initial coverage | Display the command line being run | External command text could add formatter/control lines. No need for this distinct command-line display is identified beyond ordinary diagnostics/activity labels; that is the exclusion reason, not disclosure risk alone. Formatting neither executes safely nor authorizes execution, and printing arguments can disclose secrets. Use a fixed non-secret activity label or a trusted task's logging policy; reconsider for a concrete command-display requirement. |

## Artifact, build and release coverage

| Surface and disposition | Use and typical input | Boundary, responsibility and reason / alternative |
| --- | --- | --- |
| `artifact.upload` — **Add value**, lower priority | Script selects an approved file, container folder and artifact name | Protect path and property fields against additional commands/changed destinations. Caller authorizes content, names and publication; Azure owns upload/storage. Prefer `PublishPipelineArtifact@1` for ordinary file/directory publishing on Services [3], or `PublishBuildArtifacts@1` where appropriate [4]. A wrapper may still help scripts requiring this specific logging-command channel; it is not a replacement artifact service. |
| `artifact.associate` — **Outside** current scope | Link existing container/share/version-control subjects with a typed location and name | Type/name/location can cross command/property boundaries; caller/provider retain resource trust and association semantics. Unlike publishing newly generated build outputs, no concrete need to associate these existing-resource types is identified here. Prefer supported artifact tasks for normal publishing; they do not replace every association type. Reconsider on an existing-artifact association requirement rather than adding a raw arbitrary-type builder. |
| `build.uploadlog` — **Add value**, lower priority | Attach a generated diagnostic log to the build | The path is a command-data boundary; protecting it does not redact the uploaded file or authorize disclosure. Caller owns file selection and races; Azure owns storage. Task-log attachments or a named artifact may meet the use case but use different destinations. |
| `build.updatebuildnumber` — **Covered** | Build/version tooling derives a run identifier | The [metadata contract](commands/azure-pipelines.md#build-metadata) protects the fixed operation and exact accepted number. Caller owns naming policy; Azure owns validation, update and display. YAML `name` handles preconfigured naming [5], not every runtime-derived version. |
| `build.addbuildtag` — **Covered** | A scanner or build tool supplies a classification/version label | The [metadata contract](commands/azure-pipelines.md#build-metadata) keeps one requested tag under the design-owned tag API setting. Caller authorizes labels and downstream selection; Azure owns tag semantics. An authenticated API is an alternative; API authentication is outside this CLI. |
| `release.updatereleasename` — **Outside** current profile | Rename a running Classic release from generated metadata | Text framing could help, but Classic release pipelines are outside the existing Azure profile. Caller owns naming and Azure owns lifecycle. Use configured release naming or a release-specific task/API. Reconsider only with explicit profile expansion; do not infer coverage from build-number support. |

## Priority and finite next tasks

These are proposed work packages, not commands added to the CLI or permission
to execute them. No currently unclassified item blocks this inventory; candidate
input/consumer contracts remain deliberately unimplemented.

1. **Build metadata writers selected and implemented.** The
   [decision](decisions/azure-build-metadata.md) records rationale, the
   [compatibility record](compatibility/azure-pipelines.md#build-metadata-hosted-admission)
   owns finite handler/service evidence, and the handoff owns PR progress.
2. **Dynamic secret-variable writer implemented, unreleased.** The dedicated
   [contract](commands/azure-pipelines-secret-variable.md) and
   [hosted admission](compatibility/azure-pipelines.md#secret-variable-hosted-admission)
   cover the accepted increment. PR #149 merged on 2026-10-28. This does not
   resume release preparation or extend the admitted confidentiality profile.
3. **Formatter contract for debug/group/endgroup.** Confirm the actual formatter
   boundary and whether lossless data representation exists. Completion: an
   approved representation or explicit rejection policy, consumer/display scope
   and finite tests for unintended command interpretation (not only additional
   physical lines), title/data fidelity and group
   effects. No arbitrary subprocess-log sanitizer, automatic group lifecycle or
   default decoration. Compare the SDK-used debug alternative noted below
   before selecting a wire. If safe encoding is unavailable, present rejection or
   explicit sanitization tradeoffs for approval, not a hidden transformation.
4. **File-path command contract, starting with summary/uploadfile.** Completion:
   approved path/metadata framing, clear separation from content and resource
   authorization, failure behavior and finite intended-attachment checks using
   synthetic authorized files. Do not read, hash, redact or upload files in the
   producer, expand into Markdown sanitization, or presume log masks protect
   uploaded bytes. Evaluate the lower-priority attachment/artifact/log variants
   against the task alternatives before choosing a subsequent increment.

Progress, completion text and section formatting remain useful lower-priority
candidates, not prerequisites merely to increase command count. Reconsider them
when a concrete workflow needs their distinct effect. An initial release of the
current subset can be described honestly as scoped support, but calling Azure
coverage practically complete requires a maintainer decision on the valuable
remaining use cases above; this document neither resumes nor authorizes release.

## Evidence and maintenance

The inventory owns proposed coverage rationale and relative priorities. The
handoff records the maintainer-selected task; accepted contract decisions and
their rationale still belong in the existing specifications and decision records.

A source check found `task.debug` registered by the pinned Agent and used by
Microsoft's task-lib. It is not in the official task-command list above and is
not a supported shoutx operation. The [formatter proposal](decisions/azure-formatter.md)
compares this route; the [source observations](compatibility/azure-pipelines.md#formatter-design-observations)
record its evidence and remaining admission limits. SDK use is not proof of
safe formatting or permission to expose arbitrary internal Agent commands.

The official inventory was checked on 2026-10-25: 11 task command names,
7 formatter names, 2 artifact commands, 3 build commands and 1 release command.
`setvariable` is split by secrecy semantics and `complete` by fixed versus
text-bearing use; formatter warning/error share one row. This inventory covers
the documented logging-command page, not every Azure REST API or internal Agent
extension. Product classifications and ordering above are maintainer-facing
judgments derived from the named boundaries, not recommendations attributed to
Microsoft. No source-level vulnerability discovery or new hosted experiment is
required to classify these use cases.

Reuse existing [parser and hosted evidence](compatibility/azure-pipelines.md)
when designing an increment, adding only the selected handler/effect checks.
Record new observations there rather than duplicating the current input rules.
New non-sensitive use cases can motivate a coverage change. Concrete unpublished
attack details follow [SECURITY.md](../SECURITY.md), not public inventory rows.

## Sources

1. [Microsoft logging-command inventory and syntax](https://learn.microsoft.com/en-us/azure/devops/pipelines/scripts/logging-commands?view=azure-devops).
2. [Microsoft secret-variable guidance and managed alternatives](https://learn.microsoft.com/en-us/azure/devops/pipelines/process/set-secret-variables?view=azure-devops).
3. [Publish Pipeline Artifacts task](https://learn.microsoft.com/en-us/azure/devops/pipelines/tasks/reference/publish-pipeline-artifact-v1?view=azure-pipelines).
4. [Publish Build Artifacts task](https://learn.microsoft.com/en-us/azure/devops/pipelines/tasks/reference/publish-build-artifacts-v1?view=azure-pipelines).
5. [Run and build number configuration](https://learn.microsoft.com/en-us/azure/devops/pipelines/process/run-number?view=azure-devops).
