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
fn grammar_and_input_source_follow_single_value_contract() {
    success(
        &["github-actions:mask", "secret"],
        Some(b"ignored"),
        b"::add-mask::secret\n",
    );
    success(
        &["github-actions:mask", "--", "-secret"],
        None,
        b"::add-mask::-secret\n",
    );
    success(
        &["github-actions:mask"],
        Some(b"from-stdin\n"),
        b"::add-mask::from-stdin\n",
    );
    success(
        &["github-actions:mask", "--"],
        Some(b"from-stdin"),
        b"::add-mask::from-stdin\n",
    );

    for args in [
        vec!["github-actions:mask", "-secret"],
        vec!["github-actions:mask", "one", "two"],
        vec!["github-actions:mask", "secret", "--help"],
        vec!["github-actions:mask", "--multiline", "secret"],
        vec!["github-actions:mask", "--first-line", "secret"],
        vec!["github-actions:mask", "--join-lines", "secret"],
    ] {
        failure(&args, None, 2);
    }

    for args in [
        ["github-actions:mask", "--help"].as_slice(),
        ["github-actions:mask", "--version"].as_slice(),
    ] {
        let output = run(args, None);
        assert_eq!(output.status.code(), Some(0));
        assert!(output.stderr.is_empty());
    }
}

#[test]
fn percent_and_line_boundaries_are_escaped_in_order() {
    success(
        &["github-actions:mask", "a%0A::b\r\nc\nd\re%25"],
        None,
        b"::add-mask::a%250A::b%0D%0Ac%0Ad%0De%2525\n",
    );
    assert_eq!(
        shoutx::github_actions::encode_mask(b"x\r\ny\n".to_vec()).unwrap(),
        b"::add-mask::x%0D%0Ay\n"
    );
}

#[test]
fn one_final_boundary_is_input_framing_for_argv_and_stdin() {
    for boundary in ["\n", "\r", "\r\n"] {
        let value = format!("secret{boundary}");
        success(
            &["github-actions:mask", &value],
            None,
            b"::add-mask::secret\n",
        );
        success(
            &["github-actions:mask"],
            Some(value.as_bytes()),
            b"::add-mask::secret\n",
        );
    }

    success(
        &["github-actions:mask", "secret\n\n"],
        None,
        b"::add-mask::secret%0A\n",
    );
}

#[test]
fn empty_and_unicode_whitespace_only_values_are_rejected() {
    for value in [
        "",
        "\n",
        " \t",
        "\u{00a0}",
        "\u{0085}",
        "\u{1680}",
        "\u{2000}\u{2001}\u{2002}\u{2003}\u{2004}\u{2005}\u{2006}\u{2007}\u{2008}\u{2009}\u{200a}",
        "\u{2028}\u{2029}\u{202f}\u{205f}\u{3000}",
    ] {
        failure(&["github-actions:mask", value], None, 1);
        failure(&["github-actions:mask"], Some(value.as_bytes()), 1);
    }

    success(
        &["github-actions:mask", "\u{feff}"],
        None,
        "::add-mask::\u{feff}\n".as_bytes(),
    );
    success(
        &["github-actions:mask", "\u{200b}"],
        None,
        "::add-mask::\u{200b}\n".as_bytes(),
    );
}

#[test]
fn invalid_text_is_rejected_without_disclosure() {
    let nul = failure(&["github-actions:mask"], Some(b"private\0value"), 1);
    assert!(!nul.stderr.windows(7).any(|part| part == b"private"));

    let invalid = failure(&["github-actions:mask"], Some(b"private\xffvalue"), 1);
    assert!(!invalid.stderr.windows(7).any(|part| part == b"private"));

    failure(&["github-actions:mask"], Some(b"private\0value\n"), 1);
    failure(&["github-actions:mask"], Some(b"private\xffvalue\n"), 1);
}

#[test]
fn raw_input_limit_precedes_final_boundary_consumption() {
    let at_limit = vec![b'a'; 1_048_576];
    assert!(shoutx::github_actions::encode_mask(at_limit).is_ok());

    let mut framed_at_limit = vec![b'a'; 1_048_575];
    framed_at_limit.push(b'\n');
    let output = shoutx::github_actions::encode_mask(framed_at_limit).unwrap();
    assert_eq!(output.len(), 12 + 1_048_575 + 1);

    let mut over_limit = vec![b'a'; 1_048_576];
    over_limit.push(b'\n');
    assert!(shoutx::github_actions::encode_mask(over_limit).is_err());

    let worst_case = vec![b'%'; 1_048_576];
    let output = shoutx::github_actions::encode_mask(worst_case).unwrap();
    assert_eq!(output.len(), 12 + 3 * 1_048_576 + 1);
}

#[cfg(unix)]
#[test]
fn invalid_utf8_argv_is_rejected() {
    use std::os::unix::ffi::OsStringExt;

    let output = Command::new(env!("CARGO_BIN_EXE_shoutx"))
        .arg("github-actions:mask")
        .arg(OsString::from_vec(vec![0xff]))
        .stdin(Stdio::null())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .output()
        .unwrap();
    assert_eq!(output.status.code(), Some(1));
    assert!(output.stdout.is_empty());
}

#[cfg(windows)]
#[test]
fn invalid_utf16_argv_is_rejected() {
    use std::os::windows::ffi::OsStringExt;

    let output = Command::new(env!("CARGO_BIN_EXE_shoutx"))
        .arg("github-actions:mask")
        .arg(OsString::from_wide(&[0xd800]))
        .stdin(Stdio::null())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .output()
        .unwrap();
    assert_eq!(output.status.code(), Some(1));
    assert!(output.stdout.is_empty());
}
