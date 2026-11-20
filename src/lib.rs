#![forbid(unsafe_code)]
#[cfg(feature = "azure-pipelines")]
pub mod azure_pipelines;
#[cfg(not(any(feature = "github-actions", feature = "azure-pipelines")))]
compile_error!("enable at least one provider feature");
pub mod cli;
pub mod error;
#[cfg(feature = "github-actions")]
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
