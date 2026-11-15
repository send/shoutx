//! Azure logging-command framing and escaping, without destination policy.
use crate::ShoutxError;
pub(super) const RECORD_LIMIT: usize = 8 * 1024 * 1024;

pub(super) fn escaped(byte: u8) -> Option<&'static [u8]> {
    match byte {
        b'%' => Some(b"%AZP25"),
        b'\r' => Some(b"%0D"),
        b'\n' => Some(b"%0A"),
        b';' => Some(b"%3B"),
        b']' => Some(b"%5D"),
        _ => None,
    }
}

pub(super) fn record(
    command: &[u8],
    properties: &[(&[u8], &[u8])],
    data: &[u8],
) -> Result<Vec<u8>, ShoutxError> {
    // Fixed syntax + each property key, '=' and ';' + escaped values.
    let mut size =
        Some(b"##vso[".len() + command.len() + b"]\n".len() + usize::from(!properties.is_empty()));
    for (key, value) in properties {
        size = size.and_then(|n| n.checked_add(key.len() + 2));
        for &byte in *value {
            size = size.and_then(|n| n.checked_add(escaped(byte).map_or(1, <[u8]>::len)));
        }
    }
    for &byte in data {
        size = size.and_then(|n| n.checked_add(escaped(byte).map_or(1, <[u8]>::len)));
    }
    let size = size
        .filter(|n| *n <= RECORD_LIMIT)
        .ok_or_else(|| ShoutxError::failure("encoded Azure command exceeds size limit"))?;
    let mut out = Vec::with_capacity(size);
    out.extend_from_slice(b"##vso[");
    out.extend_from_slice(command);
    if !properties.is_empty() {
        out.push(b' ');
    }
    for (key, value) in properties {
        out.extend_from_slice(key);
        out.push(b'=');
        append(&mut out, value);
        out.push(b';');
    }
    out.push(b']');
    append(&mut out, data);
    out.push(b'\n');
    debug_assert_eq!(size, out.len());
    Ok(out)
}

pub(super) fn append(out: &mut Vec<u8>, bytes: &[u8]) {
    for &byte in bytes {
        match escaped(byte) {
            Some(replacement) => out.extend_from_slice(replacement),
            None => out.push(byte),
        }
    }
}
