//! Typed Azure logging commands. No dependency on GitHub's boundary policy.
mod build_metadata;
pub(crate) mod cli;
mod execute;
mod file;
mod issue;
mod log;
mod mask;
mod path;
mod path_syntax;
mod record;
pub mod request;
mod validation;
mod variable;

pub use build_metadata::encode_build_metadata;
pub use file::encode_file;
pub use issue::encode_issue;
pub use log::encode_log;
pub use mask::encode_mask;
pub use path::encode_path;
pub use request::{BuildMetadata, FileKind, Issue, LogKind, Severity, Variable};
pub use variable::{encode_secret_variable, encode_variable, validate_variable};
