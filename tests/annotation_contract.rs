use std::{
    ffi::OsString,
    io::Write,
    process::{Command, Output, Stdio},
};

fn run(args: &[&str], stdin: Option<&[u8]>) -> Output {
    let mut command = Command::new(env!("CARGO_BIN_EXE_shoutx"));
    command
        .args(args)
        .stdout(Stdio::piped())
        .stderr(Stdio::piped());
    if stdin.is_some() {
        command.stdin(Stdio::piped());
    } else {
        command.stdin(Stdio::null());
    }
    let mut child = command.spawn().unwrap();
    if let Some(input) = stdin {
        if let Err(error) = child.stdin.take().unwrap().write_all(input) {
            assert_eq!(error.kind(), std::io::ErrorKind::BrokenPipe);
        }
    }
    child.wait_with_output().unwrap()
}

fn success(args: &[&str], stdin: Option<&[u8]>, expected: &[u8]) {
    let output = run(args, stdin);
    assert_eq!(
        output.status.code(),
        Some(0),
        "{}",
        String::from_utf8_lossy(&output.stderr)
    );
    assert_eq!(output.stdout, expected);
    assert!(output.stderr.is_empty());
}

fn failure(args: &[&str], stdin: Option<&[u8]>, status: i32) -> Output {
    let output = run(args, stdin);
    assert_eq!(output.status.code(), Some(status));
    assert!(output.stdout.is_empty());
    assert!(output.stderr.starts_with(b"error: "));
    output
}

#[test]
fn severities_and_input_sources_follow_the_single_value_contract() {
    success(
        &["github-actions:notice", "notice"],
        Some(b"ignored"),
        b"::notice::notice\n",
    );
    success(
        &["github-actions:warning", "--", "-warning"],
        None,
        b"::warning::-warning\n",
    );
    success(
        &["github-actions:error"],
        Some(b"error\n"),
        b"::error::error\n",
    );
    success(
        &["github-actions:error", "--"],
        Some(b"error"),
        b"::error::error\n",
    );

    for args in [
        vec!["github-actions:notice", "-message"],
        vec!["github-actions:warning", "one", "two"],
        vec!["github-actions:error", "message", "--help"],
        vec!["github-actions:notice", "--multiline", "message"],
        vec!["github-actions:warning", "--title=value", "message"],
        vec!["github-actions:error", "--title"],
    ] {
        failure(&args, None, 2);
    }
}

#[test]
fn option_operands_are_data_and_duplicates_are_rejected() {
    success(
        &[
            "github-actions:warning",
            "--title",
            "-title",
            "--file",
            "-file",
            "message",
        ],
        None,
        b"::warning title=-title,file=-file::message\n",
    );
    for option in [
        "--title",
        "--file",
        "--line",
        "--end-line",
        "--column",
        "--end-column",
    ] {
        failure(
            &["github-actions:notice", option, "1", option, "2", "message"],
            None,
            2,
        );
    }
}

#[test]
fn message_framing_encoding_and_utf16_limit_are_exact() {
    success(
        &["github-actions:notice", "a%0A::b\r\nc\nd\re%25"],
        None,
        b"::notice::a%250A::b%0D%0Ac%0Ad%0De%2525\n",
    );
    success(
        &["github-actions:notice", "message\r\n"],
        None,
        b"::notice::message\n",
    );
    for boundary in ["\n", "\r", "\r\n"] {
        let framed = format!("message{boundary}");
        success(
            &["github-actions:notice", &framed],
            None,
            b"::notice::message\n",
        );
        success(
            &["github-actions:notice"],
            Some(framed.as_bytes()),
            b"::notice::message\n",
        );
    }
    success(
        &["github-actions:notice", "message\n\n"],
        None,
        b"::notice::message%0A\n",
    );

    let bmp = "a".repeat(4_096);
    assert_eq!(
        run(&["github-actions:notice", &bmp], None).status.code(),
        Some(0)
    );
    let supplementary = format!("aa{}", "😀".repeat(2_047));
    assert_eq!(
        run(&["github-actions:notice", &supplementary], None)
            .status
            .code(),
        Some(0)
    );
    failure(&["github-actions:notice", &(bmp + "a")], None, 1);
    let unicode_bmp = format!("a{}", "日".repeat(4_095));
    assert_eq!(
        run(&["github-actions:notice", &unicode_bmp], None)
            .status
            .code(),
        Some(0)
    );
    failure(&["github-actions:notice", &(unicode_bmp + "日")], None, 1);
    failure(&["github-actions:notice", &(supplementary + "😀")], None, 1);
    failure(
        &["github-actions:notice", &format!("{}😀", "a".repeat(4_095))],
        None,
        1,
    );
}

