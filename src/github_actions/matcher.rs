use crate::{cli::MatcherKind, error::ShoutxError, input::VALUE_LIMIT};

pub fn encode(kind: MatcherKind, mut value: Vec<u8>) -> Result<Vec<u8>, ShoutxError> {
    if value.len() > VALUE_LIMIT {
        return Err(ShoutxError::failure("value exceeds size limit"));
    }
    std::str::from_utf8(&value).map_err(|_| ShoutxError::failure("value is not valid UTF-8"))?;
    if value.contains(&0) {
        return Err(ShoutxError::failure("value contains NUL"));
    }
    super::normalize::strip_final(&mut value);
    let text = std::str::from_utf8(&value)
        .map_err(|_| ShoutxError::failure("value is not valid UTF-8"))?;
    if text.is_empty() {
        return Err(ShoutxError::failure("matcher value is empty"));
    }
    let property = kind == MatcherKind::RemoveOwner;
    if property {
        if value.first() == Some(&b'=') {
            return Err(ShoutxError::failure("matcher owner begins with equals"));
        }
    } else if !super::stdout_guard::has_allowed_data_prefix(text) {
        return Err(ShoutxError::failure(
            "matcher path is outside the Unicode boundary policy",
        ));
    }
    let (prefix, suffix): (&[u8], &[u8]) = match kind {
        MatcherKind::AddFile => (b"::add-matcher::", b"\n"),
        MatcherKind::RemoveFile => (b"::remove-matcher::", b"\n"),
        // The final comma protects owner tails from property-region trim and
        // anchors the V2 separator. It decodes to no additional property.
        MatcherKind::RemoveOwner => (b"::remove-matcher owner=", b",::\n"),
    };
    let capacity = value
        .iter()
        .try_fold(prefix.len() + suffix.len(), |length, byte| {
            length.checked_add(
                if matches!(byte, b'%' | b'\r' | b'\n') || (property && matches!(byte, b':' | b','))
                {
                    3
                } else {
                    1
                },
            )
        })
        .ok_or_else(|| ShoutxError::failure("encoded matcher command exceeds size limit"))?;
    let mut output = Vec::with_capacity(capacity);
    output.extend_from_slice(prefix);
    for byte in value {
        match byte {
            b'%' => output.extend_from_slice(b"%25"),
            b'\r' => output.extend_from_slice(b"%0D"),
            b'\n' => output.extend_from_slice(b"%0A"),
            b':' if property => output.extend_from_slice(b"%3A"),
            b',' if property => output.extend_from_slice(b"%2C"),
            _ => output.push(byte),
        }
    }
    output.extend_from_slice(suffix);
    Ok(output)
}
