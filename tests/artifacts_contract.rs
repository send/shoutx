use std::{
    io::Write,
    process::{Command, Output, Stdio},
};

fn run(args: &[&str], input: &[u8]) -> Output {
    let mut child = Command::new(env!("CARGO_BIN_EXE_shoutx"))
        .arg("github-actions:artifacts")
        .args(args)
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .unwrap();
    if let Err(error) = child.stdin.take().unwrap().write_all(input) {
        assert_eq!(error.kind(), std::io::ErrorKind::BrokenPipe);
    }
    child.wait_with_output().unwrap()
}

fn check(args: &[&str], input: &[u8], status: i32, expected: &[u8]) {
    let result = run(args, input);
    assert_eq!(result.status.code(), Some(status));
    assert_eq!(result.stdout, expected);
    if status == 0 {
        assert!(result.stderr.is_empty());
    } else {
        assert!(result.stderr.starts_with(b"error: "));
        assert!(!result.stderr.windows(6).any(|w| w == b"SECRET"));
    }
}

#[test]
fn file_grammar_and_input_selection() {
    check(&["file"], b"report\r\n", 0, b"file://report\n");
    check(&["file", "--"], b"report", 0, b"file://report\n");
    check(&["file", "report"], b"\xffSECRET", 0, b"file://report\n");
    check(&["file", "--", "--help"], b"", 0, b"file://--help\n");
    for args in [
        vec![],
        vec!["--", "file"],
        vec!["unknown"],
        vec!["file", "-x"],
        vec!["file", "a", "b"],
        vec!["file", "a", "--help"],
        vec!["file", "--multiline"],
    ] {
        check(&args, b"", 2, b"");
    }
    for args in [
        vec!["--help"],
        vec!["file", "--help"],
        vec!["oci", "--help"],
    ] {
        check(&args, b"", 0, shoutx::HELP.as_bytes());
    }
    for args in [
        vec!["--version"],
        vec!["file", "--version"],
        vec!["oci", "--version"],
    ] {
        check(&args, b"", 0, shoutx::version_output().as_bytes());
    }
}

#[test]
fn file_rejection_precedes_stdout_and_does_not_disclose_input() {
    for input in [
        b"".as_slice(),
        b"\xffSECRET",
        b"SECRET\0",
        b"SECRET\nfile://other",
        b"SECRET=other",
        b"SECRET\n\n",
        b"SECRET ",
    ] {
        check(&["file"], input, 1, b"");
        if let Ok(text) = std::str::from_utf8(input) {
            if !input.contains(&0) {
                check(&["file", text], b"", 1, b"");
            }
        }
    }
    check(
        &["file"],
        &vec![b'a'; shoutx::input::VALUE_LIMIT + 1],
        1,
        b"",
    );
    check(
        &["file"],
        &vec![b'a'; shoutx::input::VALUE_LIMIT - 7],
        1,
        b"",
    );
}

#[test]
fn oci_requires_two_operands_and_preserves_fields() {
    let digest = format!("sha256:{}", "a".repeat(64));
    for reference in [
        "registry:5000/image:tag",
        "a@b",
        " 日本語_😀 ",
        "file://name",
    ] {
        check(
            &["oci", reference, &digest],
            b"\xffSECRET",
            0,
            format!("oci://{reference}@{digest}\n").as_bytes(),
        );
    }
    check(
        &["oci", "--", "-image", &digest],
        b"",
        0,
        format!("oci://-image@{digest}\n").as_bytes(),
    );
    for args in [
        vec!["oci"],
        vec!["oci", "--"],
        vec!["oci", "ref"],
        vec!["oci", "-ref", &digest],
        vec!["oci", "ref", &digest, "extra"],
    ] {
        check(&args, b"", 2, b"");
    }
    for reference in ["", "SECRET\n", "SECRET\r", "SECRET=value"] {
        check(&["oci", reference, &digest], b"", 1, b"");
    }
    for bad in ["", "--help", "SECRET", "sha256:0"] {
        check(&["oci", "ref", bad], b"", 1, b"");
    }
}

#[cfg(unix)]
#[test]
fn invalid_argv_encoding_is_not_lossy() {
    use std::{ffi::OsString, os::unix::ffi::OsStringExt};
    for variant in ["file", "oci"] {
        let mut command = Command::new(env!("CARGO_BIN_EXE_shoutx"));
        command
            .args(["github-actions:artifacts", variant])
            .arg(OsString::from_vec(b"SECRET\xff".to_vec()));
        if variant == "oci" {
            command.arg(format!("sha256:{}", "a".repeat(64)));
        }
        let result = command.stdin(Stdio::null()).output().unwrap();
        assert_eq!(result.status.code(), Some(1));
        assert!(result.stdout.is_empty());
        assert!(!result.stderr.windows(6).any(|w| w == b"SECRET"));
    }
}
