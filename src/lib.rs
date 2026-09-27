#![forbid(unsafe_code)]

pub mod cli;
pub mod error;
pub mod github_actions;
pub mod input;

use std::ffi::OsString;

pub use error::{ErrorClass, ShoutxError};

pub const VERSION: &str = env!("CARGO_PKG_VERSION");
pub const HELP: &str = "shoutx - safe CI output writers\n\nUsage:\n  shoutx github-actions:output [--first-line | --join-lines | --join-lines-with STRING | --multiline] NAME [VALUE]\n  shoutx github-actions:env    [--first-line | --join-lines | --join-lines-with STRING | --multiline] NAME [VALUE]\n  shoutx --help\n  shoutx --version\n";

pub fn prepare(args: Vec<OsString>) -> Result<cli::Action, ShoutxError> {
    cli::parse(args)
}

pub fn encode(request: cli::WriteRequest, value: Vec<u8>) -> Result<Vec<u8>, ShoutxError> {
    github_actions::encode(request, value)
}