#[test]
fn help_version_and_option_operand_precedence_are_explicit() {
    for option in ["--help", "--version"] {
        let output = run(&["github-actions:notice", option], None);
        assert_eq!(output.status.code(), Some(0));
        assert!(output.stderr.is_empty());
    }
    success(
        &["github-actions:notice", "--title", "--help", "message"],
        None,
        b"::notice title=--help::message\n",
    );
    success(
        &["github-actions:notice", "--title", "title", "--", "--help"],
        None,
        b"::notice title=title::--help\n",
    );
    let output = run(
        &["github-actions:notice", "--title", "title", "--version"],
        None,
    );
    assert_eq!(output.status.code(), Some(0));
    assert!(output.stderr.is_empty());
}

#[test]
fn empty_whitespace_nul_and_invalid_text_fail_before_stdout() {
    for value in [
        "",
        "\n",
        " \t",
        "\u{0085}",
        "\u{00a0}",
        "\u{1680}",
        "\u{2000}\u{200a}",
        "\u{2028}\u{2029}\u{202f}\u{205f}\u{3000}",
    ] {
        failure(&["github-actions:error", value], None, 1);
    }
    failure(&["github-actions:error", "\u{feff}"], None, 1);
    failure(&["github-actions:error"], Some(b"private\0message"), 1);
    failure(&["github-actions:error"], Some(b"private\xffmessage"), 1);
    for value in [
        "\u{0301},file=/etc/passwd,line=3::tail",
        "\u{0903}message",
        "\u{20dd}message",
        "\u{3099}message",
        "\u{02b0}message",
        "\u{ff9e},file=/etc/passwd,line=3::tail",
        "\u{ff9f},file=/etc/passwd,line=3::tail",
    ] {
        failure(&["github-actions:error", value], None, 1);
        failure(&["github-actions:error"], Some(value.as_bytes()), 1);
    }
}

#[test]
fn all_severities_reject_legacy_fallback_payloads_without_output() {
    for command in [
        "github-actions:notice",
        "github-actions:warning",
        "github-actions:error",
    ] {
        for prefix in [
            '\u{0301}',
            '\u{034f}',
            '\u{0903}',
            '\u{20dd}',
            '\u{02b0}',
            '\u{ff9e}',
            '\u{ff9f}',
            '\u{e0100}',
            '\u{0e33}',
            '\u{0eb3}',
            '\u{1f3fb}',
            '\u{1f3fc}',
            '\u{1f3fd}',
            '\u{1f3fe}',
            '\u{1f3ff}',
            '\u{1d165}',
            '\u{16fe0}',
        ] {
            let value = format!("{prefix}private ##[warning]fallback");
            for output in [
                failure(&[command, &value], None, 1),
                failure(&[command], Some(value.as_bytes()), 1),
            ] {
                assert_eq!(
                    output.stderr,
                    b"error: annotation message is outside the ASCII boundary policy\n"
                );
            }
        }
    }
}

#[test]
fn transparent_leaders_cannot_hide_a_sensitive_message_prefix() {
    for command in [
        "github-actions:notice",
        "github-actions:warning",
        "github-actions:error",
    ] {
        for prefix in [
            "\u{200d}\u{0301}",
            "\u{200c}\u{0e33}",
            "\u{e0020}\u{1f3fb}",
            "\u{200c}\u{200d}\u{e0020}\u{e007f}\u{0301}",
        ] {
            let value = format!("{prefix}private ##[warning]fallback");
            for output in [
                failure(&[command, &value], None, 1),
                failure(&[command], Some(value.as_bytes()), 1),
            ] {
                assert_eq!(
                    output.stderr,
                    b"error: annotation message is outside the ASCII boundary policy\n"
                );
            }
        }
    }
}

