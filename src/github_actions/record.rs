use crate::{
    error::ShoutxError,
    github_actions::{RandomSource, TargetOs},
};

const DELIMITER_PREFIX: &[u8] = b"SHOUTX_";
const RANDOM_BYTES: usize = 16;
const MAX_DELIMITER_ATTEMPTS: usize = 128;

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

pub fn multiline(
    name: Vec<u8>,
    value: Vec<u8>,
    target_os: TargetOs,
    random: &mut impl RandomSource,
) -> Result<Vec<u8>, ShoutxError> {
    let framing = if value.last() == Some(&b'\r') {
        match target_os {
            TargetOs::Windows => b"\r\n".as_slice(),
            TargetOs::Linux | TargetOs::MacOs => b"\n".as_slice(),
            TargetOs::Unknown => {
                return Err(ShoutxError::failure("unrecognized target runner OS"));
            }
        }
    } else {
        b"\n".as_slice()
    };
    let delimiter = choose_delimiter(&value, random)?;
    let capacity = name
        .len()
        .checked_add(2)
        .and_then(|n| n.checked_add(delimiter.len()))
        .and_then(|n| n.checked_add(1))
        .and_then(|n| n.checked_add(value.len()))
        .and_then(|n| n.checked_add(framing.len()))
        .and_then(|n| n.checked_add(delimiter.len()))
        .and_then(|n| n.checked_add(1))
        .ok_or_else(|| ShoutxError::failure("record size overflow"))?;
    let mut out = Vec::with_capacity(capacity);
    out.extend_from_slice(&name);
    out.extend_from_slice(b"<<");
    out.extend_from_slice(&delimiter);
    out.push(b'\n');
    out.extend_from_slice(&value);
    out.extend_from_slice(framing);
    out.extend_from_slice(&delimiter);
    out.push(b'\n');
    Ok(out)
}

fn choose_delimiter(value: &[u8], random: &mut impl RandomSource) -> Result<Vec<u8>, ShoutxError> {
    for _ in 0..MAX_DELIMITER_ATTEMPTS {
        let mut bytes = [0_u8; RANDOM_BYTES];
        random.fill(&mut bytes)?;
        let mut delimiter = Vec::with_capacity(DELIMITER_PREFIX.len() + RANDOM_BYTES * 2);
        delimiter.extend_from_slice(DELIMITER_PREFIX);
        for byte in bytes {
            delimiter.push(b"0123456789abcdef"[usize::from(byte >> 4)]);
            delimiter.push(b"0123456789abcdef"[usize::from(byte & 0x0f)]);
        }
        if !value
            .windows(delimiter.len())
            .any(|window| window == delimiter)
        {
            return Ok(delimiter);
        }
    }
    Err(ShoutxError::failure(
        "multiline delimiter attempts exhausted",
    ))
}
