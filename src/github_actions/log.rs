use crate::{cli::LogKind, error::ShoutxError, input::VALUE_LIMIT};

pub fn encode(kind: LogKind, mut value: Vec<u8>) -> Result<Vec<u8>, ShoutxError> {
    if value.len() > VALUE_LIMIT {
        return Err(ShoutxError::failure("value exceeds size limit"));
    }
    std::str::from_utf8(&value).map_err(|_| ShoutxError::failure("value is not valid UTF-8"))?;
    if value.contains(&0) {
        return Err(ShoutxError::failure("value contains NUL"));
    }
    super::normalize::strip_final(&mut value);
    if kind == LogKind::Group && value.iter().any(|byte| matches!(byte, b'\r' | b'\n')) {
        return Err(ShoutxError::failure("group title contains CR or LF"));
    }
    let text = std::str::from_utf8(&value)
        .map_err(|_| ShoutxError::failure("value is not valid UTF-8"))?;
    if !text.is_empty() && !super::stdout_guard::has_allowed_data_prefix(text) {
        return Err(ShoutxError::failure(
            "log value is outside the Unicode boundary policy",
        ));
    }
    let prefix: &[u8] = match kind {
        LogKind::Debug => b"::debug::",
        LogKind::Group => b"::group::",
    };
    let capacity = value
        .iter()
        .try_fold(prefix.len() + 1, |size, byte| {
            size.checked_add(if matches!(byte, b'%' | b'\r' | b'\n') {
                3
            } else {
                1
            })
        })
        .ok_or_else(|| ShoutxError::failure("encoded log command exceeds size limit"))?;
    let mut output = Vec::with_capacity(capacity);
    output.extend_from_slice(prefix);
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
