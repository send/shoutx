use shoutx::ShoutxError;
use shoutx::cli::{Destination, LineMode, WriteRequest};
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
        child.stdin.take().unwrap().write_all(input).unwrap();
    }
    child.wait_with_output().unwrap()
}

fn success(args: &[&str], expected: &[u8]) {
    let output = run(args, None);
    assert_eq!(
        output.status.code(),
        Some(0),
        "{}",
        String::from_utf8_lossy(&output.stderr)
    );
    assert_eq!(output.stdout, expected);
    assert!(output.stderr.is_empty());
}

#[test]
fn default_mode_and_operand_rules() {
    success(
        &["github-actions:output", "result", "hello"],
        b"result=hello\n",
    );
    success(
        &["github-actions:output", "result", "hello\n"],
        b"result=hello\n",
    );
    success(
        &["github-actions:output", "result", "hello\r\n"],
        b"result=hello\n",
    );
    success(&["github-actions:output", "result", "-x"], b"result=-x\n");
    success(
        &["github-actions:output", "result", "--help"],
        b"result=--help\n",
    );
    success(&["github-actions:output", "result", ""], b"result=\n");
}

#[test]
fn help_version_and_grammar_contract() {
    for args in [
        ["--help"].as_slice(),
        ["github-actions:output", "--help"].as_slice(),
    ] {
        let output = run(args, None);
        assert_eq!(output.status.code(), Some(0));
        assert!(output.stdout.starts_with(b"shoutx -"));
    }
    let version = run(&["--version"], None);
    assert_eq!(version.status.code(), Some(0));
    assert!(version.stdout.starts_with(b"shoutx "));
    success(&["github-actions:output", "--", "r", "-x"], b"r=-x\n");
    success(&["github-actions:output", "r", "--"], b"r=--\n");
    success(
        &[
            "github-actions:output",
            "--join-lines-with",
            "-",
            "r",
            "a\nb",
        ],
        b"r=a-b\n",
    );
    for args in [
        vec!["github-actions:output"],
        vec!["github-actions:output", "--unknown", "r"],
        vec!["github-actions:output", "--join-lines-with"],
    ] {
        let output = run(&args, None);
        assert_eq!(output.status.code(), Some(2));
        assert!(output.stdout.is_empty());
    }
}

#[test]
fn line_modes_follow_common_final_framing() {
    success(
        &["github-actions:output", "--first-line", "r", "a\nb\n"],
        b"r=a\n",
    );
    success(
        &["github-actions:output", "--join-lines", "r", "a\n\nb\n"],
        b"r=a  b\n",
    );
    success(
        &[
            "github-actions:output",
            "--join-lines-with",
            ",",
            "r",
            "a\r\nb\r",
        ],
        b"r=a,b\n",
    );
    success(
        &["github-actions:output", "--join-lines-with=", "r", "a\nb"],
        b"r=ab\n",
    );
}

#[test]
fn stdin_is_binary_and_value_ignores_it() {
    let output = run(&["github-actions:output", "r"], Some(b"a\r\r\n"));
    assert_eq!(output.status.code(), Some(1));
    assert!(output.stdout.is_empty());
    let ignored = run(&["github-actions:output", "r", "argv"], Some(b"stdin"));
    assert_eq!(ignored.status.code(), Some(0));
    assert_eq!(ignored.stdout, b"r=argv\n");
}

#[test]
fn output_and_env_name_policies_differ() {
    success(
        &["github-actions:output", "cache-hit", "yes"],
        b"cache-hit=yes\n",
    );
    for name in ["GITHUB_ENV", "runner_os", "Node_Options", "bad-name"] {
        let output = run(&["github-actions:env", name, "x"], None);
        assert_eq!(output.status.code(), Some(1));
        assert!(output.stdout.is_empty());
        assert!(!output.stderr.starts_with(b"::"));
    }
    success(
        &["github-actions:env", "NODE_OPTIONS_X", "x"],
        b"NODE_OPTIONS_X=x\n",
    );
}

#[test]
fn failures_have_empty_stdout_and_stable_statuses() {
    for (args, expected) in [
        (vec!["github-actions:output", "r", "a\nb"], 1),
        (
            vec![
                "github-actions:output",
                "--first-line",
                "--join-lines",
                "r",
                "x",
            ],
            2,
        ),
        (vec!["github-actions:output", "r", "a", "b"], 2),
        (vec!["github-actions:output", "--multiline", "r", "x"], 2),
    ] {
        let output = run(&args, None);
        assert_eq!(output.status.code(), Some(expected));
        assert!(output.stdout.is_empty());
    }
}