#[test]
fn ascii_boundary_and_whole_header_allowlists_are_exact() {
    for severity in ["notice", "warning", "error"] {
        let command = format!("github-actions:{severity}");
        for first in 1u8..=127 {
            let value = format!(
                "{}\u{0301}日本語😀 ##[error]literal::tail",
                char::from(first)
            );
            if (32..=126).contains(&first) || first == 10 || first == 13 {
                let encoded = value
                    .replace('%', "%25")
                    .replace('\r', "%0D")
                    .replace('\n', "%0A");
                let expected = format!("::{severity}::{encoded}\n");
                success(&[&command, "--", &value], None, expected.as_bytes());
                success(&[&command], Some(value.as_bytes()), expected.as_bytes());
            } else {
                for output in [
                    failure(&[&command, &value], None, 1),
                    failure(&[&command], Some(value.as_bytes()), 1),
                ] {
                    assert_eq!(
                        output.stderr,
                        b"error: annotation message is outside the ASCII boundary policy\n"
                    );
                }
            }
        }
        for value in [
            "日本語",
            "😀",
            "é",
            "\u{200b}",
            "\u{00ad}",
            "\u{feff}",
            "\u{200d}",
            "\u{e007f}",
            "\u{10ffff}",
        ] {
            for output in [
                failure(&[&command, value], None, 1),
                failure(&[&command], Some(value.as_bytes()), 1),
            ] {
                assert_eq!(
                    output.stderr,
                    b"error: annotation message is outside the ASCII boundary policy\n"
                );
            }
        }
    }
    for field in ["title", "file"] {
        let option = format!("--{field}");
        for scalar in (1u8..=127).map(char::from).chain([
            '日',
            '😀',
            '\u{200d}',
            '\u{0600}',
            '\u{10ffff}',
            '\u{0085}',
            '\u{00a0}',
            '\u{3000}',
            '\u{200b}',
            '\u{00ad}',
            '\u{feff}',
        ]) {
            // Exercise internal bytes as well as a bad last byte. A final ASCII
            // byte must not hide a disallowed scalar earlier in the header.
            let value = format!("a{scalar}z");
            if scalar.is_ascii() && ((' '..='~').contains(&scalar) || matches!(scalar, '\r' | '\n'))
            {
                for value in [value, format!("{scalar}az"), format!("az{scalar}")] {
                    if value.starts_with('=') || value.ends_with(' ') {
                        continue; // Separate existing property validation tests cover these.
                    }
                    let encoded = value
                        .replace('%', "%25")
                        .replace('\r', "%0D")
                        .replace('\n', "%0A")
                        .replace(':', "%3A")
                        .replace(',', "%2C");
                    let expected = format!("::warning {field}={encoded}::message\n");
                    success(
                        &["github-actions:warning", &option, &value, "message"],
                        None,
                        expected.as_bytes(),
                    );
                }
            } else {
                for value in [format!("{scalar}az"), value, format!("az{scalar}")] {
                    let output = failure(
                        &["github-actions:warning", &option, &value, "message"],
                        None,
                        1,
                    );
                    let expected = if value.ends_with(char::is_whitespace) {
                        "error: annotation property ends with whitespace\n"
                    } else {
                        "error: annotation property is outside the ASCII header policy\n"
                    };
                    assert_eq!(output.stderr, expected.as_bytes());
                }
            }
        }
    }
}

#[test]
fn text_properties_are_encoded_in_fixed_order() {
    success(
        &[
            "github-actions:warning",
            "--file",
            "a,b:c%0A\r\n=x",
            "--title",
            "title::a=b",
            "message",
        ],
        None,
        b"::warning title=title%3A%3Aa=b,file=a%2Cb%3Ac%250A%0D%0A=x::message\n",
    );
    for option in ["--title", "--file"] {
        for value in ["", "=", "=x", "==x", "space ", "tab\t", "nbsp\u{00a0}"] {
            let output = failure(
                &["github-actions:notice", option, value, "message"],
                None,
                1,
            );
            let expected = if value.is_empty() {
                "error: annotation property is empty\n"
            } else if value.starts_with('=') {
                "error: annotation property begins with equals\n"
            } else {
                "error: annotation property ends with whitespace\n"
            };
            assert_eq!(output.stderr, expected.as_bytes());
        }
        for suffix in [
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
        ] {
            let value = format!("prepend{suffix}");
            failure(
                &[
                    "github-actions:notice",
                    option,
                    &value,
                    ",file=x,line=3::tail",
                ],
                None,
                1,
            );
        }
        success(
            &["github-actions:notice", option, "a==b", "message"],
            None,
            if option == "--title" {
                b"::notice title=a==b::message\n"
            } else {
                b"::notice file=a==b::message\n"
            },
        );
        success(
            &["github-actions:notice", option, "value\r\n", "message"],
            None,
            if option == "--title" {
                b"::notice title=value%0D%0A::message\n"
            } else {
                b"::notice file=value%0D%0A::message\n"
            },
        );
    }
}

