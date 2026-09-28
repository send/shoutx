use base64::{Engine as _, engine::general_purpose::STANDARD};
use serde::Serialize;
use std::{collections::BTreeMap, ffi::OsString, fs, path::PathBuf};

use shoutx::cli::{AnnotationRequest, AnnotationSeverity};

#[derive(Serialize)]
struct AnnotationCase {
    id: &'static str,
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

    definitions
        .into_iter()
        .map(
            |(id, request, severity, message, properties, windows_properties)| AnnotationCase {
                id,
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
        .collect()
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
