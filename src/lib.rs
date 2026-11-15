#![forbid(unsafe_code)]
pub mod azure_pipelines;
pub mod cli;
pub mod error;
pub mod github_actions;
pub mod input;
pub mod provider;
pub use error::{ErrorClass, ShoutxError};
pub const VERSION: &str = env!("CARGO_PKG_VERSION");
pub fn version_output() -> String {
    format!("shoutx {VERSION}\n")
}
pub fn help() -> String {
    provider::help()
}
pub fn prepare(
    args: Vec<std::ffi::OsString>,
) -> Result<cli::Parsed<provider::Invocation>, ShoutxError> {
    cli::parse(args)
}
