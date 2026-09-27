# GitHub Actions PATH writer

This specification covers `github-actions:path`. Cross-cutting product
invariants remain in [`design.md`](../design.md), and shared testing policy
remains in [`test-plan.md`](../test-plan.md). The Contract section is normative
for this command; contradictions with the cross-cutting documents must be
resolved.

## Contract

`github-actions:path [VALUE]` emits exactly one LF-terminated entry for
`$GITHUB_PATH`. It has no line-mode options. `--` ends option parsing and is
required for an argv value beginning with `-`.

[GitHub documents](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-commands#adding-a-system-path)
each line as a directory prepended to PATH for subsequent steps. The parser
details below are grounded in the pinned
[`AddPathFileCommand`](https://github.com/actions/runner/blob/397b032cbf865e9c3ddfab89d533ec19325e1273/src/Runner.Worker/FileCommandManager.cs#L127-L158),
not inferred from the named environment-file parser.

The command uses the shared strict UTF-8, NUL rejection, 1 MiB input limit,
input-source, diagnostic, exit-status, and pre-write validation rules. It
consumes at most one final CRLF, LF, or bare CR as CLI input framing, then
rejects an empty value or any remaining CR or LF. The emitted bytes are the
remaining value followed by LF; shoutx performs no path normalization.

The target path dialect follows an exact trusted `RUNNER_OS` value of `Linux`,
`macOS`, or `Windows`; if it is absent, the native process OS is used. An
unrecognized value is always rejected because path grammar and the effective
PATH separator are target-specific.

Only fully qualified paths are accepted. POSIX paths must begin with `/`.
Windows accepts these forms:

- an ASCII drive letter, `:`, and `/` or `\`, including a drive root;
- exactly two leading separators in any `/` and `\` combination followed by
  non-empty server and share components separated by either character, where
  neither component is `.` or `?`; or
- an exact `\\?\` prefix followed by either an ASCII drive letter, `:`, and
  `\`, or uppercase `UNC\` plus non-empty server and share components separated
  by `\`.

The verbatim prefixes and their structural separators are backslash-only;
forward slashes later in a verbatim path remain literal data. Drive-relative
forms such as `C:tools`, root-relative forms such as `\tools`, incomplete UNC
forms, mixed-separator spellings of `\\.\` or `\\?\`, Win32 device forms, and
verbatim namespaces other than drive and UNC are rejected. Thus paths under
`GLOBALROOT`, `Volume{...}`, and `pipe` are not accepted. The implementation
does not require the path to exist, resolve `.` or `..`, canonicalize symlinks,
change separator spelling, trim whitespace, or change case.

POSIX `:` and Windows `;` are rejected. Although either character can be path
data in some contexts, the runner later joins accepted lines with the target
OS PATH separator; accepting it would let one line become multiple effective
PATH entries. A double quote is rejected on every target because a container
step host interpolates the resulting PATH into a quoted `docker exec` argument
string; accepting it could terminate that argument and create another runtime
option. A POSIX path ending in `\` is also rejected: .NET re-tokenizes that
argument string, so trailing backslashes can escape the synthetic closing quote
or be collapsed, changing the directory identity. Other platform-specific
invalid filename characters are not validated because shoutx neither accesses
the directory nor claims that the OS will accept it.

A leading U+FEFF is rejected. When the entry is the first content in the
command file, `File.ReadAllLines(..., Encoding.UTF8)` consumes its UTF-8 bytes
as a byte-order mark; when earlier content exists, the same bytes are retained.
Rejecting the ambiguous value makes the result independent of append position.
U+FEFF elsewhere is preserved, and shoutx never emits an encoder-added BOM.

In the pinned v2.337.0 runner, `AddPathFileCommand` uses
`File.ReadAllLines(filePath, Encoding.UTF8)`. It ignores empty lines, processes
non-empty lines in file order, removes a matching earlier path using its
current-culture comparison, and adds the new path to an internal prepend list.
It reverses that list when constructing PATH, so a later distinct entry has
higher command-lookup priority. shoutx emits one entry and does not inspect the
destination file, deduplicate entries, or promise stable duplicate equivalence
across runner cultures.

Current-culture equality can treat distinct Unicode strings as duplicates,
including strings that differ by default-ignorable characters. Exact UTF-8
preservation therefore does not imply stable duplicate identity. On non-Linux
hosts, the runner's later PATH helper also uses an ordinal-ignore-case prefix
check and avoids prepending the complete string when PATH already starts with
that string followed by the PATH separator. These are runner behaviors, not
shoutx deduplication guarantees.

This is structural validation, not authorization. The caller must establish
that the directory and executables reachable through it are trusted.

### Implementation constraints

Keep path validation and its test-only runner model separate from named-record
parsing. The implementation must not infer PATH behavior from shared
environment-file parser assumptions.

## Boundary-specific threat analysis

### `github-actions:path`

The security property is limited to one `$GITHUB_PATH` record. As with other
non-multiline modes, the command consumes at most one final CRLF, LF, or bare CR
as input framing, then rejects NUL, every remaining CR or LF, and empty values
so one input cannot add multiple entries.

The runner's second interpretation step joins accepted lines using the target
OS PATH separator. shoutx therefore also rejects POSIX `:` or Windows `;`, so
one file record cannot become multiple effective PATH entries. It accepts only
fully qualified paths in the target runner dialect and rejects a leading
U+FEFF, whose preservation would otherwise depend on whether the record begins
the file. Target selection follows trusted `RUNNER_OS`, with native fallback;
an unknown value is rejected. It rejects `"` on every target because the
runner's container step host embeds PATH in a quoted `docker exec` argument
string. For the same boundary, a POSIX path ending in backslash is rejected
because .NET argument re-tokenization can consume backslashes or the closing
quote and change the resulting argument.

There is no encoding that makes an attacker-controlled directory safe to add to
`PATH`. An attacker who controls a directory earlier in command lookup may place
a malicious executable there. The caller must separately establish that the
path is trusted and intended. `github-actions:path` is framing and validation,
not authorization.

shoutx does not canonicalize, resolve dot segments or symlinks, change path
separators, trim whitespace, inspect the destination file, or require the
directory to exist. Those transformations could change identity or introduce
filesystem races and are outside record framing.

## Command-specific verification

### Path-record verification

Every successful `github-actions:path` invocation emits the validated path
followed by exactly one LF and no BOM. Test both argv and stdin and verify that
VALUE causes stdin to remain untouched. The command has no lossy or multiline
mode.

Target selection is exact and case-sensitive. Test `RUNNER_OS=Linux`,
`RUNNER_OS=macOS`, and `RUNNER_OS=Windows`, native fallback when the variable is
absent, and rejection of empty, differently cased, invalid-encoding, and other
unknown values. Unlike multiline named records, the target is always relevant.

#### POSIX target grammar

Accept `/`, `/a`, `/a b`, `/a/./b`, `/a/../b`, repeated separators, trailing
separators, non-ASCII UTF-8, and U+FEFF away from the first character. Preserve
every accepted byte exactly. Reject relative paths, `./a`, `../a`, an empty
value, a leading U+FEFF, any CR or LF left after common final-boundary
consumption, NUL, and any value containing `:`.
Reject `"` even though it can occur in a POSIX filename, because it crosses the
runner container step-host argument boundary. Reject a path ending in `\` and
include both odd and even runs of trailing backslashes; .NET argument
re-tokenization must not silently change directory identity.

#### Windows target grammar

Accept drive-absolute paths using either directory separator, UNC paths, and
fully qualified verbatim drive and UNC forms. Include spaces, dot segments,
repeated and trailing separators, non-ASCII UTF-8, and U+FEFF away from the
first character, and assert exact preservation. Cover `C:\`, `c:/tools`,
`\\server\share`, `//server/share`, `\\?\C:\`, and
`\\?\UNC\server\share`. Normal UNC separators may be mixed, so also accept
`/\server/share` and `\/server\share`.

Reject drive-relative `C:tools`, root-relative `\tools`, plain relative paths,
incomplete UNC forms, Win32 device forms such as `\\.\...`, an empty value, a
leading U+FEFF, any remaining CR or LF, NUL, and any value containing `;`.
Reject `"` and explicitly cover bare `C:`, `\\server`, `//./x`, `/\.\x`,
`//?/C:/x`, `\\?\C:/x`, `\\?\C:`, `\\?\UNC\server`,
`\\?\GLOBALROOT\x`, `\\?\Volume{x}\`, `\\?\pipe\x`, and
`\\.\UNC\server\share`. Reject lowercase `\\?\unc\server\share` because
the verbatim UNC marker is exact and uppercase. Include lower- and uppercase
drive letters. Tests must not require the path to exist or infer validity from
the test host filesystem.

Every path grammar, separator, quote, leading-BOM, and target-selection
rejection has status 1 and empty stdout. This includes an empty or otherwise
unknown `RUNNER_OS` value.

#### Runner parser and effective ordering

Implement a separate test-only model of `File.ReadAllLines(path,
Encoding.UTF8)` and path-list handling. Compare it with the pinned runner on
native Linux and Windows. The corpus covers LF, CRLF, and bare CR separators on
both hosts; an initial UTF-8 BOM; U+FEFF after earlier file content; empty and
whitespace-only lines; a final unterminated line; multiple entries; and
duplicates.

Assert that empty lines are ignored but whitespace-only lines are retained,
that later distinct entries appear earlier in the effective PATH, and that the
last runner-equivalent duplicate determines precedence. Because the runner
uses current-culture string comparison, do not turn non-ASCII duplicate
equivalence into a portable shoutx guarantee. Use only printable ASCII for
portable duplicate fixtures, and add one native observation case showing the
runner's treatment of otherwise identical paths where one contains U+200B.
Also observe an embedded U+FEFF case so byte preservation is not confused with
effective duplicate identity.

Append a shoutx record to both an empty command file and a file containing an
earlier record. A supported value must have the same parsed text in both
positions; the leading-U+FEFF rejection specifically prevents the known
position-dependent exception.

The actual-runner fixture calls `AddPathFileCommand.ProcessCommand` with a test
execution context whose `DeferredPrependPath` is null and whose
`Global.PrependPath` is observable. A test-only handler subclass then exposes
the protected `AddPrependPathToEnvironment` path and asserts the final PATH,
including reverse ordering and an original PATH that already starts with the
complete prepend string plus the PATH separator. This distinguishes runner
execution from a local transcription of its list and join logic.

A separate native Linux characterization test exercises the runner's container
branch and its actual `ProcessInvoker` argument-string path. A test helper
standing in for `docker` records the argv it receives. Cover a normal path, a
double quote, and odd and even trailing-backslash runs, and assert the observed
token boundaries and bytes. This test independently grounds the quote and
trailing-backslash rejection instead of merely reproducing the runner's string
concatenation.
