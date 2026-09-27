use std::{
    io::Write,
    process::{Command, Output, Stdio},
};

use shoutx::{
    ErrorClass,
    github_actions::{TargetOs, encode_path},
    input::VALUE_LIMIT,
};

fn run(args: &[&str], stdin: Option<&[u8]>, runner_os: Option<&str>) -> Output {
    let mut command = Command::new(env!("CARGO_BIN_EXE_shoutx"));
    command
        .args(args)
        .stdout(Stdio::piped())
        .stderr(Stdio::piped());
    match runner_os {
        Some(value) => command.env("RUNNER_OS", value),
        None => command.env_remove("RUNNER_OS"),
    };
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

fn success(value: &str, target: &str, expected: &[u8]) {
    let output = run(&["github-actions:path", value], None, Some(target));
    assert_eq!(
        output.status.code(),
        Some(0),
        "{}",
        String::from_utf8_lossy(&output.stderr)
    );
    assert_eq!(output.stdout, expected);
    assert!(output.stderr.is_empty());
}

fn rejected(value: &str, target: &str) {
    let output = run(&["github-actions:path", value], None, Some(target));
    assert_eq!(
        output.status.code(),
        Some(1),
        "value {value:?}: {}",
        String::from_utf8_lossy(&output.stderr)
    );
    assert!(output.stdout.is_empty());
    assert!(output.stderr.starts_with(b"error: "));
    assert!(!output.stderr.starts_with(b"::"));
}

#[test]
fn grammar_stdin_and_final_boundary_contract() {
    success("/x", "Linux", b"/x\n");
    success("/x\n", "Linux", b"/x\n");
    success("/x\r", "Linux", b"/x\n");
    success("/x\r\n", "Linux", b"/x\n");

    let stdin = run(&["github-actions:path"], Some(b"/stdin\n"), Some("Linux"));
    assert_eq!(stdin.status.code(), Some(0));
    assert_eq!(stdin.stdout, b"/stdin\n");
    let after_separator = run(
        &["github-actions:path", "--"],
        Some(b"/stdin"),
        Some("Linux"),
    );
    assert_eq!(after_separator.status.code(), Some(0));
    assert_eq!(after_separator.stdout, b"/stdin\n");

    let ignored = run(
        &["github-actions:path", "/argv"],
        Some(b"invalid\nvalue"),
        Some("Linux"),
    );
    assert_eq!(ignored.status.code(), Some(0));
    assert_eq!(ignored.stdout, b"/argv\n");

    for args in [
        vec!["github-actions:path", "-x"],
        vec!["github-actions:path", "/x", "/y"],
        vec!["github-actions:path", "/x", "--help"],
    ] {
        let output = run(&args, None, Some("Linux"));
        assert_eq!(output.status.code(), Some(2));
        assert!(output.stdout.is_empty());
    }
    let dash_data = run(&["github-actions:path", "--", "-x"], None, Some("Linux"));
    assert_eq!(dash_data.status.code(), Some(1));
    assert!(dash_data.stdout.is_empty());
}

#[test]
fn posix_paths_are_validated_and_preserved() {
    for value in [
        "/",
        "/a",
        "/a b",
        "/a/./b",
        "/a/../b",
        "//a///",
        "/日本語",
        "/a\u{feff}b",
    ] {
        let mut expected = value.as_bytes().to_vec();
        expected.push(b'\n');
        success(value, "Linux", &expected);
        success(value, "macOS", &expected);
    }
    for value in [
        "",
        "a",
        "./a",
        "../a",
        "\u{feff}/a",
        "/a:b",
        "/a\"b",
        "/a\\",
        "/a\\\\",
        "/a\nb",
        "/a\rb",
        "/a\n\n",
    ] {
        rejected(value, "Linux");
    }
}

#[test]
fn windows_paths_are_validated_and_preserved() {
    for value in [
        "C:\\",
        "c:/tools",
        "C:\\a b\\..\\",
        "\\\\server\\share",
        "//server/share",
        "/\\server/share",
        "\\/server\\share",
        "\\\\?\\C:\\",
        "\\\\?\\C:\\tools/x",
        "\\\\?\\UNC\\server\\share",
        "C:\\日本語",
        "C:\\a\u{feff}b",
    ] {
        let mut expected = value.as_bytes().to_vec();
        expected.push(b'\n');
        success(value, "Windows", &expected);
    }
    for value in [
        "",
        "C:",
        "C:tools",
        "\\tools",
        "relative",
        "\\\\server",
        "\\\\server\\",
        "\\\\server\\.\\x",
        "\\\\server\\?\\x",
        "//./x",
        "/\\.\\x",
        "//?/C:/x",
        "\\\\?\\C:/x",
        "\\\\?\\C:",
        "\\\\?\\UNC\\server",
        "\\\\?\\UNC\\server\\.\\x",
        "\\\\?\\UNC\\server\\?\\x",
        "\\\\?\\GLOBALROOT\\x",
        "\\\\?\\Volume{x}\\",
        "\\\\?\\pipe\\x",
        "\\\\.\\UNC\\server\\share",
        "\\\\?\\unc\\server\\share",
        "C:\\a;b",
        "C:\\a\"b",
        "\u{feff}C:\\a",
        "C:\\a\nb",
        "C:\\a\rb",
    ] {
        rejected(value, "Windows");
    }
}

#[test]
fn target_selection_is_exact_and_precedes_stdin_reading() {
    for target in ["", "linux", "MacOS", "windows", "Other"] {
        let output = run(&["github-actions:path"], Some(b"/x"), Some(target));
        assert_eq!(output.status.code(), Some(1));
        assert!(output.stdout.is_empty());
    }

    let native_value = if cfg!(windows) { "C:\\x" } else { "/x" };
    let native = run(&["github-actions:path", native_value], None, None);
    assert_eq!(native.status.code(), Some(0));
}

#[test]
fn library_rejects_binary_and_resource_limit_failures_before_output() {
    for value in [vec![0xff], b"/a\0b".to_vec()] {
        let error = encode_path(value, TargetOs::Linux).unwrap_err();
        assert_eq!(error.class(), ErrorClass::Failure);
    }
    assert!(encode_path(vec![b'/'; VALUE_LIMIT], TargetOs::Linux).is_ok());
    let error = encode_path(vec![b'/'; VALUE_LIMIT + 1], TargetOs::Linux).unwrap_err();
    assert_eq!(error.class(), ErrorClass::Failure);
    assert!(encode_path(b"/x".to_vec(), TargetOs::Unknown).is_err());
}
