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
fn formatter_values_preserve_text_in_the_selected_wire() {
    for (value, debug) in [
        ("hello", "hello"),
        ("日本語ไทยالعربية😀e\u{301}", "日本語ไทยالعربية😀e\u{301}"),
        (" \t x ", " \t x "),
        ("%0A;%AZP25]", "%AZP250A%3B%AZP25AZP25%5D"),
        ("--help", "--help"),
    ] {
        for (command, expected) in [
            ("debug", format!("##vso[task.debug]{debug}\n")),
            ("group", format!("##[group]{value}\n")),
        ] {
            check(command, &["--", value], b"ignored", 0, expected.as_bytes());
            check(command, &[], value.as_bytes(), 0, expected.as_bytes());
        }
    }
    check("debug", &[""], b"ignored", 0, b"##vso[task.debug]\n");
    check("debug", &[], b"", 0, b"##vso[task.debug]\n");
    check("group", &[""], b"ignored", 1, b"");
    check("group", &[], b"", 1, b"");
    // Prefix reservations are exact byte sequences, not case folding.
    check("group", &["##VSO"], b"", 0, b"##[group]##VSO\n");
    check("debug", &["##vso"], b"", 0, b"##vso[task.debug]##vso\n");
}

#[test]
fn formatter_rejections_have_no_stdout() {
    for command in ["debug", "group"] {
        for reserved in [b"\r".as_slice(), b"\n", b"\r\n", b"##[", b"\0", b"\xff"] {
            for (prefix, suffix) in [
                (b"".as_slice(), b"SECRET".as_slice()),
                (b"SECRET", b"tail"),
                (b"SECRET", b""),
            ] {
                let input = [prefix, reserved, suffix].concat();
                check(command, &[], &input, 1, b"");
            }
        }
        for args in [
            vec!["--raw"],
            vec!["one", "two"],
            vec!["--multiline"],
            vec!["--file", "x"],
        ] {
            check(command, &args, b"SECRET", 2, b"");
        }
        check(command, &["--help"], b"SECRET", 0, shoutx::HELP.as_bytes());
        check(
            command,
            &["--version"],
            b"SECRET",
            0,
            shoutx::version_output().as_bytes(),
        );
        check(command, &[], &vec![b'x'; VALUE_LIMIT + 1], 1, b"");
    }
    for value in ["##vso", "##vsotail", "prefix##vso", "prefix##vsotail"] {
        check("group", &[value], b"", 1, b"");
    }
}

#[test]
fn formatter_limits_include_worst_case_encoding() {
    let value = vec![b'%'; VALUE_LIMIT];
    let mut expected = b"##vso[task.debug]".to_vec();
    expected.extend_from_slice("%AZP25".repeat(VALUE_LIMIT).as_bytes());
    expected.push(b'\n');
    check("debug", &[], &value, 0, &expected);
    let mut expected = b"##[group]".to_vec();
    expected.extend_from_slice(&value);
    expected.push(b'\n');
    check("group", &[], &value, 0, &expected);
}

#[test]
fn azure_endgroup_does_not_acquire_stdin() {
    for args in [vec![], vec!["--"]] {
        let mut child = Command::new(env!("CARGO_BIN_EXE_shoutx"))
            .arg("azure-pipelines:endgroup")
            .args(args)
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .spawn()
            .unwrap();
        let stdin = child.stdin.take().unwrap(); // Keep the pipe open without delivering EOF.
        let deadline = std::time::Instant::now() + std::time::Duration::from_secs(5);
        while child.try_wait().unwrap().is_none() {
            if std::time::Instant::now() >= deadline {
                child.kill().unwrap();
                child.wait().unwrap();
                panic!("endgroup waited for stdin");
            }
            std::thread::sleep(std::time::Duration::from_millis(10));
        }
        drop(stdin);
        let out = child.wait_with_output().unwrap();
        assert!(out.status.success());
        assert_eq!(out.stdout, b"##[endgroup]\n");
        assert!(out.stderr.is_empty());
    }
    for args in [vec![""], vec!["x"], vec!["--raw"], vec!["--", "x"]] {
        check("endgroup", &args, b"", 2, b"");
    }
}

