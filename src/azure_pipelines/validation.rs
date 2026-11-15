//! Basic Azure text checks only; command-specific admission stays local.
use crate::ShoutxError;

pub(super) fn validate_text(bytes: &[u8], limit: usize, empty: bool) -> Result<(), ShoutxError> {
    if bytes.len() > limit {
        return Err(ShoutxError::failure("Azure field exceeds size limit"));
    }
    std::str::from_utf8(bytes)
        .map_err(|_| ShoutxError::failure("Azure field is not valid UTF-8"))?;
    if bytes.contains(&0) {
        return Err(ShoutxError::failure("Azure field contains NUL"));
    }
    if !empty && bytes.is_empty() {
        return Err(ShoutxError::failure("Azure field must not be empty"));
    }
    Ok(())
}
