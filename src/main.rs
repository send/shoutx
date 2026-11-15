#![forbid(unsafe_code)]

mod process_io;

use std::{
    ffi::OsString,
    io::{self, IsTerminal, Write},
    panic,
    process::ExitCode,
};

use shoutx::{ShoutxError, cli::Parsed, error::ErrorClass};

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

struct ProcessContext;
impl shoutx::provider::Context for ProcessContext {
    fn read_stdin(&mut self, missing_operand: &'static str) -> Result<Vec<u8>, ShoutxError> {
        if io::stdin().is_terminal() {
            return Err(ShoutxError::usage(missing_operand));
        }
        let mut stdin =
            process_io::stdin_file().map_err(|_| ShoutxError::failure("failed to open stdin"))?;
        shoutx::input::read_bounded(&mut stdin)
    }
    fn env_var(&mut self, name: &str) -> Option<OsString> {
        std::env::var_os(name)
    }
}

fn run() -> Result<(), ShoutxError> {
    let args = std::env::args_os().skip(1).collect();
    let bytes = match shoutx::prepare(args)? {
        Parsed::Help => shoutx::help().into_bytes(),
        Parsed::Version => shoutx::version_output().into_bytes(),
        Parsed::Command(request) => request.encode(&mut ProcessContext)?,
    };
    output(&bytes)
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
