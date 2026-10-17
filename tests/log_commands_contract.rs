use shoutx::{cli::LogKind, github_actions::encode_log, input::VALUE_LIMIT};
use std::{
    io::Write,
    process::{Command, Stdio},
};

fn check(command: &str, args: &[&str], input: &[u8], status: i32, stdout: &[u8]) {
    let mut child = Command::new(env!("CARGO_BIN_EXE_shoutx"))
        .arg(format!("github-actions:{command}"))
        .args(args)
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .unwrap();
    if let Err(error) = child.stdin.take().unwrap().write_all(input) {
        assert_eq!(error.kind(), std::io::ErrorKind::BrokenPipe);
    }
    let result = child.wait_with_output().unwrap();
    assert_eq!(result.status.code(), Some(status));
    assert_eq!(result.stdout, stdout);
    if status == 0 {
        assert!(result.stderr.is_empty());
    } else {
        assert!(result.stderr.starts_with(b"error: "));
        assert!(!result.stderr.windows(6).any(|bytes| bytes == b"SECRET"));
    }
}

#[test]
fn grammar_sources_and_exact_encoding() {
    for command in ["debug", "group", "endgroup"] {
        check(
            command,
            &["--help", "ignored"],
            b"",
            0,
            shoutx::HELP.as_bytes(),
        );
        check(
            command,
            &["--version", "ignored"],
            b"",
            0,
            shoutx::version_output().as_bytes(),
        );
    }
    for command in ["debug", "group"] {
        for value in [
            "",
            " ",
            " Ελληνικά_日本語_😀",
            "a%0A::error::x##[warning]tail",
        ] {
            for ending in ["", "\n", "\r", "\r\n"] {
                let input = format!("{value}{ending}");
                let expected = format!("::{command}::{}\n", value.replace('%', "%25"));
                check(command, &[&input], b"\xffSECRET", 0, expected.as_bytes());
                check(command, &[], input.as_bytes(), 0, expected.as_bytes());
            }
        }
        check(
            command,
            &["--", "--help"],
            b"",
            0,
            format!("::{command}::--help\n").as_bytes(),
        );
        check(
            command,
            &["--"],
            b"abc",
            0,
            format!("::{command}::abc\n").as_bytes(),
        );
        check(command, &["--help"], b"", 0, shoutx::HELP.as_bytes());
        check(
            command,
            &["--version"],
            b"",
            0,
            shoutx::version_output().as_bytes(),
        );
        for args in [
            vec!["-x"],
            vec!["--multiline"],
            vec!["a", "b"],
            vec!["a", "--help"],
        ] {
            check(command, &args, b"", 2, b"");
        }
    }
    check(
        "debug",
        &[],
        b"a\r\nb\rc\n\n",
        0,
        b"::debug::a%0D%0Ab%0Dc%0A\n",
    );
    check("endgroup", &[], b"\xffSECRET", 0, b"::endgroup::\n");
    check("endgroup", &["--"], b"\xffSECRET", 0, b"::endgroup::\n");
    check("endgroup", &["--help"], b"", 0, shoutx::HELP.as_bytes());
    for args in [vec![""], vec!["data"], vec!["--", "--help"]] {
        check("endgroup", &args, b"", 2, b"");
    }
}

#[test]
fn rejection_is_before_output() {
    for command in ["debug", "group"] {
        for input in [
            b"SECRET\0".as_slice(),
            b"SECRET\xff",
            "\u{301}SECRET::x".as_bytes(),
        ] {
            check(command, &[], input, 1, b"");
        }
        check(command, &[], &vec![b'a'; VALUE_LIMIT + 1], 1, b"");
    }
    for value in ["SECRET\n::endgroup::", "SECRET\rnext", "SECRET\n\n"] {
        check("group", &[value], b"", 1, b"");
        check("group", &[], value.as_bytes(), 1, b"");
    }
}

#[test]
fn invalid_native_argv_is_rejected_without_output() {
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
    for command in ["debug", "group"] {
        let result = Command::new(env!("CARGO_BIN_EXE_shoutx"))
            .arg(format!("github-actions:{command}"))
            .arg(&invalid)
            .stdin(Stdio::null())
            .output()
            .unwrap();
        assert_eq!(result.status.code(), Some(1));
        assert!(result.stdout.is_empty());
        assert!(result.stderr.starts_with(b"error: "));
        assert!(!result.stderr.windows(6).any(|bytes| bytes == b"SECRET"));
    }
}

#[test]
fn argv_and_endgroup_do_not_wait_for_stdin_eof() {
    for (command, value, expected) in [
        ("debug", Some("value"), b"::debug::value\n".as_slice()),
        ("group", Some("value"), b"::group::value\n".as_slice()),
        ("endgroup", None, b"::endgroup::\n".as_slice()),
    ] {
        let mut process = Command::new(env!("CARGO_BIN_EXE_shoutx"));
        process.arg(format!("github-actions:{command}"));
        if let Some(value) = value {
            process.arg(value);
        }
        let mut child = process
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
                panic!("{command} waited for stdin EOF");
            }
            std::thread::sleep(std::time::Duration::from_millis(10));
        }
        drop(open_stdin);
        let result = child.wait_with_output().unwrap();
        assert!(result.status.success());
        assert_eq!(result.stdout, expected);
        assert!(result.stderr.is_empty());
    }
}

#[test]
fn limits_and_generated_wire_invariants() {
    for kind in [LogKind::Debug, LogKind::Group] {
        for size in [VALUE_LIMIT - 1, VALUE_LIMIT] {
            assert_eq!(
                encode_log(kind, vec![b'%'; size]).unwrap().len(),
                3 * size + 10
            );
        }
        assert!(encode_log(kind, vec![b'a'; VALUE_LIMIT + 1]).is_err());
        for scalar in (1..=0x10ffff).step_by(997) {
            let Some(c) = char::from_u32(scalar) else {
                continue;
            };
            let value = format!("A{c}%0A::error::x##[warning]tail");
            let wire = encode_log(kind, value.into_bytes()).unwrap();
            assert_eq!(wire.iter().filter(|byte| **byte == b'\n').count(), 1);
            assert!(!wire.contains(&b'\r'));
        }
    }
}
