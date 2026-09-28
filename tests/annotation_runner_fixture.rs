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
            "位置 😀",
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
                Some("a==b\u{200b}"),
                None,
                None,
                None,
                None,
                None,
            ),
            "warning",
            "\u{200b}message",
            properties(&[("title", "a==b\u{200b}")]),
            properties(&[("title", "a==b\u{200b}")]),
        ),
        (
            "notice-soft-hyphen",
            request(
                AnnotationSeverity::Notice,
                Some("title\u{00ad}"),
                None,
                None,
                None,
                None,
                None,
            ),
            "notice",
            "\u{00ad}message",
            properties(&[("title", "title\u{00ad}")]),
            properties(&[("title", "title\u{00ad}")]),
        ),
        (
            "error-byte-order-mark",
            request(
                AnnotationSeverity::Error,
                Some("title\u{feff}"),
                None,
                None,
                None,
                None,
                None,
            ),
            "error",
            "\u{feff}message",
            properties(&[("title", "title\u{feff}")]),
            properties(&[("title", "title\u{feff}")]),
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
        let title = format!("title-{index},colon::percent%25-日本語=end");
        let file = format!("src/generated-{index},colon:percent%25-日本語.rs");
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
