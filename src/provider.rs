//! Explicit registration of built-in providers. This is not a stable plugin API.
use crate::{ShoutxError, cli::Parsed};
use std::ffi::OsString;

/// Host capabilities are lazy: a provider requests input/environment only at
/// the point required by its command contract. Providers never write stdout.
pub trait Context {
    fn read_stdin(&mut self, missing_operand: &'static str) -> Result<Vec<u8>, ShoutxError>;
    fn env_var(&mut self, name: &str) -> Option<OsString>;
}

#[derive(Debug)]
pub enum Invocation {
    Github(crate::github_actions::request::Request),
    Azure(crate::azure_pipelines::request::Request),
}
impl Invocation {
    pub fn encode(self, context: &mut impl Context) -> Result<Vec<u8>, ShoutxError> {
        match self {
            Self::Github(request) => request.encode(context),
            Self::Azure(request) => request.encode(context),
        }
    }
}

struct Provider {
    namespace: &'static str,
    names: fn() -> Vec<&'static str>,
    parse: fn(&str, Vec<OsString>) -> Result<Parsed<Invocation>, ShoutxError>,
    help: fn(&mut String),
}
const PROVIDERS: &[Provider] = &[
    Provider {
        namespace: "azure-pipelines",
        names: || crate::azure_pipelines::cli::command_names().collect(),
        parse: |command, args| {
            Ok(crate::azure_pipelines::cli::parse(command, args)?.map(Invocation::Azure))
        },
        help: crate::azure_pipelines::cli::help,
    },
    Provider {
        namespace: "github-actions",
        names: || crate::github_actions::cli::command_names().collect(),
        parse: |command, args| {
            Ok(crate::github_actions::cli::parse(command, args)?.map(Invocation::Github))
        },
        help: crate::github_actions::cli::help,
    },
];

pub(crate) fn command_names() -> impl Iterator<Item = &'static str> {
    PROVIDERS.iter().flat_map(|provider| (provider.names)())
}
pub(crate) fn parse(command: &str, args: Vec<OsString>) -> Result<Parsed<Invocation>, ShoutxError> {
    let namespace = command.split_once(':').map(|(namespace, _)| namespace);
    let provider = PROVIDERS
        .iter()
        .find(|p| Some(p.namespace) == namespace)
        .ok_or_else(|| ShoutxError::usage("unknown command"))?;
    (provider.parse)(command, args)
}
pub(crate) fn help() -> String {
    let mut out = String::from("shoutx - safe CI output writers\n\n");
    // Retain the established help layout independently of command enumeration.
    for provider in PROVIDERS.iter().rev() {
        (provider.help)(&mut out);
    }
    out
}
