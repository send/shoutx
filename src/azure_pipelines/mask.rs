use super::{
    record::{RECORD_LIMIT, append, escaped},
    validation::validate_text,
};
use crate::{ShoutxError, input::VALUE_LIMIT};

/// Prepare the entire mask batch before allowing any stdout side effect.
pub fn encode_mask(value: &[u8], each_line: bool) -> Result<Vec<u8>, ShoutxError> {
    validate_text(value, VALUE_LIMIT, false)?;
    if !each_line && value.iter().any(|b| matches!(b, b'\r' | b'\n')) {
        return Err(ShoutxError::failure("Azure mask contains a line boundary"));
    }
    // Splitting both bytes and omitting empty segments also consumes CRLF as
    // one boundary: its intermediate empty segment cannot become an entry.
    let segments: Vec<&[u8]> = value
        .split(|b| each_line && matches!(b, b'\r' | b'\n'))
        .filter(|segment| !segment.is_empty())
        .take(1025)
        .collect();
    if segments.is_empty() {
        return Err(ShoutxError::failure("Azure mask has no nonempty entries"));
    }
    if segments.len() > 1024 {
        return Err(ShoutxError::failure("Azure mask exceeds entry limit"));
    }
    const HEADER: &[u8] = b"##vso[task.setsecret]";
    let mut size = Some(0usize);
    for segment in &segments {
        size = size.and_then(|n| n.checked_add(HEADER.len() + 1));
        for &byte in *segment {
            size = size.and_then(|n| n.checked_add(escaped(byte).map_or(1, <[u8]>::len)));
        }
    }
    let size = size
        .filter(|n| *n <= RECORD_LIMIT)
        .ok_or_else(|| ShoutxError::failure("encoded Azure command exceeds size limit"))?;
    let mut out = Vec::with_capacity(size);
    for segment in segments {
        out.extend_from_slice(HEADER);
        append(&mut out, segment);
        out.push(b'\n');
    }
    debug_assert_eq!(size, out.len());
    Ok(out)
}
