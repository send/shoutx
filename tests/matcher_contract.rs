use shoutx::{cli::MatcherKind, github_actions::encode_matcher, input::VALUE_LIMIT};
use std::{
    io::Write,
    process::{Command, Output, Stdio},
};

fn run(args: &[&str], input: &[u8]) -> Output {
    let mut child = Command::new(env!("CARGO_BIN_EXE_shoutx"))
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

fn check(args: &[&str], input: &[u8], status: i32, output: &[u8]) {
    let result = run(args, input);
    assert_eq!(result.status.code(), Some(status));
    assert_eq!(result.stdout, output);
    if status == 0 {
        assert!(result.stderr.is_empty());
    } else {
        assert!(result.stderr.starts_with(b"error: "));
        assert!(!result.stderr.windows(6).any(|value| value == b"SECRET"));
    }
}

const MODES: &[&[&str]] = &[
    &["github-actions:add-matcher"],
    &["github-actions:remove-matcher", "file"],
    &["github-actions:remove-matcher", "owner"],
];

#[test]
fn argv_does_not_wait_for_stdin_eof() {
    for mode in MODES {
        let mut child = Command::new(env!("CARGO_BIN_EXE_shoutx"))
            .args(*mode)
            .arg("value")
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .spawn()
            .unwrap();
        let open_stdin = child.stdin.take().unwrap();
        let deadline = std::time::Instant::now() + std::time::Duration::from_secs(10);
        loop {
            if child.try_wait().unwrap().is_some() {
                break;
            }
            if std::time::Instant::now() >= deadline {
                child.kill().unwrap();
                child.wait().unwrap();
                panic!("matcher waited for stdin EOF");
            }
            std::thread::sleep(std::time::Duration::from_millis(10));
        }
        drop(open_stdin);
        let result = child.wait_with_output().unwrap();
        assert!(result.status.success());
        assert!(result.stderr.is_empty());
        let expected = run(mode, b"value");
        assert_eq!(result.stdout, expected.stdout);
    }
}

#[test]
fn exact_encoding_and_sources() {
    for (mode, expected) in MODES.iter().zip([
        "::add-matcher::α,x::y=a%250A%0D%0A##[warning]literal \n",
        "::remove-matcher::α,x::y=a%250A%0D%0A##[warning]literal \n",
        "::remove-matcher owner=α%2Cx%3A%3Ay=a%250A%0D%0A##[warning]literal ,::\n",
    ]) {
        let value = "α,x::y=a%0A\r\n##[warning]literal ";
        for boundary in ["", "\n", "\r", "\r\n"] {
            let input = format!("{value}{boundary}");
            let mut args = mode.to_vec();
            args.extend(["--", &input]);
            check(&args, b"\xffSECRET", 0, expected.as_bytes());
            check(mode, input.as_bytes(), 0, expected.as_bytes());
        }
    }
    for owner in [
        " ",
        "\t",
        "\u{200b}",
        "\u{301}",
        "ع Ελληνικά हिन्दी 日本語 😀\u{a0}",
        "a=b",
        "a==b",
    ] {
        check(
            &["github-actions:remove-matcher", "owner", "--", owner],
            b"",
            0,
            format!("::remove-matcher owner={owner},::\n").as_bytes(),
        );
    }
}

#[test]
fn grammar_and_rejections() {
    for mode in MODES {
        for option in ["--help", "--version"] {
            let mut args = mode.to_vec();
            args.extend([option, "ignored"]);
            let expected = if option == "--help" {
                shoutx::HELP.to_owned()
            } else {
                shoutx::version_output()
            };
            check(&args, b"\xffSECRET", 0, expected.as_bytes());
        }
        for extras in [
            vec!["a", "b"],
            vec!["a", "--help"],
            vec!["--multiline"],
            vec!["--owner=a"],
        ] {
            let mut args = mode.to_vec();
            args.extend(extras);
            check(&args, b"", 2, b"");
        }
        for value in [b"".as_slice(), b"\n", b"\r\n", b"SECRET\0", b"SECRET\xff"] {
            check(mode, value, 1, b"");
        }
        check(mode, &vec![b'a'; VALUE_LIMIT + 1], 1, b"");
        for size in [VALUE_LIMIT - 1, VALUE_LIMIT] {
            let result = run(mode, &vec![b'a'; size]);
            assert!(result.status.success());
            assert!(result.stderr.is_empty());
            let prefix = if mode.len() == 1 {
                "::add-matcher::"
            } else if mode[1] == "file" {
                "::remove-matcher::"
            } else {
                "::remove-matcher owner="
            };
            let suffix = if mode.last() == Some(&"owner") {
                ",::\n"
            } else {
                "\n"
            };
            assert_eq!(
                result.stdout,
                format!("{prefix}{}{suffix}", "a".repeat(size)).as_bytes()
            );
        }
    }
    for mode in [None, Some("unknown"), Some("OWNER"), Some("--")] {
        let mut args = vec!["github-actions:remove-matcher"];
        args.extend(mode);
        check(&args, b"SECRET", 2, b"");
    }
    for value in ["=", "=SECRET", "==SECRET"] {
        check(
            &["github-actions:remove-matcher", "owner", value],
            b"",
            1,
            b"",
        );
    }
    for mode in &MODES[..2] {
        check(mode, "\u{301}SECRET".as_bytes(), 1, b"");
    }
    check(
        &["github-actions:remove-matcher", "--help"],
        b"",
        0,
        shoutx::HELP.as_bytes(),
    );
}

#[test]
fn native_invalid_arguments_and_limits() {
    #[cfg(unix)]
    let invalid = {
        use std::os::unix::ffi::OsStringExt;
        std::ffi::OsString::from_vec(b"SECRET\xff".to_vec())
    };
    #[cfg(windows)]
    let invalid = {
        use std::os::windows::ffi::OsStringExt;
        std::ffi::OsString::from_wide(&[83, 69, 67, 82, 69, 84, 0xd800])
    };
    for mode in MODES {
        let result = Command::new(env!("CARGO_BIN_EXE_shoutx"))
            .args(*mode)
            .arg(&invalid)
            .stdin(Stdio::null())
            .output()
            .unwrap();
        assert_eq!(result.status.code(), Some(1));
        assert!(result.stdout.is_empty());
        assert!(!result.stderr.windows(6).any(|value| value == b"SECRET"));
    }
    for kind in [
        MatcherKind::AddFile,
        MatcherKind::RemoveFile,
        MatcherKind::RemoveOwner,
    ] {
        for size in [VALUE_LIMIT - 1, VALUE_LIMIT] {
            let wire = encode_matcher(kind, vec![b'%'; size]).unwrap();
            assert!(wire.len() > 3 * size);
            assert_eq!(wire.iter().filter(|byte| **byte == b'\n').count(), 1);
            assert!(!wire.contains(&b'\r'));
        }
        assert!(encode_matcher(kind, vec![b'a'; VALUE_LIMIT + 1]).is_err());
    }
}
