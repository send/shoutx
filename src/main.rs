#![forbid(unsafe_code)]

mod process_io;

use std::{
    ffi::OsString,
    io::{self, IsTerminal, Write},
    panic,
    process::ExitCode,
};

use shoutx::{ShoutxError, cli::Action, error::ErrorClass};

fn diagnostic(message: &'static str) {
    let mut stderr = io::stderr().lock();
    let _ = stderr.write_all(b"error: ");
    let _ = stderr.write_all(message.as_bytes());
    let _ = stderr.write_all(b"\n");
}

fn output(bytes: &[u8]) -> Result<(), ShoutxError> {
    let mut stdout =
        process_io::stdout_file().map_err(|_| ShoutxError::failure("failed to open stdout"))?;
    stdout
        .write_all(bytes)
        .and_then(|_| stdout.flush())
        .map_err(|_| ShoutxError::failure("failed to write stdout"))
}

fn run() -> Result<(), ShoutxError> {
    let args: Vec<OsString> = std::env::args_os().skip(1).collect();
    match shoutx::prepare(args)? {
        Action::Help => output(shoutx::HELP.as_bytes()),
        Action::Version => output(shoutx::version_output().as_bytes()),
        Action::Write(request) => {
            shoutx::github_actions::validate_request(&request)?;
            let value = if let Some(value) = request.value.as_ref() {
                shoutx::cli::os_bytes(value)?.to_vec()
            } else {
                if io::stdin().is_terminal() {
                    return Err(ShoutxError::usage(
                        "VALUE omitted while stdin is a terminal",
                    ));
                }
                let mut stdin = process_io::stdin_file()
                    .map_err(|_| ShoutxError::failure("failed to open stdin"))?;
                shoutx::input::read_bounded(&mut stdin)?
            };
            let target_os = shoutx::github_actions::TargetOs::from_runner_os(
                std::env::var_os("RUNNER_OS").as_deref(),
            );
            let record = shoutx::github_actions::encode_with(
                request,
                value,
                target_os,
                &mut shoutx::github_actions::OsRandom,
            )?;
            output(&record)
        }
        Action::WritePath(request) => {
            let target_os = shoutx::github_actions::TargetOs::from_runner_os(
                std::env::var_os("RUNNER_OS").as_deref(),
            );
            if target_os == shoutx::github_actions::TargetOs::Unknown {
                return Err(ShoutxError::failure("unknown target runner OS"));
            }
            let value = if let Some(value) = request.value.as_ref() {
                shoutx::cli::os_bytes(value)?.to_vec()
            } else {
                if io::stdin().is_terminal() {
                    return Err(ShoutxError::usage(
                        "VALUE omitted while stdin is a terminal",
                    ));
                }
                let mut stdin = process_io::stdin_file()
                    .map_err(|_| ShoutxError::failure("failed to open stdin"))?;
                shoutx::input::read_bounded(&mut stdin)?
            };
            output(&shoutx::github_actions::encode_path(value, target_os)?)
        }
        #[cfg(feature = "unstable-github-actions-stdout")]
        Action::Mask(request) => {
            let value = if let Some(value) = request.value.as_ref() {
                shoutx::cli::os_bytes(value)?.to_vec()
            } else {
                if io::stdin().is_terminal() {
                    return Err(ShoutxError::usage(
                        "VALUE omitted while stdin is a terminal",
                    ));
                }
                let mut stdin = process_io::stdin_file()
                    .map_err(|_| ShoutxError::failure("failed to open stdin"))?;
                shoutx::input::read_bounded(&mut stdin)?
            };
            output(&shoutx::github_actions::encode_mask(value)?)
        }
        #[cfg(feature = "unstable-github-actions-stdout")]
        Action::Annotate(request) => {
            let message = if let Some(message) = request.message.as_ref() {
                shoutx::cli::os_bytes(message)?.to_vec()
            } else {
                if io::stdin().is_terminal() {
                    return Err(ShoutxError::usage(
                        "MESSAGE omitted while stdin is a terminal",
                    ));
                }
                let mut stdin = process_io::stdin_file()
                    .map_err(|_| ShoutxError::failure("failed to open stdin"))?;
                shoutx::input::read_bounded(&mut stdin)?
            };
            output(&shoutx::github_actions::encode_annotation(
                request, message,
            )?)
        }
    }
}

fn caught_status<F>(operation: F) -> u8
where
    F: FnOnce() -> Result<(), ShoutxError> + panic::UnwindSafe,
{
    match panic::catch_unwind(operation) {
        Ok(Ok(())) => 0,
        Ok(Err(error)) => {
            diagnostic(error.message());
            match error.class() {
                ErrorClass::Failure => 1,
                ErrorClass::Usage => 2,
            }
        }
        Err(_) => 1,
    }
}

fn main() -> ExitCode {
    panic::set_hook(Box::new(|_| diagnostic("internal failure")));
    ExitCode::from(caught_status(run))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn recoverable_panic_maps_to_status_one() {
        assert_eq!(caught_status(|| panic!("secret panic payload")), 1);
    }

    #[test]
    fn diagnostic_failure_cannot_change_classified_status() {
        assert_eq!(caught_status(|| Err(ShoutxError::failure("failure"))), 1);
        assert_eq!(caught_status(|| Err(ShoutxError::usage("usage"))), 2);
    }
}
