#![forbid(unsafe_code)]

pub mod azure_pipelines;
pub mod cli;
pub mod error;
pub mod github_actions;
pub mod input;

use std::ffi::OsString;

pub use error::{ErrorClass, ShoutxError};

pub const VERSION: &str = env!("CARGO_PKG_VERSION");
macro_rules! stable_help {
    () => {
        "shoutx - safe CI output writers\n\nUsage:\n  shoutx github-actions:output [--first-line | --join-lines | --join-lines-with STRING | --multiline] NAME [VALUE]\n  shoutx github-actions:env    [--first-line | --join-lines | --join-lines-with STRING | --multiline] NAME [VALUE]\n  shoutx github-actions:state  [--first-line | --join-lines | --join-lines-with STRING | --multiline] NAME [VALUE]\n  shoutx github-actions:path   [VALUE]\n  shoutx --help\n  shoutx --version\n"
    };
}

pub const HELP: &str = concat!(
    stable_help!(),
    "\nGitHub Actions artifact declarations:\n",
    "  shoutx github-actions:artifacts file [PATH]\n",
    "  shoutx github-actions:artifacts oci REFERENCE DIGEST\n",
    "\nGitHub Actions stdout commands:\n",
    "  shoutx github-actions:add-matcher [PATH]\n",
    "  shoutx github-actions:remove-matcher owner [OWNER]\n",
    "  shoutx github-actions:remove-matcher file [PATH]\n",
    "  shoutx github-actions:debug [MESSAGE]\n",
    "  shoutx github-actions:group [TITLE]\n",
    "  shoutx github-actions:endgroup\n",
    "  shoutx github-actions:mask   [VALUE]\n",
    "  shoutx github-actions:notice  [--title TITLE] [--file FILE] [--line N] [--end-line N] [--column N] [--end-column N] [MESSAGE]\n",
    "  shoutx github-actions:warning [--title TITLE] [--file FILE] [--line N] [--end-line N] [--column N] [--end-column N] [MESSAGE]\n",
    "  shoutx github-actions:error   [--title TITLE] [--file FILE] [--line N] [--end-line N] [--column N] [--end-column N] [MESSAGE]\n",
    "\nAzure Pipelines commands (unreleased):\n",
    "  shoutx azure-pipelines:variable [--output] [--read-only] NAME [VALUE]\n",
    "  shoutx azure-pipelines:warning [--file FILE] [--line N] [--column N] [--code CODE] [MESSAGE]\n",
    "  shoutx azure-pipelines:error   [--file FILE] [--line N] [--column N] [--code CODE] [MESSAGE]\n",
    "  shoutx azure-pipelines:path [PATH]\n",
    "  shoutx azure-pipelines:mask [--each-line]\n",
    "  shoutx azure-pipelines:build-number [NUMBER]\n",
    "  shoutx azure-pipelines:build-tag [TAG]\n",
);

pub fn version_output() -> String {
    format!("shoutx {VERSION}\n")
}

pub fn prepare(args: Vec<OsString>) -> Result<cli::Action, ShoutxError> {
    cli::parse(args)
}

pub fn encode(request: cli::WriteRequest, value: Vec<u8>) -> Result<Vec<u8>, ShoutxError> {
    github_actions::encode(request, value)
}
