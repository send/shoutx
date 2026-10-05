use base64::{Engine as _, engine::general_purpose::STANDARD};
use serde::Serialize;
use std::{collections::BTreeMap, ffi::OsString, fs, path::PathBuf};

use shoutx::cli::{AnnotationRequest, AnnotationSeverity};

#[derive(Serialize)]
struct AnnotationCase {
    id: String,
    command: String,
    severity: &'static str,
    message: String,
    properties: BTreeMap<&'static str, String>,
    windows_properties: BTreeMap<&'static str, String>,
}

fn encode(value: &[u8]) -> String {
    STANDARD.encode(value)
}

fn request(
    severity: AnnotationSeverity,
    title: Option<&str>,
    file: Option<&str>,
    line: Option<&str>,
    end_line: Option<&str>,
    column: Option<&str>,
    end_column: Option<&str>,
) -> AnnotationRequest {
    AnnotationRequest {
        severity,
        title: title.map(OsString::from),
        file: file.map(OsString::from),
        line: line.map(OsString::from),
        end_line: end_line.map(OsString::from),
        column: column.map(OsString::from),
        end_column: end_column.map(OsString::from),
        message: None,
    }
}

fn properties(values: &[(&'static str, &str)]) -> BTreeMap<&'static str, String> {
    values
        .iter()
        .map(|(name, value)| (*name, encode(value.as_bytes())))
        .collect()
}

fn cases() -> Vec<AnnotationCase> {
    let definitions = [
        (
            "notice-plain",
            request(
                AnnotationSeverity::Notice,
                None,
                None,
                None,
                None,
                None,
                None,
            ),
            "notice",
            "plain message",
            properties(&[]),
            properties(&[]),
        ),
        (
            "warning-escaped",
            request(
                AnnotationSeverity::Warning,
                Some("title,with:delimiters%0A"),
                Some("src/a,b:c%25.rs"),
                None,
                None,
                None,
                None,
            ),
            "warning",
            "first\r\nsecond\n::error::literal%0A",
            properties(&[
                ("title", "title,with:delimiters%0A"),
                ("file", "src/a,b:c%25.rs"),
            ]),
            properties(&[
                ("title", "title,with:delimiters%0A"),
                ("file", "src/a,b:c%25.rs"),
            ]),
        ),
        (
            "error-location",
            request(
                AnnotationSeverity::Error,
                Some("range"),
                None,
                Some("0005"),
                Some("05"),
                Some("1"),
                Some("0009"),
            ),
            "error",
            "position 位置 😀",
            properties(&[
                ("title", "range"),
                ("line", "5"),
                ("endLine", "5"),
                ("col", "1"),
                ("endColumn", "9"),
            ]),
            properties(&[
                ("title", "range"),
                ("line", "5"),
                ("endLine", "5"),
                ("col", "1"),
                ("endColumn", "9"),
            ]),
        ),
        (
            "notice-multiline-range",
            request(
                AnnotationSeverity::Notice,
                Some("multiline range"),
                Some("src/range.rs"),
                Some("1"),
                Some("2147483647"),
                None,
                None,
            ),
            "notice",
            "large multiline range",
            properties(&[
                ("title", "multiline range"),
                ("file", "src/range.rs"),
                ("line", "1"),
                ("endLine", "2147483647"),
            ]),
            properties(&[
                ("title", "multiline range"),
                ("file", "src/range.rs"),
                ("line", "1"),
                ("endLine", "2147483647"),
            ]),
        ),
        (
            "warning-internal-equals",
            request(
                AnnotationSeverity::Warning,
                Some("a==b"),
                None,
                None,
                None,
                None,
                None,
            ),
            "warning",
            "a\u{200b}message",
            properties(&[("title", "a==b")]),
            properties(&[("title", "a==b")]),
        ),
        (
            "notice-soft-hyphen",
            request(
                AnnotationSeverity::Notice,
                Some("title-soft-hyphen"),
                None,
                None,
                None,
                None,
                None,
            ),
            "notice",
            "a\u{00ad}message",
            properties(&[("title", "title-soft-hyphen")]),
            properties(&[("title", "title-soft-hyphen")]),
        ),
        (
            "error-byte-order-mark",
            request(
                AnnotationSeverity::Error,
                Some("title-bom"),
                None,
                None,
                None,
                None,
                None,
            ),
            "error",
            "a\u{feff}message",
            properties(&[("title", "title-bom")]),
            properties(&[("title", "title-bom")]),
        ),
    ];

    let mut cases: Vec<_> = definitions
        .into_iter()
        .map(
            |(id, request, severity, message, properties, windows_properties)| AnnotationCase {
                id: id.to_owned(),
                command: encode(
                    &shoutx::github_actions::encode_annotation(
                        request,
                        message.as_bytes().to_vec(),
                    )
                    .unwrap(),
                ),
                severity,
                message: encode(message.as_bytes()),
                properties,
                windows_properties,
            },
        )
        .collect();

    for (id, prefix) in [
        ("zwj", "\u{200d}"),
        ("zwnj", "\u{200c}"),
        ("transparent-chain", "\u{200c}\u{200d}\u{e0020}\u{e007f}"),
        (
            "transparent-control-before-combining",
            "\u{200d}\u{200b}\u{0301}",
        ),
        ("tag-space", "\u{e0020}"),
        ("cancel-tag", "\u{e007f}"),
        ("space-before-combining", " \u{0301}"),
        ("format-before-combining", "\u{200b}\u{0301}"),
        ("bom-before-combining", "\u{feff}\u{0301}"),
    ] {
        let message = format!("a{prefix}message ##[warning]literal");
        cases.push(AnnotationCase {
            id: id.to_owned(),
            command: encode(
                &shoutx::github_actions::encode_annotation(
                    request(
                        AnnotationSeverity::Warning,
                        None,
                        None,
                        None,
                        None,
                        None,
                        None,
                    ),
                    message.as_bytes().to_vec(),
                )
                .unwrap(),
            ),
            severity: "warning",
            message: encode(message.as_bytes()),
            properties: properties(&[]),
            windows_properties: properties(&[]),
        });
    }

    let severities = [
        (AnnotationSeverity::Notice, "notice"),
        (AnnotationSeverity::Warning, "warning"),
        (AnnotationSeverity::Error, "error"),
    ];
    let message_fragments = [
        "plain",
        "percent%0A",
        "delimiter::text",
        "comma,title=value",
        "line1\r\nline2",
        "日本語😀",
        "\u{200b}zero-width",
        "\u{00ad}soft-hyphen",
        "\u{feff}byte-order-mark",
    ];
    for index in 0..96 {
        let (severity, severity_name) = severities[index % severities.len()];
        let message = format!(
            "generated-{index}-{}-{}",
            message_fragments[index % message_fragments.len()],
            message_fragments[(index * 5 + 1) % message_fragments.len()]
        );
        let title = format!("title-{index},colon::percent%25-ASCII=end");
        let file = format!("src/generated-{index},colon:percent%25-ASCII.rs");
        let line = (index + 1).to_string();
        let column = (index % 17 + 1).to_string();
        let end_column = (index % 17 + 2).to_string();
        let request = request(
            severity,
            Some(&title),
            Some(&file),
            Some(&line),
            Some(&line),
            Some(&column),
            Some(&end_column),
        );
        let expected = properties(&[
            ("title", &title),
            ("file", &file),
            ("line", &line),
            ("endLine", &line),
            ("col", &column),
            ("endColumn", &end_column),
        ]);
        cases.push(AnnotationCase {
            id: format!("generated-{index}"),
            command: encode(
                &shoutx::github_actions::encode_annotation(request, message.as_bytes().to_vec())
                    .unwrap(),
            ),
            severity: severity_name,
            message: encode(message.as_bytes()),
            windows_properties: expected.clone(),
            properties: expected,
        });
    }

    for first in (b' '..=b'~').chain(*b"\r\n") {
        for title in [
            format!("{}az", char::from(first)),
            format!("az{}", char::from(first)),
        ] {
            if title.starts_with('=') || title.ends_with(' ') {
                continue;
            }
            let message = "A\u{0301} ##[error]literal::tail";
            let expected = properties(&[("title", &title)]);
            cases.push(AnnotationCase {
                id: format!("property-boundary-{first}-{}", encode(title.as_bytes())),
                command: encode(
                    &shoutx::github_actions::encode_annotation(
                        request(
                            AnnotationSeverity::Warning,
                            Some(&title),
                            None,
                            None,
                            None,
                            None,
                            None,
                        ),
                        message.as_bytes().to_vec(),
                    )
                    .unwrap(),
                ),
                severity: "warning",
                message: encode(message.as_bytes()),
                properties: expected.clone(),
                windows_properties: expected,
            });
        }
        for (index, tail) in [
            "\u{0301}",
            "\u{200d}\u{0301}",
            "\u{0e33}",
            "\u{0eb3}",
            "\u{1f3fb}",
            "\u{e0020}\u{1f3fb}",
            "日本語😀",
            "\u{10ffff}",
        ]
        .into_iter()
        .enumerate()
        {
            for (severity, name) in severities {
                let message = format!("{}{tail} ##[error]literal::tail", char::from(first));
                let title = format!("a{}z", char::from(first));
                let expected = properties(&[("title", &title)]);
                cases.push(AnnotationCase {
                    id: format!("ascii-boundary-{name}-{first}-{index}"),
                    command: encode(
                        &shoutx::github_actions::encode_annotation(
                            request(severity, Some(&title), None, None, None, None, None),
                            message.as_bytes().to_vec(),
                        )
                        .unwrap(),
                    ),
                    severity: name,
                    message: encode(message.as_bytes()),
                    properties: expected.clone(),
                    windows_properties: expected,
                });
            }
        }
    }
    // Metadata boundaries are independent of the data-start policy. Exercise
    // marks, ignorables and prepend characters at actual field edges, not just
    // inside an ASCII wrapper. Cover both final text properties and a following
    // typed field; the latter alone cannot exercise the final-property boundary.
    for (index, scalar) in [
        '\u{0301}',
        '\u{200b}',
        '\u{0640}',
        '\u{0600}',
        '\u{0605}',
        '\u{06dd}',
        '\u{070f}',
        '\u{0890}',
        '\u{0891}',
        '\u{08e2}',
        '\u{0d4e}',
        '\u{110bd}',
        '\u{110cd}',
        '\u{111c2}',
        '\u{111c3}',
        '\u{1193f}',
        '\u{11941}',
        '\u{11a3a}',
        '\u{11a84}',
        '\u{11a89}',
        '\u{11d46}',
        '\u{11f02}',
    ]
    .into_iter()
    .enumerate()
    {
        let title = format!("{scalar}title{scalar}");
        let file = format!("{scalar}file.rs{scalar}");
        let message = ",file=x,line=9::tail";
        for field in ["title", "file"] {
            for tail in ["", "\u{200d}\u{034f}"] {
                let value = format!("{scalar}value{scalar}{tail}");
                let expected = properties(&[(field, &value)]);
                cases.push(AnnotationCase {
                    id: format!("unicode-final-{field}-{index}-{}", tail.len()),
                    command: encode(
                        &shoutx::github_actions::encode_annotation(
                            request(
                                AnnotationSeverity::Warning,
                                (field == "title").then_some(value.as_str()),
                                (field == "file").then_some(value.as_str()),
                                None,
                                None,
                                None,
                                None,
                            ),
                            message.as_bytes().to_vec(),
                        )
                        .unwrap(),
                    ),
                    severity: "warning",
                    message: encode(message.as_bytes()),
                    properties: expected.clone(),
                    windows_properties: expected,
                });
            }
        }
        let expected = properties(&[("title", &title), ("file", &file), ("line", "3")]);
        cases.push(AnnotationCase {
            id: format!("unicode-property-edges-{index}"),
            command: encode(
                &shoutx::github_actions::encode_annotation(
                    request(
                        AnnotationSeverity::Warning,
                        Some(&title),
                        Some(&file),
                        Some("3"),
                        None,
                        None,
                        None,
                    ),
                    message.as_bytes().to_vec(),
                )
                .unwrap(),
            ),
            severity: "warning",
            message: encode(message.as_bytes()),
            properties: expected.clone(),
            windows_properties: expected,
        });
    }
    for (index, first) in [
        "日本語",
        "😀",
        "é",
        "العربية",
        "हिन्दी",
        "Ελληνικά",
        "עברית",
        "ภาษาไทย",
        "한국어",
        "𐐀",
        "\u{02b0}",
        "\u{16fe0}",
        "\u{10ffff}",
    ]
    .into_iter()
    .enumerate()
    {
        for (name, severity) in [
            ("notice", AnnotationSeverity::Notice),
            ("warning", AnnotationSeverity::Warning),
            ("error", AnnotationSeverity::Error),
        ] {
            let message = format!("{first}\u{0301}-message::tail ##[warning]literal");
            let title = format!("{first}\u{0301},title:%25");
            let file = "日本語_العربية_😀.rs";
            let expected = properties(&[("title", &title), ("file", file), ("line", "1")]);
            cases.push(AnnotationCase {
                id: format!("unicode-start-{name}-{index}"),
                command: encode(
                    &shoutx::github_actions::encode_annotation(
                        request(
                            severity,
                            Some(&title),
                            Some(file),
                            Some("1"),
                            None,
                            None,
                            None,
                        ),
                        message.as_bytes().to_vec(),
                    )
                    .unwrap(),
                ),
                severity: name,
                message: encode(message.as_bytes()),
                properties: expected.clone(),
                windows_properties: expected,
            });
        }
    }
    cases
}

#[test]
fn generated_commands_have_one_physical_line() {
    for case in cases() {
        let command = STANDARD.decode(case.command).unwrap();
        assert!(command.starts_with(format!("::{}", case.severity).as_bytes()));
        assert!(command.ends_with(b"\n"));
        assert!(!command[..command.len() - 1].contains(&b'\r'));
        assert!(!command[..command.len() - 1].contains(&b'\n'));
    }
}

#[test]
#[ignore = "writes the generated corpus for the pinned runner oracle job"]
fn export_annotation_corpus() {
    let path = PathBuf::from(std::env::var_os("SHOUTX_ANNOTATION_CORPUS_PATH").unwrap());
    fs::write(path, serde_json::to_vec_pretty(&cases()).unwrap()).unwrap();
}