#[test]
fn secret_variable_stdin_wire_and_rejection() {
    for (flags, output, read_only) in [
        (vec![], false, false),
        (vec!["--output"], true, false),
        (vec!["--read-only"], false, true),
        (vec!["--output", "--read-only"], true, true),
    ] {
        let mut args = flags;
        args.push("Credential");
        for value in [
            "x",
            "😀日本語ไทย",
            " \t ",
            "a%0A;]%AZP25",
            "$x(y))$",
            "##vso[task.complete]inert",
        ] {
            let escaped = value
                .replace('%', "%AZP25")
                .replace(';', "%3B")
                .replace(']', "%5D");
            let expected = format!(
                "##vso[task.setsecret]{escaped}\n##vso[task.setsecret]{}\n##vso[task.setvariable variable=Credential;isSecret=true;isOutput={output};isReadOnly={read_only};]{escaped}\n",
                escaped.replace('%', "%AZP25")
            );
            check(
                "secret-variable",
                &args,
                value.as_bytes(),
                0,
                expected.as_bytes(),
            );
        }
    }
    for value in [
        b"".as_slice(),
        b"SECRET\n",
        b"SECRET\r",
        b"SECRET\0",
        b"SECRET\xff",
        b"a$(",
        b"$(x)tail",
    ] {
        check("secret-variable", &["Credential"], value, 1, b"");
    }
    for args in [
        vec![],
        vec!["Credential", "SECRET"],
        vec!["--each-line", "Credential"],
        vec!["--output", "--output", "Credential"],
    ] {
        check("secret-variable", &args, b"SECRET", 2, b"");
    }
    check("secret-variable", &["secretName"], b"SECRET", 1, b"");
    let value = "x".repeat(16 * 1024);
    let expected = format!(
        "##vso[task.setsecret]{value}\n##vso[task.setsecret]{value}\n##vso[task.setvariable variable=Credential;isSecret=true;isOutput=false;isReadOnly=false;]{value}\n"
    );
    check(
        "secret-variable",
        &["Credential"],
        value.as_bytes(),
        0,
        expected.as_bytes(),
    );
    check(
        "secret-variable",
        &["Credential"],
        "x".repeat(16 * 1024 + 1).as_bytes(),
        1,
        b"",
    );
}

#[test]
fn secret_variable_maximum_escape_expansion_is_three_complete_records() {
    let value = "%".repeat(16 * 1024);
    let wire = "%AZP25".repeat(16 * 1024);
    let double_wire = "%AZP25AZP25".repeat(16 * 1024);
    let expected = format!(
        "##vso[task.setsecret]{wire}\n##vso[task.setsecret]{double_wire}\n##vso[task.setvariable variable=Credential;isSecret=true;isOutput=false;isReadOnly=false;]{wire}\n"
    );
    check(
        "secret-variable",
        &["Credential"],
        value.as_bytes(),
        0,
        expected.as_bytes(),
    );
}

#[test]
fn secret_variable_validation_order_and_fixed_diagnostics() {
    let cases = [
        (
            b"SECRET\xff\0\n$(".to_vec(),
            "Azure field is not valid UTF-8",
        ),
        (b"SECRET\0\n$(".to_vec(), "Azure field contains NUL"),
        (
            [vec![b'x'; 16 * 1024], b"\n$(".to_vec()].concat(),
            "Azure secret value exceeds size limit",
        ),
        (Vec::new(), "Azure secret value must not be empty"),
        (
            b"SECRET\r\n$(".to_vec(),
            "Azure secret value contains a line boundary",
        ),
        (
            b"SECRET$(".to_vec(),
            "Azure secret value contains variable syntax",
        ),
        (
            vec![b'x'; VALUE_LIMIT],
            "Azure secret value exceeds size limit",
        ),
        (vec![b'x'; VALUE_LIMIT + 1], "value exceeds size limit"),
    ];
    for (input, message) in cases {
        let mut child = Command::new(env!("CARGO_BIN_EXE_shoutx"))
            .args(["azure-pipelines:secret-variable", "Credential"])
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .spawn()
            .unwrap();
        let mut stdin = child.stdin.take().unwrap();
        let writer = std::thread::spawn(move || {
            if let Err(error) = stdin.write_all(&input) {
                assert_eq!(error.kind(), std::io::ErrorKind::BrokenPipe);
            }
        });
        let result = child.wait_with_output().unwrap();
        writer.join().unwrap();
        assert_eq!(result.status.code(), Some(1));
        assert!(result.stdout.is_empty());
        assert_eq!(result.stderr, format!("error: {message}\n").as_bytes());
    }
    check("secret-variable", &["--", "Credential"], b"$x(y)", 0,
        b"##vso[task.setsecret]$x(y)\n##vso[task.setsecret]$x(y)\n##vso[task.setvariable variable=Credential;isSecret=true;isOutput=false;isReadOnly=false;]$x(y)\n");
    for args in [
        vec!["Credential", "--help"],
        vec!["--read-only", "--read-only", "Credential"],
        vec!["Credential", "SECRET", "extra"],
    ] {
        check("secret-variable", &args, b"SECRET\xff", 2, b"");
    }
    let value = "😀".repeat(4096);
    let expected = format!(
        "##vso[task.setsecret]{value}\n##vso[task.setsecret]{value}\n##vso[task.setvariable variable=Credential;isSecret=true;isOutput=false;isReadOnly=false;]{value}\n"
    );
    check(
        "secret-variable",
        &["Credential"],
        value.as_bytes(),
        0,
        expected.as_bytes(),
    );
    check(
        "secret-variable",
        &["Credential"],
        format!("{value}x").as_bytes(),
        1,
        b"",
    );
}

