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
