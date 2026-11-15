use crate::error::ShoutxError;
use std::io::Read;

pub const VALUE_LIMIT: usize = 1_048_576;

pub fn read_bounded(reader: &mut impl Read) -> Result<Vec<u8>, ShoutxError> {
    let mut value = Vec::new();
    reader
        .take((VALUE_LIMIT + 1) as u64)
        .read_to_end(&mut value)
        .map_err(|_| ShoutxError::failure("failed to read stdin"))?;
    if value.len() > VALUE_LIMIT {
        return Err(ShoutxError::failure("value exceeds size limit"));
    }
    Ok(value)
}

pub fn os_bytes(value: &std::ffi::OsStr) -> Result<&[u8], ShoutxError> {
    value
        .to_str()
        .map(str::as_bytes)
        .ok_or_else(|| ShoutxError::failure("input is not valid UTF-8"))
}

pub(crate) fn read_value(
    value: Option<&std::ffi::OsString>,
    context: &mut impl crate::provider::Context,
    missing_operand: &'static str,
) -> Result<Vec<u8>, ShoutxError> {
    match value {
        Some(value) => Ok(os_bytes(value)?.to_vec()),
        None => context.read_stdin(missing_operand),
    }
}