#[cfg(any(unix, windows))]
#[test]
fn secret_variable_invalid_os_operands_keep_error_classification() {
    use std::ffi::OsString;
    #[cfg(unix)]
    let invalid = {
        use std::os::unix::ffi::OsStringExt;
        OsString::from_vec(b"SECRET\xff".to_vec())
    };
    #[cfg(windows)]
    let invalid = {
        use std::os::windows::ffi::OsStringExt;
        OsString::from_wide(&[0x53, 0xd800])
    };
    for (args, status) in [
        (vec![invalid.clone()], 1),
        (vec![OsString::from("Credential"), invalid], 2),
    ] {
        let result = Command::new(env!("CARGO_BIN_EXE_shoutx"))
            .arg("azure-pipelines:secret-variable")
            .args(args)
            .stdin(Stdio::null())
            .output()
            .unwrap();
        assert_eq!(result.status.code(), Some(status));
        assert!(result.stdout.is_empty());
        if status == 2 {
            assert_eq!(result.stderr, b"error: secret variable takes stdin only\n");
        } else {
            assert!(result.stderr.starts_with(b"error: "));
            assert!(!result.stderr.windows(6).any(|s| s == b"SECRET"));
        }
    }
}

#[test]
fn build_metadata_exact_bytes_and_rejections() {
    check(
        "build-number",
        &[" v1 interior "],
        b"",
        0,
        b"##vso[build.updatebuildnumber] v1 interior \n",
    );
    for (command, wire) in [
        ("build-number", "updatebuildnumber"),
        ("build-tag", "addbuildtag"),
    ] {
        for value in [
            "v1.2.3",
            "日本語😀ไทย",
            "\u{301}α",
            "literal%0A%AZP25;]",
            "-label",
        ] {
            let data = value
                .replace('%', "%AZP25")
                .replace(';', "%3B")
                .replace(']', "%5D");
            let expected = format!("##vso[build.{wire}]{data}\n");
            check(command, &["--", value], b"ignored", 0, expected.as_bytes());
            check(command, &[], value.as_bytes(), 0, expected.as_bytes());
        }
        for value in [
            "",
            "SECRET\n",
            "SECRET\r",
            "SECRET\r\n",
            "x\nSECRET",
            "x\tSECRET",
            "x\u{7f}SECRET",
            "x\u{85}SECRET",
        ] {
            check(command, &["--", value], b"", 1, b"");
            check(command, &[], value.as_bytes(), 1, b"");
        }
        for input in [&b"SECRET\0"[..], &b"SECRET\xff"[..]] {
            check(command, &[], input, 1, b"");
        }
        for code in (0..=0x1f).chain(0x7f..=0x9f) {
            let value = format!("x{}SECRET", char::from_u32(code).unwrap());
            check(command, &[], value.as_bytes(), 1, b"");
            if code != 0 {
                check(command, &["--", &value], b"", 1, b"");
            }
        }
        for args in [
            &["--unknown"][..],
            &["x", "y"][..],
            &["--first-line", "x"][..],
        ] {
            check(command, args, b"", 2, b"");
        }
        for value in ["x".repeat(255), format!("{}x", "😀".repeat(127))] {
            check(
                command,
                &[],
                value.as_bytes(),
                0,
                format!("##vso[build.{wire}]{value}\n").as_bytes(),
            );
        }
        for value in [
            "x".repeat(256),
            "😀".repeat(128),
            "x".repeat(VALUE_LIMIT + 1),
        ] {
            check(command, &[], value.as_bytes(), 1, b"");
        }
    }
    for character in ['"', '/', '\\', ':', '<', '>', '\'', '|', '?', '@', '*'] {
        check(
            "build-number",
            &[],
            format!("SECRET{character}x").as_bytes(),
            1,
            b"",
        );
    }
    check("build-number", &["SECRET."], b"", 1, b"");
    check("build-tag", &["SECRET:x"], b"", 1, b"");
    for scalar in [
        ' ', '\u{a0}', '\u{1680}', '\u{2000}', '\u{200a}', '\u{2028}', '\u{2029}', '\u{202f}',
        '\u{205f}', '\u{3000}',
    ] {
        for value in [format!("{scalar}SECRET"), format!("SECRET{scalar}")] {
            check("build-tag", &[], value.as_bytes(), 1, b"");
        }
        let value = format!("x{scalar}y");
        check(
            "build-tag",
            &[],
            value.as_bytes(),
            0,
            format!("##vso[build.addbuildtag]{value}\n").as_bytes(),
        );
    }
    check(
        "build-tag",
        &["--", "x/\\@?*,#y"],
        b"",
        0,
        b"##vso[build.addbuildtag]x/\\@?*,#y\n",
    );
}

