use crate::{error::ShoutxError, input::VALUE_LIMIT};

use super::TargetOs;

pub fn encode(mut value: Vec<u8>, target_os: TargetOs) -> Result<Vec<u8>, ShoutxError> {
    if value.len() > VALUE_LIMIT {
        return Err(ShoutxError::failure("value exceeds size limit"));
    }
    std::str::from_utf8(&value).map_err(|_| ShoutxError::failure("value is not valid UTF-8"))?;
    if value.contains(&0) {
        return Err(ShoutxError::failure("value contains NUL"));
    }
    strip_final_boundary(&mut value);
    if value.is_empty() {
        return Err(ShoutxError::failure("path is empty"));
    }
    if value.contains(&b'\r') || value.contains(&b'\n') {
        return Err(ShoutxError::failure("path contains a line boundary"));
    }
    if value.starts_with(b"\xef\xbb\xbf") {
        return Err(ShoutxError::failure("path begins with U+FEFF"));
    }
    if value.contains(&b'"') {
        return Err(ShoutxError::failure("path contains a double quote"));
    }

    match target_os {
        TargetOs::Linux | TargetOs::MacOs => validate_posix(&value)?,
        TargetOs::Windows => validate_windows(&value)?,
        TargetOs::Unknown => return Err(ShoutxError::failure("unknown target runner OS")),
    }
    value.push(b'\n');
    Ok(value)
}

fn strip_final_boundary(value: &mut Vec<u8>) {
    if value.ends_with(b"\r\n") {
        value.truncate(value.len() - 2);
    } else if value.ends_with(b"\r") || value.ends_with(b"\n") {
        value.pop();
    }
}

fn validate_posix(value: &[u8]) -> Result<(), ShoutxError> {
    if !value.starts_with(b"/") {
        return Err(ShoutxError::failure("path is not fully qualified"));
    }
    if value.contains(&b':') {
        return Err(ShoutxError::failure("path contains the PATH separator"));
    }
    if value.ends_with(b"\\") {
        return Err(ShoutxError::failure("path ends in a backslash"));
    }
    Ok(())
}

fn validate_windows(value: &[u8]) -> Result<(), ShoutxError> {
    if value.contains(&b';') {
        return Err(ShoutxError::failure("path contains the PATH separator"));
    }
    if drive_absolute(value) || normal_unc(value) || verbatim(value) {
        Ok(())
    } else {
        Err(ShoutxError::failure("path is not fully qualified"))
    }
}

fn separator(byte: u8) -> bool {
    byte == b'/' || byte == b'\\'
}

fn drive_absolute(value: &[u8]) -> bool {
    value.len() >= 3 && value[0].is_ascii_alphabetic() && value[1] == b':' && separator(value[2])
}

fn normal_unc(value: &[u8]) -> bool {
    if value.len() < 5 || !separator(value[0]) || !separator(value[1]) || separator(value[2]) {
        return false;
    }
    let Some(server_end) = value[2..].iter().position(|byte| separator(*byte)) else {
        return false;
    };
    let server_end = server_end + 2;
    let server = &value[2..server_end];
    let rest = &value[server_end + 1..];
    let share_end = rest
        .iter()
        .position(|byte| separator(*byte))
        .unwrap_or(rest.len());
    let share = &rest[..share_end];
    !share.is_empty() && server != b"." && server != b"?" && share != b"." && share != b"?"
}

fn verbatim(value: &[u8]) -> bool {
    let Some(rest) = value.strip_prefix(b"\\\\?\\") else {
        return false;
    };
    if rest.len() >= 3 && rest[0].is_ascii_alphabetic() && rest[1] == b':' && rest[2] == b'\\' {
        return true;
    }
    let Some(rest) = rest.strip_prefix(b"UNC\\") else {
        return false;
    };
    let Some(server_end) = rest.iter().position(|byte| *byte == b'\\') else {
        return false;
    };
    let server = &rest[..server_end];
    let rest = &rest[server_end + 1..];
    let share_end = rest
        .iter()
        .position(|byte| *byte == b'\\')
        .unwrap_or(rest.len());
    let share = &rest[..share_end];
    !server.is_empty()
        && !share.is_empty()
        && server != b"."
        && server != b"?"
        && share != b"."
        && share != b"?"
}
