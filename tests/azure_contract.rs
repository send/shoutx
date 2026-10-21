use shoutx::{
    azure_pipelines::{self, Variable},
    input::VALUE_LIMIT,
};
use std::{
    io::Write,
    process::{Command, Stdio},
};

fn check(command: &str, args: &[&str], input: &[u8], status: i32, expected: &[u8]) {
    let mut child = Command::new(env!("CARGO_BIN_EXE_shoutx"))
        .arg(format!("azure-pipelines:{command}"))
        .args(args)
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .unwrap();
    // Read stdout concurrently for maximum-sized inputs/outputs.
    let mut stdin = child.stdin.take().unwrap();
    let input = input.to_vec();
    let writer = std::thread::spawn(move || {
        if let Err(error) = stdin.write_all(&input) {
            assert_eq!(error.kind(), std::io::ErrorKind::BrokenPipe);
        }
    });
    let result = child.wait_with_output().unwrap();
    writer.join().unwrap();
    assert_eq!(result.status.code(), Some(status));
    assert_eq!(result.stdout, expected);
    if status == 0 {
        assert!(result.stderr.is_empty());
    } else {
        assert!(result.stderr.starts_with(b"error: "));
        assert!(!result.stderr.windows(6).any(|s| s == b"SECRET"));
        assert!(!result.stderr.windows(5).any(|s| s == b"##vso"));
    }
}

#[test]
fn exact_values_flags_and_properties() {
    check("variable", &["--output", "--read-only", "Result", "%0A;%AZP25]\r\n"],
        b"\xffSECRET", 0,
        b"##vso[task.setvariable variable=Result;isOutput=true;isReadOnly=true;]%AZP250A%3B%AZP25AZP25%5D%0D%0A\n");
    for (value, encoded) in [
        ("", ""),
        ("\r\n", "%0D%0A"),
        ("a\n\n", "a%0A%0A"),
        ("\u{301}\u{200b}日本語😀ไทย", "\u{301}\u{200b}日本語😀ไทย"),
        (
            "##vso[task.complete result=Failed;]",
            "##vso[task.complete result=Failed%3B%5D",
        ),
    ] {
        let expected = format!(
            "##vso[task.setvariable variable=Result;isOutput=false;isReadOnly=false;]{encoded}\n"
        );
        check(
            "variable",
            &["Result", value],
            b"\xffSECRET",
            0,
            expected.as_bytes(),
        );
        check(
            "variable",
            &["Result"],
            value.as_bytes(),
            0,
            expected.as_bytes(),
        );
        if !value.is_empty() {
            for severity in ["warning", "error"] {
                let expected = format!("##vso[task.logissue type={severity};]{encoded}\n");
                check(severity, &["--", value], b"", 0, expected.as_bytes());
                check(severity, &[], value.as_bytes(), 0, expected.as_bytes());
            }
        }
    }
    check("warning", &["--file", "a];type=error\n", "--line", "0001", "--column", "02", "--code", "%0A", "message"],
        b"", 0, b"##vso[task.logissue type=warning;sourcepath=a%5D%3Btype=error%0A;linenumber=1;columnnumber=2;code=%AZP250A;]message\n");
}

#[test]
fn grammar_and_source_selection() {
    for command in ["variable", "warning", "error"] {
        check(
            command,
            &["--help", "ignored"],
            b"",
            0,
            shoutx::HELP.as_bytes(),
        );
        check(
            command,
            &["--version"],
            b"",
            0,
            shoutx::version_output().as_bytes(),
        );
        check(command, &["--unknown", "SECRET"], b"", 2, b"");
    }
    check(
        "variable",
        &["--", "Result", "--help"],
        b"",
        0,
        b"##vso[task.setvariable variable=Result;isOutput=false;isReadOnly=false;]--help\n",
    );
    check(
        "warning",
        &["--", "--help"],
        b"",
        0,
        b"##vso[task.logissue type=warning;]--help\n",
    );
    check(
        "warning",
        &["--"],
        b"data",
        0,
        b"##vso[task.logissue type=warning;]data\n",
    );
    for args in [
        vec![],
        vec!["--output"],
        vec!["--output", "--output", "X"],
        vec!["--read-only", "--read-only", "X"],
        vec!["--secret", "X"],
        vec!["--output=true", "X"],
        vec!["X", "a", "b"],
    ] {
        check("variable", &args, b"", 2, b"");
    }
    for args in [
        vec!["--file"],
        vec!["--line"],
        vec!["--code"],
        vec!["--column"],
        vec!["--file", "a", "--file", "b", "m"],
        vec!["--code", "a", "--code", "b", "m"],
        vec!["--line", "1", "--line", "2", "m"],
        vec!["--column", "1", "--column", "2", "m"],
        vec!["--file=a", "m"],
        vec!["m", "--help"],
        vec!["-x"],
    ] {
        check("warning", &args, b"", 2, b"");
    }
}