#[test]
fn mask_exact_values_and_line_selection() {
    for value in [" ", "\t", "\u{feff}日本語😀ไทย", "header", "a"] {
        let expected = format!("##vso[task.setsecret]{value}\n");
        for args in [
            &[][..],
            &["--"][..],
            &["--each-line"][..],
            &["--each-line", "--"][..],
        ] {
            check("mask", args, value.as_bytes(), 0, expected.as_bytes());
        }
    }
    for n in 1..=7 {
        for scalar in ["x", "😀"] {
            let value = scalar.repeat(n);
            check(
                "mask",
                &[],
                value.as_bytes(),
                0,
                format!("##vso[task.setsecret]{value}\n").as_bytes(),
            );
        }
    }
    check(
        "mask",
        &[],
        b"%0A;%AZP25]##vso[task.complete]",
        0,
        b"##vso[task.setsecret]%AZP250A%3B%AZP25AZP25%5D##vso[task.complete%5D\n",
    );
    check("mask", &["--each-line"], b"\r\na\r\n\r\nb\rc\n \n\t\na\n", 0,
        b"##vso[task.setsecret]a\n##vso[task.setsecret]b\n##vso[task.setsecret]c\n##vso[task.setsecret] \n##vso[task.setsecret]\t\n##vso[task.setsecret]a\n");
}

#[test]
fn mask_rejection_is_batch_wide_and_value_free() {
    for input in [
        &b""[..],
        b"SECRET\0",
        b"SECRET\xff",
        b"SECRET\r",
        b"SECRET\n",
        b"SECRET\r\n",
        b"SE\nCRET",
    ] {
        check("mask", &[], input, 1, b"");
    }
    for input in [
        &b""[..],
        b"\r\n\n\r",
        b"valid\nSECRET\0",
        b"valid\nSECRET\xff",
    ] {
        check("mask", &["--each-line"], input, 1, b"");
    }
    for args in [
        vec!["SECRET"],
        vec!["--", "SECRET"],
        vec!["--", "--each-line"],
        vec!["--each-line", "--each-line"],
        vec!["--each-line=true"],
        vec!["--secret"],
        vec!["--output"],
    ] {
        check("mask", &args, b"\xffSECRET", 2, b"");
    }
}

#[test]
fn mask_raw_and_entry_limits_are_inclusive() {
    let raw = vec![b'%'; 1_048_576];
    let expected = format!("##vso[task.setsecret]{}\n", "%AZP25".repeat(1_048_576));
    for args in [&[][..], &["--each-line"][..]] {
        check("mask", args, &raw, 0, expected.as_bytes());
        check("mask", args, &vec![b'x'; 1_048_577], 1, b"");
    }
    check(
        "mask",
        &["--each-line"],
        "x\r\n\n".repeat(1024).as_bytes(),
        0,
        "##vso[task.setsecret]x\n".repeat(1024).as_bytes(),
    );
    check(
        "mask",
        &["--each-line"],
        "x\n".repeat(1025).as_bytes(),
        1,
        b"",
    );
    let mut late_invalid = "x\n".repeat(1024).into_bytes();
    late_invalid.push(0xff);
    check("mask", &["--each-line"], &late_invalid, 1, b"");
}