#[test]
fn input_limit_is_enforced() {
    let input = vec![b'a'; 1_048_577];
    let output = run(&["github-actions:output", "r"], Some(&input));
    assert_eq!(output.status.code(), Some(1));
    assert!(output.stdout.is_empty());
}

#[test]
fn validation_covers_discarded_data_and_boundaries() {
    let output = run(
        &["github-actions:output", "--first-line", "r"],
        Some(b"safe\nignored\0data"),
    );
    assert_eq!(output.status.code(), Some(1));
    assert!(output.stdout.is_empty());

    success(
        &["github-actions:output", "r", "\u{feff}value"],
        "r=\u{feff}value\n".as_bytes(),
    );
    for name in ["", "1bad", "bad=name", "é"] {
        let output = run(&["github-actions:output", name, "x"], None);
        assert_eq!(output.status.code(), Some(1));
        assert!(output.stdout.is_empty());
    }
    let long_name = "a".repeat(256);
    let output = run(&["github-actions:output", &long_name, "x"], None);
    assert_eq!(output.status.code(), Some(1));
    assert!(output.stdout.is_empty());
}

#[test]
fn expanded_join_size_is_checked_before_construction() {
    let request = WriteRequest {
        destination: Destination::Output,
        mode: LineMode::Join(vec![b'x'; 255]),
        name: OsString::from("r"),
        value: None,
    };
    let value = vec![b'\n'; 10_000];
    let error = shoutx::encode(request, value).unwrap_err();
    assert_eq!(error.class(), shoutx::ErrorClass::Failure);
}

#[test]
fn library_size_boundaries_are_exact() {
    for (size, succeeds) in [(1_048_575, true), (1_048_576, true), (1_048_577, false)] {
        let request = WriteRequest {
            destination: Destination::Output,
            mode: LineMode::Default,
            name: OsString::from("r"),
            value: None,
        };
        assert_eq!(shoutx::encode(request, vec![b'a'; size]).is_ok(), succeeds);
    }
    for (size, succeeds) in [(254, true), (255, true), (256, false)] {
        let request = WriteRequest {
            destination: Destination::Output,
            mode: LineMode::Join(vec![b'x'; size]),
            name: OsString::from("r"),
            value: None,
        };
        assert_eq!(shoutx::encode(request, b"a\nb".to_vec()).is_ok(), succeeds);
    }
}