#[test]
fn locations_are_canonical_and_dependencies_are_enforced() {
    success(
        &[
            "github-actions:error",
            "--end-column",
            "0009",
            "--line",
            "0005",
            "--column",
            "0001",
            "--end-line",
            "05",
            "message",
        ],
        None,
        b"::error line=5,endLine=5,col=1,endColumn=9::message\n",
    );
    success(
        &[
            "github-actions:error",
            "--line",
            "1",
            "--end-line",
            "2147483647",
            "message",
        ],
        None,
        b"::error line=1,endLine=2147483647::message\n",
    );
    let long_leading_zeroes = format!("{}1", "0".repeat(10_000));
    success(
        &[
            "github-actions:error",
            "--line",
            &long_leading_zeroes,
            "message",
        ],
        None,
        b"::error line=1::message\n",
    );

    for args in [
        vec!["--line", "0"],
        vec!["--line", "-1"],
        vec!["--line", "+1"],
        vec!["--line", " 1"],
        vec!["--line", "１"],
        vec!["--line", "2147483648"],
        vec!["--end-line", "1"],
        vec!["--column", "1"],
        vec!["--end-column", "1"],
        vec!["--line", "2", "--end-line", "1"],
        vec!["--line", "1", "--end-column", "2"],
        vec!["--line", "1", "--column", "2", "--end-column", "1"],
        vec!["--line", "1", "--end-line", "2", "--column", "1"],
    ] {
        let mut command = vec!["github-actions:notice"];
        command.extend(args);
        command.push("message");
        failure(&command, None, 1);
    }
}

#[test]
fn error_annotation_does_not_fail_the_process() {
    success(
        &["github-actions:error", "diagnostic"],
        None,
        b"::error::diagnostic\n",
    );
}

#[test]
fn raw_input_limit_precedes_final_boundary_consumption() {
    let at_limit = vec![b'a'; 1_048_576];
    let output = run(&["github-actions:notice"], Some(&at_limit));
    assert_eq!(output.status.code(), Some(1));
    assert!(output.stdout.is_empty());

    let mut over_limit = at_limit;
    over_limit.push(b'\n');
    let output = run(&["github-actions:notice"], Some(&over_limit));
    assert_eq!(output.status.code(), Some(1));
    assert!(output.stdout.is_empty());
}

#[cfg(unix)]
#[test]
fn invalid_utf8_in_every_option_operand_is_an_input_failure() {
    use std::os::unix::ffi::OsStringExt;

    for option in [
        "--title",
        "--file",
        "--line",
        "--end-line",
        "--column",
        "--end-column",
    ] {
        let output = Command::new(env!("CARGO_BIN_EXE_shoutx"))
            .arg("github-actions:notice")
            .arg(option)
            .arg(OsString::from_vec(vec![0xff]))
            .arg("message")
            .stdin(Stdio::null())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .output()
            .unwrap();
        assert_eq!(output.status.code(), Some(1));
        assert!(output.stdout.is_empty());
    }
}

#[cfg(windows)]
#[test]
fn invalid_utf16_in_every_option_operand_is_an_input_failure() {
    use std::os::windows::ffi::OsStringExt;

    for option in [
        "--title",
        "--file",
        "--line",
        "--end-line",
        "--column",
        "--end-column",
    ] {
        let output = Command::new(env!("CARGO_BIN_EXE_shoutx"))
            .arg("github-actions:notice")
            .arg(option)
            .arg(OsString::from_wide(&[0xd800]))
            .arg("message")
            .stdin(Stdio::null())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .output()
            .unwrap();
        assert_eq!(output.status.code(), Some(1));
        assert!(output.stdout.is_empty());
    }
}