#[test]
fn mask_validation_precedence_and_immediate_help() {
    for (input, expected) in [
        (&b"valid\n\0\xff"[..], "Azure field is not valid UTF-8"),
        (&b"valid\n\0"[..], "Azure field contains NUL"),
        (&b"valid\n"[..], "Azure mask contains a line boundary"),
    ] {
        let error = azure_pipelines::encode_mask(input, false).unwrap_err();
        assert_eq!(error.message(), expected);
    }
    for args in [
        vec!["--help", "SECRET"],
        vec!["--each-line", "--help", "--each-line"],
    ] {
        check("mask", &args, b"\xffSECRET", 0, shoutx::HELP.as_bytes());
    }
    check(
        "mask",
        &["--version", "SECRET"],
        b"\xffSECRET",
        0,
        shoutx::version_output().as_bytes(),
    );
    check("mask", &["--", "--help"], b"", 2, b"");
    check(
        "mask",
        &["--each-line", "--each-line", "--help"],
        b"",
        2,
        b"",
    );
}

#[test]
fn mask_combined_failures_choose_fixed_diagnostics_before_output() {
    let mut over_raw = vec![b'x'; 1_048_576];
    over_raw.push(0xff);
    let mut over_count_utf8 = b"x\n".repeat(1025);
    over_count_utf8.push(0xff);
    let mut over_count_nul = b"x\n".repeat(1025);
    over_count_nul.push(0);
    for (input, diagnostic) in [
        (over_raw, "error: value exceeds size limit\n"),
        (over_count_utf8, "error: Azure field is not valid UTF-8\n"),
        (over_count_nul, "error: Azure field contains NUL\n"),
        (
            b"x\n".repeat(1025),
            "error: Azure mask exceeds entry limit\n",
        ),
    ] {
        let mut child = Command::new(env!("CARGO_BIN_EXE_shoutx"))
            .args(["azure-pipelines:mask", "--each-line"])
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .spawn()
            .unwrap();
        let mut stdin = child.stdin.take().unwrap();
        let writer = std::thread::spawn(move || {
            if let Err(error) = stdin.write_all(&input) {
                assert_eq!(error.kind(), std::io::ErrorKind::BrokenPipe);
            }
        });
        let result = child.wait_with_output().unwrap();
        writer.join().unwrap();
        assert_eq!(result.status.code(), Some(1));
        assert!(result.stdout.is_empty());
        assert_eq!(result.stderr, diagnostic.as_bytes());
    }
    // A final boundary counts toward the raw ceiling, not toward entry count.
    let mut at_cap = vec![b'x'; 1_048_575];
    at_cap.push(b'\n');
    let expected = format!("##vso[task.setsecret]{}\n", "x".repeat(1_048_575));
    check("mask", &["--each-line"], &at_cap, 0, expected.as_bytes());
    check("mask", &[], &at_cap, 1, b"");
    at_cap.push(b'\n');
    check("mask", &["--each-line"], &at_cap, 1, b"");
}

#[cfg(windows)]
#[test]
fn mask_rejects_unpaired_surrogate_argv_as_usage() {
    use std::os::windows::ffi::OsStringExt;
    let output = Command::new(env!("CARGO_BIN_EXE_shoutx"))
        .arg("azure-pipelines:mask")
        .arg(std::ffi::OsString::from_wide(&[0xd800]))
        .stdin(Stdio::null())
        .output()
        .unwrap();
    assert_eq!(output.status.code(), Some(2));
    assert!(output.stdout.is_empty());
    assert_eq!(output.stderr, b"error: invalid Azure mask argument\n");
}

