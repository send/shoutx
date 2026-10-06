use std::{
    path::PathBuf,
    process::{Command, Output, Stdio},
};

fn binary() -> PathBuf {
    match std::env::var_os("SHOUTX_VERIFY_BINARY") {
        Some(path) => PathBuf::from(path),
        None if std::env::var_os("SHOUTX_VERIFY_REQUIRE_EXTERNAL").is_some() => {
            panic!("external binary path is required")
        }
        None => PathBuf::from(env!("CARGO_BIN_EXE_shoutx")),
    }
}

fn run(args: &[&str]) -> Output {
    Command::new(binary())
        .args(args)
        .env_remove("RUNNER_OS")
        .stdin(Stdio::null())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .output()
        .expect("failed to execute the binary under verification")
}

fn matches_result(
    status: Option<i32>,
    stdout: &[u8],
    stderr: &[u8],
    expected_status: i32,
    expected_stdout: &[u8],
    expected_stderr: &[u8],
) -> bool {
    status == Some(expected_status) && stdout == expected_stdout && stderr == expected_stderr
}

fn verify(args: &[&str], status: i32, stdout: &[u8], stderr: &[u8]) {
    let actual = run(args);
    assert!(
        matches_result(
            actual.status.code(),
            &actual.stdout,
            &actual.stderr,
            status,
            stdout,
            stderr
        ),
        "artifact result mismatch (stdout length {}, stderr length {})",
        actual.stdout.len(),
        actual.stderr.len()
    );
}

#[test]
fn surface_verifier_sentinel() {
    if let Ok(expected) = std::env::var("SHOUTX_EXPECT_SURFACE") {
        assert_eq!(expected, "stable", "only the official surface is supported");
    }
}

#[test]
fn packaged_binary_has_exact_help_and_version() {
    verify(
        &["--help"],
        0,
        include_bytes!("fixtures/stable-help.txt"),
        b"",
    );
    verify(
        &["--version"],
        0,
        format!("shoutx {}\n", shoutx::VERSION).as_bytes(),
        b"",
    );
}

#[test]
fn packaged_binary_exposes_all_eight_writers() {
    for command in [
        "github-actions:output",
        "github-actions:env",
        "github-actions:state",
    ] {
        verify(
            &[command, "NAME", "fixed-value"],
            0,
            b"NAME=fixed-value\n",
            b"",
        );
    }
    if cfg!(windows) {
        verify(
            &["github-actions:path", "C:\\fixed"],
            0,
            b"C:\\fixed\n",
            b"",
        );
    } else {
        verify(&["github-actions:path", "/fixed"], 0, b"/fixed\n", b"");
    }
    verify(
        &["github-actions:mask", "\u{03b1}%\nvalue"],
        0,
        "::add-mask::\u{03b1}%25%0Avalue\n".as_bytes(),
        b"",
    );
    for severity in ["notice", "warning", "error"] {
        let command = format!("github-actions:{severity}");
        verify(
            &[
                &command,
                "--title",
                "\u{200b}",
                "--file",
                "\u{03b1}.rs",
                "--line",
                "001",
                "\u{1f600}%\nvalue",
            ],
            0,
            format!("::{severity} title=\u{200b},file=\u{03b1}.rs,line=1,::\u{1f600}%25%0Avalue\n")
                .as_bytes(),
            b"",
        );
    }
}

#[test]
fn packaged_binary_rejects_invalid_and_unintended_surface() {
    for command in [
        "github-actions:add-mask",
        "github-actions:debug",
        "github-actions:group",
        "github-actions:stop-commands",
        "github-actions:raw",
    ] {
        verify(
            &[command, "fixed-value"],
            2,
            b"",
            b"error: unknown command\n",
        );
    }
    verify(
        &["github-actions:mask", "\u{200b}value"],
        1,
        b"",
        b"error: mask value is outside the Unicode boundary policy\n",
    );
    for command in [
        "github-actions:notice",
        "github-actions:warning",
        "github-actions:error",
    ] {
        verify(
            &[command, "\u{200b}value"],
            1,
            b"",
            b"error: annotation message is outside the Unicode boundary policy\n",
        );
    }
}

#[test]
fn result_checker_rejects_corrupt_status_bytes_and_diagnostics() {
    let expected = b"::notice::fixed\n";
    assert!(matches_result(Some(0), expected, b"", 0, expected, b""));
    for (status, stdout, stderr) in [
        (Some(1), expected.as_slice(), b"".as_slice()),
        (None, expected.as_slice(), b"".as_slice()),
        (Some(0), b"".as_slice(), b"".as_slice()),
        (Some(0), b"::warning::fixed\n".as_slice(), b"".as_slice()),
        (Some(0), b"::notice::fixed\r\n".as_slice(), b"".as_slice()),
        (
            Some(0),
            expected.as_slice(),
            b"unexpected diagnostic".as_slice(),
        ),
    ] {
        assert!(!matches_result(status, stdout, stderr, 0, expected, b""));
    }
    assert!(!matches_result(
        Some(1),
        b"leak",
        b"error\n",
        1,
        b"",
        b"error\n"
    ));
    assert!(!matches_result(
        Some(2),
        b"",
        b"error\n",
        1,
        b"",
        b"error\n"
    ));
}