#[test]
fn rejection_does_not_write_or_disclose_input() {
    for name in [
        "",
        "1name",
        "SECRET_NAME",
        "PaThThing",
        "endpointX",
        "inputX",
        "securefileX",
        "a;b",
        "a]b",
        "a=b",
        "a\nb",
        "日本語",
    ] {
        check("variable", &[name, "SECRET"], b"", 1, b"");
    }
    for command in ["variable", "warning", "error"] {
        let args = if command == "variable" {
            vec!["Result"]
        } else {
            vec![]
        };
        for value in [b"SECRET\0".as_slice(), b"SECRET\xff"] {
            check(command, &args, value, 1, b"");
        }
        check(command, &args, &vec![b'x'; VALUE_LIMIT + 1], 1, b"");
    }
    for command in ["warning", "error"] {
        check(command, &[""], b"", 1, b"");
        check(command, &[], b"", 1, b"");
        for args in [
            vec!["--file", "", "SECRET"],
            vec!["--code", "", "SECRET"],
            vec!["--line", "1", "SECRET"],
            vec!["--column", "1", "SECRET"],
            vec!["--file", "a", "--column", "1", "SECRET"],
        ] {
            check(command, &args, b"", 1, b"");
        }
        for n in [
            "0",
            "-1",
            "+1",
            "１",
            "1x",
            "2147483648",
            "9999999999",
            "00000000001",
        ] {
            check(
                command,
                &["--file", "a", "--line", n, "SECRET"],
                b"",
                1,
                b"",
            );
            check(
                command,
                &["--file", "a", "--line", "1", "--column", n, "SECRET"],
                b"",
                1,
                b"",
            );
        }
    }
}

#[test]
fn exact_limits_and_expansion() {
    for n in [254, 255] {
        let name = "N".repeat(n);
        let expected =
            format!("##vso[task.setvariable variable={name};isOutput=false;isReadOnly=false;]\n");
        check("variable", &[&name, ""], b"", 0, expected.as_bytes());
    }
    check("variable", &[&"N".repeat(256), ""], b"", 1, b"");
    for (option, key, limit) in [("--file", "sourcepath", 4096), ("--code", "code", 255)] {
        let field = "x".repeat(limit);
        let expected = format!("##vso[task.logissue type=warning;{key}={field};]m\n");
        check(
            "warning",
            &[option, &field, "m"],
            b"",
            0,
            expected.as_bytes(),
        );
        check(
            "warning",
            &[option, &"x".repeat(limit + 1), "m"],
            b"",
            1,
            b"",
        );
    }
    check(
        "error",
        &["--file", "a", "--line", "2147483647", "m"],
        b"",
        0,
        b"##vso[task.logissue type=error;sourcepath=a;linenumber=2147483647;]m\n",
    );
    let request = Variable {
        name: "N".into(),
        output: false,
        read_only: false,
        value: None,
    };
    for n in [VALUE_LIMIT - 1, VALUE_LIMIT] {
        let value = vec![b'%'; n];
        let expected = format!(
            "##vso[task.setvariable variable=N;isOutput=false;isReadOnly=false;]{}\n",
            "%AZP25".repeat(n)
        );
        assert_eq!(
            azure_pipelines::encode_variable(&request, &value).unwrap(),
            expected.as_bytes()
        );
        check("variable", &["N"], &value, 0, expected.as_bytes());
    }
    assert!(azure_pipelines::encode_variable(&request, &vec![b'x'; VALUE_LIMIT + 1]).is_err());
}

#[cfg(unix)]
#[test]
fn invalid_argv_is_not_lossily_replaced() {
    use std::{ffi::OsString, os::unix::ffi::OsStringExt};
    for command in ["azure-pipelines:variable", "azure-pipelines:warning"] {
        let mut cmd = Command::new(env!("CARGO_BIN_EXE_shoutx"));
        cmd.arg(command);
        if command.ends_with("variable") {
            cmd.arg("Result");
        }
        let result = cmd
            .arg(OsString::from_vec(b"SECRET\xff".to_vec()))
            .output()
            .unwrap();
        assert_eq!(result.status.code(), Some(1));
        assert!(result.stdout.is_empty());
        assert!(!result.stderr.windows(6).any(|s| s == b"SECRET"));
    }
}