#[cfg(unix)]
#[test]
fn mask_rejects_non_utf8_argv_as_usage_without_disclosure() {
    use std::os::unix::ffi::OsStringExt;
    let output = Command::new(env!("CARGO_BIN_EXE_shoutx"))
        .arg("azure-pipelines:mask")
        .arg(std::ffi::OsString::from_vec(b"SECRET\xff".to_vec()))
        .stdin(Stdio::null())
        .output()
        .unwrap();
    assert_eq!(output.status.code(), Some(2));
    assert!(output.stdout.is_empty());
    assert_eq!(output.stderr, b"error: invalid Azure mask argument\n");
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
    for command in ["variable", "secret-variable", "warning", "error"] {
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
    for command in [
        "azure-pipelines:variable",
        "azure-pipelines:warning",
        "azure-pipelines:path",
    ] {
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

#[test]
fn path_native_bytes_and_rejections() {
    let root = if cfg!(windows) { "C:\\" } else { "/" };
    for tail in [
        "tools",
        "α日本語😀ไทย\u{301}\u{200b}",
        "%0A%AZP25]",
        " space ",
    ] {
        let path = format!("{root}{tail}");
        let expected = format!(
            "##vso[task.prependpath]{}\n",
            path.replace('%', "%AZP25").replace(']', "%5D")
        );
        check("path", &[&path], b"ignored\xff", 0, expected.as_bytes());
        check("path", &[], path.as_bytes(), 0, expected.as_bytes());
        check("path", &["--", &path], b"", 0, expected.as_bytes());
    }
    for data in [
        b"".as_slice(),
        b"relative",
        b"SECRET\xff",
        b"/SECRET\0",
        b"/SECRET\n##vso[task.complete]x",
        b"/SECRET\r",
        b"/SECRET\n",
        b"/SECRET\r\n",
    ] {
        check("path", &[], data, 1, b"");
    }
    let separator = if cfg!(windows) { ';' } else { ':' };
    check(
        "path",
        &[&format!("{root}first{separator}{root}second")],
        b"",
        1,
        b"",
    );
    for args in [vec!["--unknown"], vec!["--multiline"], vec![root, root]] {
        check("path", &args, b"", 2, b"");
    }
    check("path", &["--help"], b"", 0, shoutx::HELP.as_bytes());
    check(
        "path",
        &["--version"],
        b"",
        0,
        shoutx::version_output().as_bytes(),
    );
    let value = format!("{root}{}", "%".repeat(VALUE_LIMIT - root.len()));
    let expected = format!(
        "##vso[task.prependpath]{root}{}\n",
        "%AZP25".repeat(VALUE_LIMIT - root.len())
    );
    check("path", &[], value.as_bytes(), 0, expected.as_bytes());
    check("path", &[], format!("{value}x").as_bytes(), 1, b"");
    for selector in ["Windows", "Linux", "invalid", ""] {
        let result = Command::new(env!("CARGO_BIN_EXE_shoutx"))
            .args(["azure-pipelines:path", root])
            .env("RUNNER_OS", selector)
            .env("AGENT_OS", selector)
            .output()
            .unwrap();
        assert!(result.status.success());
        assert!(result.stderr.is_empty());
        assert_eq!(
            result.stdout,
            format!("##vso[task.prependpath]{root}\n").as_bytes()
        );
    }
}

#[cfg(windows)]
#[test]
fn path_rejects_unpaired_surrogate_argv() {
    use std::{ffi::OsString, os::windows::ffi::OsStringExt};
    for units in [&[0x43, 0x3a, 0x5c, 0xd800][..], &[0x2d, 0xd800][..]] {
        let value = OsString::from_wide(units);
        let result = Command::new(env!("CARGO_BIN_EXE_shoutx"))
            .arg("azure-pipelines:path")
            .arg(value)
            .output()
            .unwrap();
        assert_eq!(result.status.code(), Some(1));
        assert!(result.stdout.is_empty());
        assert_eq!(result.stderr, b"error: input is not valid UTF-8\n");
    }
}

#[cfg(unix)]
#[test]
fn azure_path_invalid_dash_operand_is_input_failure() {
    use std::{ffi::OsString, os::unix::ffi::OsStringExt};
    for end_options in [false, true] {
        let mut command = Command::new(env!("CARGO_BIN_EXE_shoutx"));
        command.arg("azure-pipelines:path");
        if end_options {
            command.arg("--");
        }
        let result = command
            .arg(OsString::from_vec(vec![b'-', 0xff]))
            .output()
            .unwrap();
        assert_eq!(result.status.code(), Some(1));
        assert!(result.stdout.is_empty());
        assert_eq!(result.stderr, b"error: input is not valid UTF-8\n");
    }
}
