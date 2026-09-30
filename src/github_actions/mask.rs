use crate::{error::ShoutxError, input::VALUE_LIMIT};

use super::normalize::strip_final;

const PREFIX: &[u8] = b"::add-mask::";

pub fn encode(mut value: Vec<u8>) -> Result<Vec<u8>, ShoutxError> {
    if value.len() > VALUE_LIMIT {
        return Err(ShoutxError::failure("value exceeds size limit"));
    }
    std::str::from_utf8(&value).map_err(|_| ShoutxError::failure("value is not valid UTF-8"))?;
    if value.contains(&0) {
        return Err(ShoutxError::failure("value contains NUL"));
    }

    strip_final(&mut value);
    let text = std::str::from_utf8(&value)
        .map_err(|_| ShoutxError::failure("value is not valid UTF-8"))?;
    if text.is_empty() || text.chars().all(char::is_whitespace) {
        return Err(ShoutxError::failure(
            "mask value is empty or whitespace only",
        ));
    }
    if super::stdout_guard::has_sensitive_data_prefix(text) {
        return Err(ShoutxError::failure(
            "mask value begins with a separator-sensitive character",
        ));
    }

    let escaped_len = value.iter().try_fold(0usize, |length, byte| {
        length.checked_add(if matches!(byte, b'%' | b'\r' | b'\n') {
            3
        } else {
            1
        })
    });
    let capacity = escaped_len
        .and_then(|length| length.checked_add(PREFIX.len() + 1))
        .ok_or_else(|| ShoutxError::failure("encoded mask exceeds size limit"))?;

    let mut output = Vec::with_capacity(capacity);
    output.extend_from_slice(PREFIX);
    for byte in value {
        match byte {
            b'%' => output.extend_from_slice(b"%25"),
            b'\r' => output.extend_from_slice(b"%0D"),
            b'\n' => output.extend_from_slice(b"%0A"),
            _ => output.push(byte),
        }
    }
    output.push(b'\n');
    Ok(output)
}
