use crate::{
    cli::{Destination, os_bytes},
    error::ShoutxError,
};
use std::ffi::OsStr;

pub fn validate(destination: Destination, name: &OsStr) -> Result<Vec<u8>, ShoutxError> {
    let bytes = os_bytes(name)?;
    if bytes.is_empty() || bytes.len() > 255 {
        return Err(ShoutxError::failure("invalid record name"));
    }
    if !(bytes[0].is_ascii_alphabetic() || bytes[0] == b'_') {
        return Err(ShoutxError::failure("invalid record name"));
    }
    let valid = bytes[1..].iter().all(|b| {
        b.is_ascii_alphanumeric()
            || *b == b'_'
            || (destination == Destination::Output && *b == b'-')
    });
    if !valid {
        return Err(ShoutxError::failure("invalid record name"));
    }
    if destination == Destination::Env {
        let upper: Vec<u8> = bytes.iter().map(u8::to_ascii_uppercase).collect();
        if upper.starts_with(b"GITHUB_")
            || upper.starts_with(b"RUNNER_")
            || upper == b"NODE_OPTIONS"
        {
            return Err(ShoutxError::failure("reserved environment name"));
        }
    }
    Ok(bytes.to_vec())
}