#[cfg(windows)]
#[test]
fn windows_unpaired_surrogate_is_rejected() {
    use std::os::windows::ffi::OsStringExt;
    let invalid = OsString::from_wide(&[0xd800]);
    let output = Command::new(env!("CARGO_BIN_EXE_shoutx"))
        .arg("github-actions:output")
        .arg("r")
        .arg(invalid)
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
fn windows_ctrl_z_is_value_data() {
    let output = run(&["github-actions:output", "r"], Some(b"a\x1ab"));
    assert_eq!(output.status.code(), Some(0));
    assert_eq!(output.stdout, b"r=a\x1ab\n");
}

#[cfg(unix)]
#[test]
fn invalid_utf8_argv_is_rejected_without_echoing_it() {
    use std::os::unix::ffi::OsStringExt;
    let invalid = OsString::from_vec(vec![0xff]);
    let output = Command::new(env!("CARGO_BIN_EXE_shoutx"))
        .arg("github-actions:output")
        .arg("r")
        .arg(invalid)
        .stdin(Stdio::null())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .output()
        .unwrap();
    assert_eq!(output.status.code(), Some(1));
    assert!(output.stdout.is_empty());
    assert!(!output.stderr.contains(&0xff));
}

#[cfg(unix)]
#[test]
fn broken_pipe_is_status_one_not_signal_termination() {
    use std::os::fd::OwnedFd;
    use std::os::unix::net::UnixStream;

    let (writer, reader) = UnixStream::pair().unwrap();
    drop(reader);
    let writer: OwnedFd = writer.into();
    let output = Command::new(env!("CARGO_BIN_EXE_shoutx"))
        .args(["github-actions:output", "r", "value"])
        .stdin(Stdio::null())
        .stdout(Stdio::from(writer))
        .stderr(Stdio::piped())
        .output()
        .unwrap();
    assert_eq!(output.status.code(), Some(1));
}

#[cfg(unix)]
#[test]
fn posix_runtime_substitutes_startup_closed_descriptors() {
    let binary = env!("CARGO_BIN_EXE_shoutx");
    let input_closed = Command::new("sh")
        .args([
            "-c",
            "exec \"$1\" github-actions:output r 0<&-",
            "sh",
            binary,
        ])
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .output()
        .unwrap();
    assert_eq!(input_closed.status.code(), Some(0));
    assert_eq!(input_closed.stdout, b"r=\n");

    let output_closed = Command::new("sh")
        .args([
            "-c",
            "exec \"$1\" github-actions:output r value 1>&-",
            "sh",
            binary,
        ])
        .stderr(Stdio::piped())
        .output()
        .unwrap();
    assert_eq!(output_closed.status.code(), Some(0));
}

fn matrix_encode(
    destination: Destination,
    mode: LineMode,
    input: &[u8],
) -> Result<Vec<u8>, ShoutxError> {
    shoutx::encode(
        WriteRequest {
            destination,
            mode,
            name: OsString::from("r"),
            value: None,
        },
        input.to_vec(),
    )
}

#[test]
fn normative_line_matrix_all_modes_and_destinations() {
    type MatrixRow = (
        &'static [u8],
        Option<&'static [u8]>,
        &'static [u8],
        &'static [u8],
    );
    let rows: &[MatrixRow] = &[
        (b"", Some(b""), b"", b""),
        (b"a", Some(b"a"), b"a", b"a"),
        (b"a\n", Some(b"a"), b"a", b"a"),
        (b"a\r", Some(b"a"), b"a", b"a"),
        (b"a\r\n", Some(b"a"), b"a", b"a"),
        (b"a\n\n", None, b"a", b"a "),
        (b"a\r\n\r\n", None, b"a", b"a "),
        (b"a\r\r", None, b"a", b"a "),
        (b"a\nb\n", None, b"a", b"a b"),
        (b"a\rb\r", None, b"a", b"a b"),
        (b"a\r\nb\r\n", None, b"a", b"a b"),
        (b"\na", None, b"", b" a"),
        (b"a\n\r", None, b"a", b"a "),
        (b"a\r\n", Some(b"a"), b"a", b"a"),
    ];
    for destination in [Destination::Output, Destination::Env] {
        for (input, default, first, joined) in rows {
            match default {
                Some(expected) => {
                    let out = matrix_encode(destination, LineMode::Default, input).unwrap();
                    assert_eq!(&out[2..out.len() - 1], *expected);
                }
                None => assert!(matrix_encode(destination, LineMode::Default, input).is_err()),
            }
            let out = matrix_encode(destination, LineMode::FirstLine, input).unwrap();
            assert_eq!(&out[2..out.len() - 1], *first);
            let out = matrix_encode(destination, LineMode::Join(b" ".to_vec()), input).unwrap();
            assert_eq!(&out[2..out.len() - 1], *joined);
        }
    }
}

#[test]
fn invalid_and_multibyte_separators_are_covered() {
    for separator in [
        b"\r".to_vec(),
        b"\n".to_vec(),
        b"\0".to_vec(),
        vec![b'x'; 256],
    ] {
        assert!(matrix_encode(Destination::Output, LineMode::Join(separator), b"plain").is_err());
    }
    let out = matrix_encode(
        Destination::Output,
        LineMode::Join("・".as_bytes().to_vec()),
        b"a\nb",
    )
    .unwrap();
    assert_eq!(out, "r=a・b\n".as_bytes());
    for name in ["-bad", "has space", "bad<name"] {
        let output = run(&["github-actions:output", "--", name, "x"], None);
        assert_eq!(output.status.code(), Some(1));
        assert!(output.stdout.is_empty());
    }
}

#[cfg(unix)]
#[test]
fn failed_stderr_preserves_usage_status() {
    let output = Command::new("sh")
        .args([
            "-c",
            "exec \"$1\" --unknown 2>&-",
            "sh",
            env!("CARGO_BIN_EXE_shoutx"),
        ])
        .output()
        .unwrap();
    assert_eq!(output.status.code(), Some(2));
}
