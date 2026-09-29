use shoutx::cli::{Destination, LineMode, WriteRequest};
use shoutx::github_actions::{RandomSource, TargetOs};
use shoutx::{ErrorClass, ShoutxError};
use std::{
    ffi::OsString,
    io::Write,
    process::{Command, Output, Stdio},
};

mod support;

use support::runner_parser::{Platform, parse as parse_runner_file};

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

fn run_with_runner_os(args: &[&str], stdin: Option<&[u8]>, runner_os: &str) -> Output {
    let mut command = Command::new(env!("CARGO_BIN_EXE_shoutx"));
    command
        .args(args)
        .env("RUNNER_OS", runner_os)
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

fn run_without_runner_os(args: &[&str], stdin: &[u8]) -> Output {
    let mut child = Command::new(env!("CARGO_BIN_EXE_shoutx"))
        .args(args)
        .env_remove("RUNNER_OS")
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .unwrap();
    if let Err(error) = child.stdin.take().unwrap().write_all(stdin) {
        assert_eq!(error.kind(), std::io::ErrorKind::BrokenPipe);
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
        assert_eq!(output.stdout, shoutx::HELP.as_bytes());
        assert!(output.stderr.is_empty());
    }
    let version = run(&["--version"], None);
    assert_eq!(version.status.code(), Some(0));
    assert_eq!(version.stdout, shoutx::version_output().as_bytes());
    assert!(version.stderr.is_empty());
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
fn configured_command_table_is_the_complete_expected_surface() {
    if let Ok(expected) = std::env::var("SHOUTX_EXPECT_SURFACE") {
        let actual = if cfg!(feature = "unstable-github-actions-stdout") {
            "unstable"
        } else {
            "stable"
        };
        assert_eq!(
            actual, expected,
            "compiled surface does not match expectation"
        );
    }
    #[cfg(not(feature = "unstable-github-actions-stdout"))]
    const EXPECTED: &[&str] = &[
        "github-actions:output",
        "github-actions:env",
        "github-actions:state",
        "github-actions:path",
    ];
    #[cfg(feature = "unstable-github-actions-stdout")]
    const EXPECTED: &[&str] = &[
        "github-actions:output",
        "github-actions:env",
        "github-actions:state",
        "github-actions:path",
        "github-actions:mask",
        "github-actions:notice",
        "github-actions:warning",
        "github-actions:error",
    ];

    assert_eq!(shoutx::cli::command_names().collect::<Vec<_>>(), EXPECTED);
}

#[cfg(not(feature = "unstable-github-actions-stdout"))]
#[test]
fn unstable_stdout_commands_are_ordinary_unknown_commands() {
    for args in [
        ["github-actions:mask", "fixed-mask-value"].as_slice(),
        ["github-actions:notice", "fixed notice"].as_slice(),
        ["github-actions:warning", "fixed warning"].as_slice(),
        ["github-actions:error", "fixed error"].as_slice(),
    ] {
        let output = run(args, None);
        assert_eq!(output.status.code(), Some(2));
        assert!(output.stdout.is_empty());
        assert_eq!(output.stderr, b"error: unknown command\n");
    }
}

#[cfg(not(feature = "unstable-github-actions-stdout"))]
#[test]
fn stable_help_and_version_are_exact() {
    assert_eq!(shoutx::HELP, include_str!("fixtures/stable-help.txt"));
    assert_eq!(
        shoutx::version_output(),
        format!("shoutx {}\n", shoutx::VERSION)
    );
}

#[cfg(feature = "unstable-github-actions-stdout")]
#[test]
fn unstable_feature_identity_is_explicit() {
    assert!(shoutx::HELP.contains("Unstable GitHub Actions stdout research commands:"));
    assert_eq!(
        shoutx::version_output(),
        format!(
            "shoutx {} (unstable-github-actions-stdout)\n",
            shoutx::VERSION
        )
    );
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
fn state_name_policy_uses_portable_grammar_without_env_reservations() {
    for name in ["a", "_", "A0", "GITHUB_ENV", "RUNNER_OS", "NODE_OPTIONS"] {
        success(
            &["github-actions:state", name, "x"],
            format!("{name}=x\n").as_bytes(),
        );
    }
    let max_name = format!("a{}", "b".repeat(254));
    success(
        &["github-actions:state", &max_name, "x"],
        format!("{max_name}=x\n").as_bytes(),
    );
    let too_long = format!("a{}", "b".repeat(255));
    for name in [
        "",
        "1bad",
        "-bad",
        "has space",
        "bad-name",
        "bad=name",
        "bad<name",
        "bad\rname",
        "bad\nname",
        "é",
        &too_long,
    ] {
        let output = run(&["github-actions:state", "--", name, "x"], None);
        assert_eq!(output.status.code(), Some(1), "{name:?}");
        assert!(output.stdout.is_empty(), "{name:?}");
    }
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
        (
            vec![
                "github-actions:output",
                "--multiline",
                "--first-line",
                "r",
                "x",
            ],
            2,
        ),
        (vec!["github-actions:output", "r", "a", "b"], 2),
    ] {
        let output = run(&args, None);
        assert_eq!(output.status.code(), Some(expected));
        assert!(output.stdout.is_empty());
    }
}

#[derive(Default)]
struct DeterministicRandom {
    bytes: Vec<[u8; 16]>,
    offset: usize,
    fail: bool,
}

impl RandomSource for DeterministicRandom {
    fn fill(&mut self, destination: &mut [u8]) -> Result<(), ShoutxError> {
        if self.fail {
            return Err(ShoutxError::failure("test randomness failure"));
        }
        let bytes = self
            .bytes
            .get(self.offset)
            .copied()
            .unwrap_or([self.offset as u8; 16]);
        self.offset += 1;
        destination.copy_from_slice(&bytes);
        Ok(())
    }
}

fn multiline_request(destination: Destination, name: &str) -> WriteRequest {
    WriteRequest {
        destination,
        mode: LineMode::Multiline,
        name: OsString::from(name),
        value: None,
    }
}

#[test]
fn multiline_round_trips_exact_values_and_is_appendable() {
    let values: &[&[u8]] = &[
        b"",
        b"plain",
        b"a\nb",
        b"a\r\nb\rc\n",
        b"\n\r\n\r",
        "雪\u{2028}x".as_bytes(),
        b"\xef\xbb\xbfvalue",
        b"::stop-commands::TOKEN\nname=value",
    ];
    for destination in [Destination::Output, Destination::Env, Destination::State] {
        for (target, platform) in [
            (TargetOs::Linux, Platform::Posix),
            (TargetOs::MacOs, Platform::Posix),
            (TargetOs::Windows, Platform::Windows),
        ] {
            for value in values {
                let mut random = DeterministicRandom::default();
                let mut record = shoutx::github_actions::encode_with(
                    multiline_request(destination, "result"),
                    value.to_vec(),
                    target,
                    &mut random,
                )
                .unwrap();
                let header_end = record.iter().position(|byte| *byte == b'\n').unwrap();
                let delimiter = &record[b"result<<".len()..header_end];
                assert_eq!(delimiter.len(), 39);
                assert!(delimiter.starts_with(b"SHOUTX_"));
                assert!(
                    delimiter[7..]
                        .iter()
                        .all(|byte| matches!(byte, b'0'..=b'9' | b'a'..=b'f'))
                );
                assert!(!value.windows(delimiter.len()).any(|part| part == delimiter));
                assert_eq!(
                    parse_runner_file(&record, platform).unwrap(),
                    vec![(b"result".to_vec(), value.to_vec())]
                );
                record.extend_from_slice(b"next=ok\n");
                assert_eq!(
                    parse_runner_file(&record, platform).unwrap(),
                    vec![
                        (b"result".to_vec(), value.to_vec()),
                        (b"next".to_vec(), b"ok".to_vec()),
                    ]
                );
            }
        }
    }
}

#[test]
fn multiline_retries_collisions_and_bounds_failures() {
    let zero_delimiter = b"SHOUTX_00000000000000000000000000000000";
    let mut random = DeterministicRandom {
        bytes: vec![[0; 16], [1; 16]],
        ..DeterministicRandom::default()
    };
    let record = shoutx::github_actions::encode_with(
        multiline_request(Destination::Output, "r"),
        zero_delimiter.to_vec(),
        TargetOs::Linux,
        &mut random,
    )
    .unwrap();
    assert!(record.starts_with(b"r<<SHOUTX_01010101010101010101010101010101\n"));
    assert_eq!(random.offset, 2);

    let mut exhausted = DeterministicRandom {
        bytes: vec![[0; 16]; 128],
        ..DeterministicRandom::default()
    };
    let error = shoutx::github_actions::encode_with(
        multiline_request(Destination::Output, "r"),
        zero_delimiter.to_vec(),
        TargetOs::Linux,
        &mut exhausted,
    )
    .unwrap_err();
    assert_eq!(error.class(), ErrorClass::Failure);
    assert_eq!(exhausted.offset, 128);

    let mut failed = DeterministicRandom {
        fail: true,
        ..DeterministicRandom::default()
    };
    let error = shoutx::github_actions::encode_with(
        multiline_request(Destination::Output, "r"),
        b"value".to_vec(),
        TargetOs::Linux,
        &mut failed,
    )
    .unwrap_err();
    assert_eq!(error.class(), ErrorClass::Failure);
}

#[test]
fn multiline_target_os_only_matters_for_trailing_bare_cr() {
    let mut random = DeterministicRandom::default();
    let error = shoutx::github_actions::encode_with(
        multiline_request(Destination::Output, "r"),
        b"value\r".to_vec(),
        TargetOs::Unknown,
        &mut random,
    )
    .unwrap_err();
    assert_eq!(error.class(), ErrorClass::Failure);
    let record = shoutx::github_actions::encode_with(
        multiline_request(Destination::Output, "r"),
        b"value".to_vec(),
        TargetOs::Unknown,
        &mut random,
    )
    .unwrap();
    assert_eq!(
        parse_runner_file(&record, Platform::Posix).unwrap()[0].1,
        b"value"
    );
}

#[test]
fn executable_multiline_uses_trusted_runner_os() {
    let windows = run_with_runner_os(
        &["github-actions:output", "--multiline", "r"],
        Some(b"value\r"),
        "Windows",
    );
    assert_eq!(windows.status.code(), Some(0));
    assert!(windows.stderr.is_empty());
    assert_eq!(
        parse_runner_file(&windows.stdout, Platform::Windows).unwrap(),
        vec![(b"r".to_vec(), b"value\r".to_vec())]
    );

    let unknown = run_with_runner_os(
        &["github-actions:output", "--multiline", "r"],
        Some(b"value\r"),
        "Other",
    );
    assert_eq!(unknown.status.code(), Some(1));
    assert!(unknown.stdout.is_empty());

    let irrelevant = run_with_runner_os(
        &["github-actions:output", "--multiline", "r", "value"],
        None,
        "Other",
    );
    assert_eq!(irrelevant.status.code(), Some(0));
    assert_eq!(
        parse_runner_file(&irrelevant.stdout, Platform::Posix).unwrap(),
        vec![(b"r".to_vec(), b"value".to_vec())]
    );

    let native = run_without_runner_os(&["github-actions:output", "--multiline", "r"], b"value\r");
    assert_eq!(native.status.code(), Some(0));
    let platform = if cfg!(windows) {
        Platform::Windows
    } else {
        Platform::Posix
    };
    assert_eq!(
        parse_runner_file(&native.stdout, platform).unwrap(),
        vec![(b"r".to_vec(), b"value\r".to_vec())]
    );
}

#[test]
fn runner_parser_model_covers_platform_and_error_edges() {
    assert_eq!(
        parse_runner_file(b"a=1\nb<<X\r\nline\r\nX\r\n", Platform::Windows).unwrap(),
        vec![
            (b"a".to_vec(), b"1".to_vec()),
            (b"b".to_vec(), b"line".to_vec()),
        ]
    );
    assert_eq!(
        parse_runner_file(b"a<<X\nX", Platform::Posix).unwrap(),
        vec![(b"a".to_vec(), Vec::new())]
    );
    assert_eq!(
        parse_runner_file(b"a=b<<c\n", Platform::Posix).unwrap(),
        vec![(b"a".to_vec(), b"b<<c".to_vec())]
    );
    assert_eq!(
        parse_runner_file(b"a<<b=c\nvalue\nb=c\n", Platform::Posix).unwrap(),
        vec![(b"a".to_vec(), b"value".to_vec())]
    );
    assert_eq!(
        parse_runner_file(b"a<<X\r\nv\r\r\nX\n", Platform::Windows).unwrap(),
        vec![(b"a".to_vec(), b"v\r".to_vec())]
    );
    assert_eq!(
        parse_runner_file(b"a<<X\r\nv\r\nX\r\n", Platform::Posix).unwrap(),
        vec![(b"a".to_vec(), b"v\r".to_vec())]
    );
    for malformed in [
        b"invalid\n".as_slice(),
        b"a<<\n".as_slice(),
        b"a<<X\nvalue".as_slice(),
        b"a<<X\nvalue\n".as_slice(),
        b"a<<X\nv\nX\nrest\n".as_slice(),
    ] {
        assert!(parse_runner_file(malformed, Platform::Posix).is_err());
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
fn windows_unpaired_surrogate_equals_separator_is_input_failure() {
    use std::os::windows::ffi::OsStringExt;
    let mut option: Vec<u16> = "--join-lines-with=".encode_utf16().collect();
    option.push(0xd800);
    let output = Command::new(env!("CARGO_BIN_EXE_shoutx"))
        .arg("github-actions:output")
        .arg(OsString::from_wide(&option))
        .arg("r")
        .arg("value")
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
fn windows_invalid_option_data_preserves_usage_precedence() {
    use std::os::windows::ffi::OsStringExt;

    let invalid = OsString::from_wide(&[0xd800]);
    for args in [
        vec![OsString::from("--join-lines-with"), invalid.clone()],
        vec![
            OsString::from("--join-lines-with"),
            invalid.clone(),
            OsString::from("r"),
            OsString::from("a"),
            OsString::from("b"),
        ],
        vec![
            OsString::from_wide(&[u16::from(b'-'), 0xd800]),
            OsString::from("r"),
        ],
    ] {
        let output = Command::new(env!("CARGO_BIN_EXE_shoutx"))
            .arg("github-actions:output")
            .args(args)
            .stdin(Stdio::null())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .output()
            .unwrap();
        assert_eq!(output.status.code(), Some(2));
        assert!(output.stdout.is_empty());
    }
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
fn invalid_utf8_equals_separator_is_input_failure() {
    use std::os::unix::ffi::OsStringExt;
    let mut option = b"--join-lines-with=".to_vec();
    option.push(0xff);
    let output = Command::new(env!("CARGO_BIN_EXE_shoutx"))
        .arg("github-actions:output")
        .arg(OsString::from_vec(option))
        .arg("r")
        .arg("value")
        .stdin(Stdio::null())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .output()
        .unwrap();
    assert_eq!(output.status.code(), Some(1));
    assert!(output.stdout.is_empty());
}

#[cfg(unix)]
#[test]
fn invalid_utf8_option_data_preserves_usage_precedence() {
    use std::os::unix::ffi::OsStringExt;

    let invalid = OsString::from_vec(vec![0xff]);
    for args in [
        vec![OsString::from("--join-lines-with"), invalid.clone()],
        vec![
            OsString::from("--join-lines-with"),
            invalid.clone(),
            OsString::from("r"),
            OsString::from("a"),
            OsString::from("b"),
        ],
        vec![OsString::from_vec(vec![b'-', 0xff]), OsString::from("r")],
    ] {
        let output = Command::new(env!("CARGO_BIN_EXE_shoutx"))
            .arg("github-actions:output")
            .args(args)
            .stdin(Stdio::null())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .output()
            .unwrap();
        assert_eq!(output.status.code(), Some(2));
        assert!(output.stdout.is_empty());
    }
}

#[cfg(unix)]
#[test]
fn broken_pipe_is_status_one_not_signal_termination() {
    use std::os::fd::OwnedFd;
    use std::{net::Shutdown, os::unix::net::UnixStream};

    let (writer, reader) = UnixStream::pair().unwrap();
    reader.shutdown(Shutdown::Both).unwrap();
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
    for destination in [Destination::Output, Destination::Env, Destination::State] {
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
    use std::os::fd::OwnedFd;
    use std::{net::Shutdown, os::unix::net::UnixStream};
    let (writer, reader) = UnixStream::pair().unwrap();
    reader.shutdown(Shutdown::Both).unwrap();
    drop(reader);
    let writer: OwnedFd = writer.into();
    let output = Command::new(env!("CARGO_BIN_EXE_shoutx"))
        .arg("--unknown")
        .stdin(Stdio::null())
        .stdout(Stdio::piped())
        .stderr(Stdio::from(writer))
        .output()
        .unwrap();
    assert_eq!(output.status.code(), Some(2));
}
