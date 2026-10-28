# Azure source-parser oracle

Run `cargo build --locked`, then:

```sh
mise exec -- python3 -B tests/azure-oracle/verify.py target/debug/shoutx
```

Windows uses `target/debug/shoutx.exe`. CI installs .NET 8.0.425 directly.
The harness downloads two commit- and SHA-256-pinned MIT-licensed Agent source
files into a temporary directory, compiles them unchanged with a constructor
assertion stub, and compares actual CLI output with independently supplied
command/property/data expectations. No production dependency is added.

It checks 3,218 successful cases (including 333 native PATH cases) and twenty-six
discriminating negative controls. PATH cases require the fixed `prependpath`
event, no properties and exact decoded input; native validation precedes them.
Metadata cases check the distinct `build` area, fixed event, empty properties
and exact data, including Unicode, literal escapes and UTF-16 length boundaries.
Wrong-area controls ensure task and build commands are not interchangeable.
Secret-variable cases cover all four output/read-only flag combinations, exact
secret properties, Unicode, literal escapes, inert command-like data and the
semantic cap. Negative controls flip each boolean, add a property or add a
second command. Consumer assignment, scope and masking are separate hosted gates.
Randomized cases use a fixed seed across Unicode scalar values; this is a
regression corpus, not a character-set proof. Only bounded counts and source
identity are printed. Fetch/build/process failures fail the test.

Mask cases require `setsecret`, no properties and exact decoded values.
Batch cases independently select nonempty CRLF/CR/LF-delimited entries and
compare the entire ordered sequence, including duplicates and whitespace.
They include the 1 MiB raw cap and 1,024-entry cap. Negative controls remove,
reorder or add records and alter properties; parsing each surviving line alone
cannot satisfy these checks.

This is a .NET 8 source-component test, **not a running Agent or hosted service
test**. It does not cover task handlers, scope, service quotas or log rendering.
See the [compatibility evidence](../../docs/compatibility/azure-pipelines.md).
