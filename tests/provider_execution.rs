//! Host-operation assertions protect ordering when provider dispatch is moved.
use shoutx::{ShoutxError, cli::Parsed, provider::Context};
use std::ffi::OsString;

#[derive(Default)]
struct Host {
    events: Vec<String>,
    runner_os: Option<OsString>,
}
impl Context for Host {
    fn read_stdin(&mut self, missing: &'static str) -> Result<Vec<u8>, ShoutxError> {
        self.events.push(format!("stdin:{missing}"));
        Err(ShoutxError::failure("test stdin unavailable"))
    }
    fn env_var(&mut self, name: &str) -> Option<OsString> {
        self.events.push(format!("env:{name}"));
        self.runner_os.clone()
    }
}
fn execute(args: &[&str], host: &mut Host) -> Result<Vec<u8>, ShoutxError> {
    match shoutx::prepare(args.iter().map(OsString::from).collect())? {
        Parsed::Help => Ok(shoutx::help().into_bytes()),
        Parsed::Version => Ok(shoutx::version_output().into_bytes()),
        Parsed::Command(request) => request.encode(host),
    }
}

#[test]
fn help_version_and_no_input_commands_do_not_touch_host() {
    let mut host = Host::default();
    for name in shoutx::cli::command_names() {
        assert_eq!(
            execute(&[name, "--help", "ignored"], &mut host).unwrap(),
            shoutx::help().as_bytes()
        );
        assert_eq!(
            execute(&[name, "--version", "ignored"], &mut host).unwrap(),
            shoutx::version_output().as_bytes()
        );
    }
    assert_eq!(
        execute(&["github-actions:endgroup"], &mut host).unwrap(),
        b"::endgroup::\n"
    );
    assert_eq!(
        execute(&["azure-pipelines:endgroup"], &mut host).unwrap(),
        b"##[endgroup]\n"
    );
    assert!(host.events.is_empty());
}

#[test]
fn argv_values_bypass_stdin_in_both_providers() {
    let mut host = Host::default();
    assert_eq!(
        execute(&["github-actions:debug", "hello"], &mut host).unwrap(),
        b"::debug::hello\n"
    );
    assert_eq!(
        execute(&["azure-pipelines:debug", "hello"], &mut host).unwrap(),
        b"##vso[task.debug]hello\n"
    );
    assert_eq!(
        execute(&["github-actions:output", "x", "hello"], &mut host).unwrap(),
        b"x=hello\n"
    );
    assert_eq!(host.events, ["env:RUNNER_OS"]);
}

#[test]
fn preflight_failures_precede_stdin_and_environment_access() {
    for args in [
        vec!["github-actions:output", "bad=name"],
        vec!["github-actions:output", "--join-lines-with", "\n", "name"],
        vec!["azure-pipelines:variable", "bad=name"],
        vec!["azure-pipelines:secret-variable", "bad=name"],
        vec!["azure-pipelines:secret-variable", "name", "forbidden-argv"],
    ] {
        let mut host = Host::default();
        let error = execute(&args, &mut host).unwrap_err();
        assert_ne!(error.message(), "test stdin unavailable", "{args:?}");
        assert!(host.events.is_empty(), "{args:?}");
    }
}

#[test]
fn path_checks_environment_before_stdin_but_named_records_read_first() {
    let mut host = Host {
        runner_os: Some("unsupported".into()),
        ..Host::default()
    };
    assert_eq!(
        execute(&["github-actions:path"], &mut host)
            .unwrap_err()
            .message(),
        "unknown target runner OS"
    );
    assert_eq!(host.events, ["env:RUNNER_OS"]);
    host.events.clear();
    assert_eq!(
        execute(&["github-actions:output", "name"], &mut host)
            .unwrap_err()
            .message(),
        "test stdin unavailable"
    );
    assert_eq!(
        host.events,
        ["stdin:VALUE omitted while stdin is a terminal"]
    );
}

#[test]
fn post_input_field_validation_does_not_move_before_stdin() {
    for args in [
        vec!["github-actions:warning", "--line", "invalid"],
        vec!["azure-pipelines:warning", "--line", "invalid"],
    ] {
        let mut host = Host::default();
        assert_eq!(
            execute(&args, &mut host).unwrap_err().message(),
            "test stdin unavailable"
        );
        assert_eq!(host.events.len(), 1);
    }
}

#[test]
fn missing_operand_diagnostic_is_owned_by_command() {
    for (args, expected) in [
        (vec!["github-actions:artifacts", "file"], "PATH"),
        (vec!["github-actions:warning"], "MESSAGE"),
        (vec!["github-actions:mask"], "VALUE"),
        (vec!["azure-pipelines:summary"], "VALUE"),
        (vec!["azure-pipelines:mask"], "VALUE"),
        (vec!["azure-pipelines:secret-variable", "name"], "VALUE"),
    ] {
        let mut host = Host::default();
        assert_eq!(
            execute(&args, &mut host).unwrap_err().message(),
            "test stdin unavailable"
        );
        assert_eq!(
            host.events,
            [format!(
                "stdin:{expected} omitted while stdin is a terminal"
            )]
        );
    }
}
