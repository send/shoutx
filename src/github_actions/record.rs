use crate::error::ShoutxError;

pub fn single_line(name: Vec<u8>, value: Vec<u8>) -> Result<Vec<u8>, ShoutxError> {
    let capacity = name
        .len()
        .checked_add(value.len())
        .and_then(|n| n.checked_add(2))
        .ok_or_else(|| ShoutxError::failure("record size overflow"))?;
    let mut out = Vec::with_capacity(capacity);
    out.extend_from_slice(&name);
    out.push(b'=');
    out.extend_from_slice(&value);
    out.push(b'\n');
    Ok(out)
}
