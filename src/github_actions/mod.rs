#[cfg(feature = "unstable-github-actions-stdout")]
mod annotation;
#[cfg(feature = "unstable-github-actions-stdout")]
mod mask;
mod name;
mod normalize;
mod path;
mod random;
mod record;
#[cfg(feature = "unstable-github-actions-stdout")]
mod stdout_guard;

use std::ffi::OsStr;

use crate::{cli::WriteRequest, error::ShoutxError, input::VALUE_LIMIT};

#[cfg(feature = "unstable-github-actions-stdout")]
pub use annotation::encode as encode_annotation;
#[cfg(feature = "unstable-github-actions-stdout")]
pub use mask::encode as encode_mask;
pub use path::encode as encode_path;
pub use random::{OsRandom, RandomSource};

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum TargetOs {
    Linux,
    MacOs,
    Windows,
    Unknown,
}

impl TargetOs {
    pub fn from_runner_os(value: Option<&OsStr>) -> Self {
        match value.and_then(OsStr::to_str) {
            Some("Linux") => Self::Linux,
            Some("macOS") => Self::MacOs,
            Some("Windows") => Self::Windows,
            Some(_) => Self::Unknown,
            None if value.is_some() => Self::Unknown,
            None => Self::native(),
        }
    }

    pub const fn native() -> Self {
        if cfg!(windows) {
            Self::Windows
        } else if cfg!(target_os = "macos") {
            Self::MacOs
        } else if cfg!(target_os = "linux") {
            Self::Linux
        } else {
            Self::Unknown
        }
    }
}

pub fn validate_request(request: &WriteRequest) -> Result<(), ShoutxError> {
    name::validate(request.destination, &request.name)?;
    if let crate::cli::LineMode::Join(separator) = &request.mode {
        normalize::validate_separator(separator)?;
    }
    Ok(())
}

pub fn encode(request: WriteRequest, value: Vec<u8>) -> Result<Vec<u8>, ShoutxError> {
    encode_with(request, value, TargetOs::native(), &mut OsRandom)
}

pub fn encode_with(
    request: WriteRequest,
    value: Vec<u8>,
    target_os: TargetOs,
    random: &mut impl RandomSource,
) -> Result<Vec<u8>, ShoutxError> {
    validate_request(&request)?;
    if value.len() > VALUE_LIMIT {
        return Err(ShoutxError::failure("value exceeds size limit"));
    }
    std::str::from_utf8(&value).map_err(|_| ShoutxError::failure("value is not valid UTF-8"))?;
    if value.contains(&0) {
        return Err(ShoutxError::failure("value contains NUL"));
    }
    let name = name::validate(request.destination, &request.name)?;
    match request.mode {
        crate::cli::LineMode::Multiline => record::multiline(name, value, target_os, random),
        mode => {
            let normalized = normalize::apply(mode, value)?;
            record::single_line(name, normalized)
        }
    }
}
