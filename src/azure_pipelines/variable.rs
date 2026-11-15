use super::{
    record::{RECORD_LIMIT, append, record},
    request::Variable,
    validation::validate_text,
};
use crate::{
    ShoutxError,
    input::{VALUE_LIMIT, os_bytes},
};

pub fn validate_variable(request: &Variable) -> Result<(), ShoutxError> {
    let name = os_bytes(&request.name)?;
    validate_text(name, 255, false)?;
    if !(name[0].is_ascii_alphabetic() || name[0] == b'_')
        || !name
            .iter()
            .all(|b| b.is_ascii_alphanumeric() || matches!(b, b'_' | b'.'))
    {
        return Err(ShoutxError::failure("invalid Azure variable name"));
    }
    for prefix in [
        b"endpoint".as_slice(),
        b"input",
        b"secret",
        b"path",
        b"securefile",
    ] {
        if name
            .get(..prefix.len())
            .is_some_and(|start| start.eq_ignore_ascii_case(prefix))
        {
            return Err(ShoutxError::failure("reserved Azure variable prefix"));
        }
    }
    Ok(())
}

pub fn encode_variable(request: &Variable, value: &[u8]) -> Result<Vec<u8>, ShoutxError> {
    validate_variable(request)?;
    validate_text(value, VALUE_LIMIT, true)?;
    record(
        b"task.setvariable",
        &[
            (b"variable", os_bytes(&request.name)?),
            (b"isOutput", if request.output { b"true" } else { b"false" }),
            (
                b"isReadOnly",
                if request.read_only { b"true" } else { b"false" },
            ),
        ],
        value,
    )
}

pub fn encode_secret_variable(request: &Variable, value: &[u8]) -> Result<Vec<u8>, ShoutxError> {
    validate_variable(request)?;
    validate_text(value, VALUE_LIMIT, true)?;
    if value.len() > 16 * 1024 {
        return Err(ShoutxError::failure(
            "Azure secret value exceeds size limit",
        ));
    }
    if value.is_empty() {
        return Err(ShoutxError::failure("Azure secret value must not be empty"));
    }
    if value.iter().any(|b| matches!(b, b'\r' | b'\n')) {
        return Err(ShoutxError::failure(
            "Azure secret value contains a line boundary",
        ));
    }
    if value.windows(2).any(|pair| pair == b"$(") {
        return Err(ShoutxError::failure(
            "Azure secret value contains variable syntax",
        ));
    }
    let assignment = record(
        b"task.setvariable",
        &[
            (b"variable", os_bytes(&request.name)?),
            (b"isSecret", b"true"),
            (b"isOutput", if request.output { b"true" } else { b"false" }),
            (
                b"isReadOnly",
                if request.read_only { b"true" } else { b"false" },
            ),
        ],
        value,
    )?;
    // The Agent may report assignment rejection using the original command
    // line. Register both the original value and that line's data representation
    // before asking for assignment. Prepare everything before stdout is touched.
    let original_mask = record(b"task.setsecret", &[], value)?;
    let mut wire_value = Vec::new();
    append(&mut wire_value, value);
    let wire_mask = record(b"task.setsecret", &[], &wire_value)?;
    let size = original_mask
        .len()
        .checked_add(wire_mask.len())
        .and_then(|n| n.checked_add(assignment.len()))
        .filter(|n| *n <= RECORD_LIMIT)
        .ok_or_else(|| ShoutxError::failure("encoded Azure command exceeds size limit"))?;
    let mut out = Vec::with_capacity(size);
    out.extend_from_slice(&original_mask);
    out.extend_from_slice(&wire_mask);
    out.extend_from_slice(&assignment);
    Ok(out)
}
