use crate::{cli::LineMode, error::ShoutxError, input::VALUE_LIMIT};

pub(super) fn strip_final(value: &mut Vec<u8>) {
    if value.ends_with(b"\r\n") {
        value.truncate(value.len() - 2);
    } else if value.ends_with(b"\r") || value.ends_with(b"\n") {
        value.pop();
    }
}

pub fn apply(mode: LineMode, mut value: Vec<u8>) -> Result<Vec<u8>, ShoutxError> {
    strip_final(&mut value);
    match mode {
        LineMode::Default => {
            if value.iter().any(|b| *b == b'\r' || *b == b'\n') {
                return Err(ShoutxError::failure("value contains CR or LF"));
            }
            Ok(value)
        }
        LineMode::FirstLine => {
            if let Some(index) = value.iter().position(|b| *b == b'\r' || *b == b'\n') {
                value.truncate(index);
            }
            Ok(value)
        }
        LineMode::Join(separator) => join(value, separator),
        LineMode::Multiline => Err(ShoutxError::failure("invalid normalization mode")),
    }
}

fn join(value: Vec<u8>, separator: Vec<u8>) -> Result<Vec<u8>, ShoutxError> {
    validate_separator(&separator)?;

    let mut retained = 0usize;
    let mut boundaries = 0usize;
    let mut i = 0;
    while i < value.len() {
        if value[i] == b'\r' {
            boundaries += 1;
            i += if value.get(i + 1) == Some(&b'\n') {
                2
            } else {
                1
            };
        } else if value[i] == b'\n' {
            boundaries += 1;
            i += 1;
        } else {
            retained += 1;
            i += 1;
        }
    }
    let size = boundaries
        .checked_mul(separator.len())
        .and_then(|n| retained.checked_add(n))
        .ok_or_else(|| ShoutxError::failure("normalized value exceeds size limit"))?;
    if size > VALUE_LIMIT {
        return Err(ShoutxError::failure("normalized value exceeds size limit"));
    }
    let mut out = Vec::with_capacity(size);
    i = 0;
    while i < value.len() {
        if value[i] == b'\r' {
            out.extend_from_slice(&separator);
            i += if value.get(i + 1) == Some(&b'\n') {
                2
            } else {
                1
            };
        } else if value[i] == b'\n' {
            out.extend_from_slice(&separator);
            i += 1;
        } else {
            out.push(value[i]);
            i += 1;
        }
    }
    Ok(out)
}

pub(super) fn validate_separator(separator: &[u8]) -> Result<(), ShoutxError> {
    if separator.len() > 255
        || separator.contains(&0)
        || separator.iter().any(|b| *b == b'\r' || *b == b'\n')
        || std::str::from_utf8(separator).is_err()
    {
        return Err(ShoutxError::failure("invalid join separator"));
    }
    Ok(())
}
