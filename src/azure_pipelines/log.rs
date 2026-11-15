use super::{
    record::{RECORD_LIMIT, record},
    request::LogKind,
    validation::validate_text,
};
use crate::{ShoutxError, input::VALUE_LIMIT};

pub fn encode_log(kind: LogKind, value: &[u8]) -> Result<Vec<u8>, ShoutxError> {
    validate_text(value, VALUE_LIMIT, true)?;
    if value.iter().any(|b| matches!(b, b'\r' | b'\n')) {
        return Err(ShoutxError::failure(
            "Azure log value contains a line boundary",
        ));
    }
    if matches!(kind, LogKind::Group) && value.is_empty() {
        return Err(ShoutxError::failure("Azure group title must not be empty"));
    }
    if value.windows(3).any(|part| part == b"##[")
        || matches!(kind, LogKind::Group) && value.windows(5).any(|part| part == b"##vso")
    {
        return Err(ShoutxError::failure(
            "Azure log value contains reserved syntax",
        ));
    }
    match kind {
        LogKind::Debug => record(b"task.debug", &[], value),
        LogKind::Group => {
            const HEADER: &[u8] = b"##[group]";
            let size = value
                .len()
                .checked_add(HEADER.len() + 1)
                .filter(|n| *n <= RECORD_LIMIT)
                .ok_or_else(|| ShoutxError::failure("encoded Azure command exceeds size limit"))?;
            let mut out = Vec::with_capacity(size);
            out.extend_from_slice(HEADER);
            out.extend_from_slice(value);
            out.push(b'\n');
            Ok(out)
        }
    }
}
