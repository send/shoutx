mod name;
mod normalize;
mod record;

use crate::{cli::WriteRequest, error::ShoutxError, input::VALUE_LIMIT};

pub fn validate_request(request: &WriteRequest) -> Result<(), ShoutxError> {
    name::validate(request.destination, &request.name)?;
    if let crate::cli::LineMode::Join(separator) = &request.mode {
        normalize::validate_separator(separator)?;
    }
    Ok(())
}

pub fn encode(request: WriteRequest, value: Vec<u8>) -> Result<Vec<u8>, ShoutxError> {
    validate_request(&request)?;
    if value.len() > VALUE_LIMIT {
        return Err(ShoutxError::failure("value exceeds size limit"));
    }
    std::str::from_utf8(&value).map_err(|_| ShoutxError::failure("value is not valid UTF-8"))?;
    if value.contains(&0) {
        return Err(ShoutxError::failure("value contains NUL"));
    }
    let name = name::validate(request.destination, &request.name)?;
    let normalized = normalize::apply(request.mode, value)?;
    record::single_line(name, normalized)
}
