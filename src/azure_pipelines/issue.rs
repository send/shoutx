use super::{
    record::record,
    request::{Issue, Severity},
    validation::validate_text,
};
use crate::{
    ShoutxError,
    input::{VALUE_LIMIT, os_bytes},
};
use std::ffi::OsString;

fn number(value: &OsString) -> Result<Vec<u8>, ShoutxError> {
    let bytes = os_bytes(value)?;
    if bytes.is_empty() || bytes.len() > 10 || !bytes.iter().all(u8::is_ascii_digit) {
        return Err(ShoutxError::failure("invalid Azure location number"));
    }
    let value = bytes.iter().try_fold(0u32, |n, b| {
        n.checked_mul(10)?.checked_add(u32::from(b - b'0'))
    });
    match value {
        Some(value @ 1..=2_147_483_647) => Ok(value.to_string().into_bytes()),
        _ => Err(ShoutxError::failure("invalid Azure location number")),
    }
}

pub fn encode_issue(request: &Issue, message: &[u8]) -> Result<Vec<u8>, ShoutxError> {
    validate_text(message, VALUE_LIMIT, false)?;
    if request.line.is_some() && request.file.is_none()
        || request.column.is_some() && request.line.is_none()
    {
        return Err(ShoutxError::failure(
            "Azure location fields require their parent",
        ));
    }
    let line = request.line.as_ref().map(number).transpose()?;
    let column = request.column.as_ref().map(number).transpose()?;
    let mut properties: Vec<(&[u8], &[u8])> = vec![(
        b"type",
        match request.severity {
            Severity::Warning => b"warning",
            Severity::Error => b"error",
        },
    )];
    for (field, limit) in [(request.file.as_ref(), 4096), (request.code.as_ref(), 255)] {
        if let Some(field) = field {
            validate_text(os_bytes(field)?, limit, false)?;
        }
    }
    if let Some(file) = request.file.as_ref() {
        properties.push((b"sourcepath", os_bytes(file)?));
    }
    if let Some(line) = line.as_ref() {
        properties.push((b"linenumber", line));
    }
    if let Some(column) = column.as_ref() {
        properties.push((b"columnnumber", column));
    }
    if let Some(code) = request.code.as_ref() {
        properties.push((b"code", os_bytes(code)?));
    }
    record(b"task.logissue", &properties, message)
}
