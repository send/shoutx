use std::{
    path::PathBuf,
    process::{Command, Output, Stdio},
};

const UNSTABLE_MARKERS: [&[u8]; 4] = [
    b"github-actions:mask",
    b"github-actions:notice",
    b"github-actions:warning",
    b"github-actions:error",
];

fn binary() -> PathBuf {
    match std::env::var_os("SHOUTX_VERIFY_BINARY") {
        Some(path) => PathBuf::from(path),
        None if std::env::var_os("SHOUTX_VERIFY_REQUIRE_EXTERNAL").is_some() => {
            panic!("external binary path is required")
        }
        None => PathBuf::from(env!("CARGO_BIN_EXE_shoutx")),
    }
}

#[test]
fn surface_verifier_sentinel() {
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
}

fn run(args: &[&str]) -> Output {
    Command::new(binary())
        .args(args)
        .stdin(Stdio::null())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .output()
        .expect("failed to execute the binary under verification")
}

fn require_bytes(label: &str, actual: &[u8], expected: &[u8]) {
    assert!(
        actual == expected,
        "{label} mismatch (actual length {}, expected length {})",
        actual.len(),
        expected.len()
    );
}

fn contains(haystack: &[u8], needle: &[u8]) -> bool {
    haystack
        .windows(needle.len())
        .any(|window| window == needle)
}

#[cfg(not(feature = "unstable-github-actions-stdout"))]
#[test]
fn packaged_binary_has_only_the_stable_surface() {
    let help = run(&["--help"]);
    assert_eq!(help.status.code(), Some(0));
    require_bytes(
        "help stdout",
        &help.stdout,
        include_bytes!("fixtures/stable-help.txt"),
    );
    require_bytes("help stderr", &help.stderr, b"");

    let version = run(&["--version"]);
    assert_eq!(version.status.code(), Some(0));
    require_bytes(
        "version stdout",
        &version.stdout,
        format!("shoutx {}\n", shoutx::VERSION).as_bytes(),
    );
    require_bytes("version stderr", &version.stderr, b"");

    for args in [
        ["github-actions:mask", "fixed-mask-value"].as_slice(),
        ["github-actions:mask", "--help"].as_slice(),
        ["github-actions:mask", "--version"].as_slice(),
        ["github-actions:notice", "fixed notice"].as_slice(),
        ["github-actions:warning", "fixed warning"].as_slice(),
        ["github-actions:error", "fixed error"].as_slice(),
    ] {
        let output = run(args);
        assert_eq!(output.status.code(), Some(2));
        require_bytes("unknown-command stdout", &output.stdout, b"");
        require_bytes(
            "unknown-command stderr",
            &output.stderr,
            b"error: unknown command\n",
        );
    }

    let bytes = std::fs::read(binary()).expect("failed to read the binary under verification");
    for marker in UNSTABLE_MARKERS {
        assert!(
            !contains(&bytes, marker),
            "stable binary contains an unstable marker of length {}",
            marker.len()
        );
    }
}

#[cfg(feature = "unstable-github-actions-stdout")]
#[test]
fn unstable_binary_is_an_explicit_marker_scan_control() {
    let version = run(&["--version"]);
    assert_eq!(version.status.code(), Some(0));
    require_bytes(
        "unstable version stdout",
        &version.stdout,
        format!(
            "shoutx {} (unstable-github-actions-stdout)\n",
            shoutx::VERSION
        )
        .as_bytes(),
    );
    require_bytes("unstable version stderr", &version.stderr, b"");

    let bytes = std::fs::read(binary()).expect("failed to read the binary under verification");
    for marker in UNSTABLE_MARKERS {
        assert!(
            contains(&bytes, marker),
            "unstable control binary lacks a marker of length {}",
            marker.len()
        );
    }
}
