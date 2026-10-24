//! Typed Azure logging commands. No dependency on GitHub's boundary policy.
use std::ffi::OsString;

use crate::{ShoutxError, cli::os_bytes, input::VALUE_LIMIT};

const RECORD_LIMIT: usize = 8 * 1024 * 1024;

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

#[derive(Debug)]
pub struct Variable {
    pub name: OsString,
    pub output: bool,
    pub read_only: bool,
    pub value: Option<OsString>,
}

#[derive(Clone, Copy, Debug)]
pub enum Severity {
    Warning,
    Error,
}

#[derive(Debug)]
pub struct Issue {
    pub severity: Severity,
    pub file: Option<OsString>,
    pub line: Option<OsString>,
    pub column: Option<OsString>,
    pub code: Option<OsString>,
    pub message: Option<OsString>,
}

pub fn encode_path(value: &[u8]) -> Result<Vec<u8>, ShoutxError> {
    validate_path(value, cfg!(windows))?;
    record(b"task.prependpath", &[], value)
}

fn validate_path(value: &[u8], windows: bool) -> Result<(), ShoutxError> {
    validate_text(value, VALUE_LIMIT, false)?;
    if value.contains(&b'\r') || value.contains(&b'\n') {
        return Err(ShoutxError::failure("Azure path contains a line boundary"));
    }
    if value.contains(&if windows { b';' } else { b':' }) {
        return Err(ShoutxError::failure(
            "Azure path contains the PATH separator",
        ));
    }
    let absolute = if windows {
        if value.contains(&b'"') {
            return Err(ShoutxError::failure("Azure path contains a double quote"));
        }
        windows_absolute(value)
    } else {
        value.starts_with(b"/")
    };
    if !absolute {
        return Err(ShoutxError::failure("Azure path is not fully qualified"));
    }
    Ok(())
}

fn windows_absolute(value: &[u8]) -> bool {
    let separator = |b: u8| matches!(b, b'/' | b'\\');
    if value.len() >= 3 && value[0].is_ascii_alphabetic() && value[1] == b':' && separator(value[2])
    {
        return true;
    }
    if value.len() < 5 || !separator(value[0]) || !separator(value[1]) {
        return false;
    }
    let mut components = value[2..].split(|b| separator(*b));
    let valid = |part: &[u8]| !part.is_empty() && part != b"." && part != b"?";
    components.next().is_some_and(valid) && components.next().is_some_and(valid)
}

fn validate_text(bytes: &[u8], limit: usize, empty: bool) -> Result<(), ShoutxError> {
    if bytes.len() > limit {
        return Err(ShoutxError::failure("Azure field exceeds size limit"));
    }
    std::str::from_utf8(bytes)
        .map_err(|_| ShoutxError::failure("Azure field is not valid UTF-8"))?;
    if bytes.contains(&0) {
        return Err(ShoutxError::failure("Azure field contains NUL"));
    }
    if !empty && bytes.is_empty() {
        return Err(ShoutxError::failure("Azure field must not be empty"));
    }
    Ok(())
}

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

fn escaped(byte: u8) -> Option<&'static [u8]> {
    match byte {
        b'%' => Some(b"%AZP25"),
        b'\r' => Some(b"%0D"),
        b'\n' => Some(b"%0A"),
        b';' => Some(b"%3B"),
        b']' => Some(b"%5D"),
        _ => None,
    }
}

fn record(
    command: &[u8],
    properties: &[(&[u8], &[u8])],
    data: &[u8],
) -> Result<Vec<u8>, ShoutxError> {
    // Fixed syntax + each property key, '=' and ';' + escaped values.
    let mut size =
        Some(b"##vso[".len() + command.len() + b"]\n".len() + usize::from(!properties.is_empty()));
    for (key, value) in properties {
        size = size.and_then(|n| n.checked_add(key.len() + 2));
        for &byte in *value {
            size = size.and_then(|n| n.checked_add(escaped(byte).map_or(1, <[u8]>::len)));
        }
    }
    for &byte in data {
        size = size.and_then(|n| n.checked_add(escaped(byte).map_or(1, <[u8]>::len)));
    }
    let size = size
        .filter(|n| *n <= RECORD_LIMIT)
        .ok_or_else(|| ShoutxError::failure("encoded Azure command exceeds size limit"))?;
    let mut out = Vec::with_capacity(size);
    out.extend_from_slice(b"##vso[");
    out.extend_from_slice(command);
    if !properties.is_empty() {
        out.push(b' ');
    }
    for (key, value) in properties {
        out.extend_from_slice(key);
        out.push(b'=');
        append(&mut out, value);
        out.push(b';');
    }
    out.push(b']');
    append(&mut out, data);
    out.push(b'\n');
    debug_assert_eq!(size, out.len());
    Ok(out)
}

fn append(out: &mut Vec<u8>, bytes: &[u8]) {
    for &byte in bytes {
        match escaped(byte) {
            Some(replacement) => out.extend_from_slice(replacement),
            None => out.push(byte),
        }
    }
}

#[cfg(test)]
mod path_tests {
    use super::validate_path;

    #[test]
    fn dialects_are_explicit_and_do_not_normalize() {
        for path in ["/", "/ space ", "/a;]", "/a\"b", "/ends\\", "/a/../b"] {
            assert!(validate_path(path.as_bytes(), false).is_ok(), "{path}");
        }
        for path in [
            "",
            "relative",
            " /x",
            "\u{feff}/x",
            "/a:/b",
            "/a\n",
            "/a\r",
            "/a\0",
        ] {
            assert!(validate_path(path.as_bytes(), false).is_err());
        }
        for path in [
            "C:\\",
            "z:/tools",
            "C:\\α😀",
            "\\\\host\\share",
            "//host/share/x",
        ] {
            assert!(validate_path(path.as_bytes(), true).is_ok(), "{path}");
        }
        for path in [
            "",
            "C:relative",
            "\\rooted",
            "/rooted",
            "\\\\host",
            "//host/",
            "///share",
            "//./share",
            "//?/share",
            "//host/.",
            "//host/?",
            "\\\\?\\C:\\x",
            "C:\\x;D:\\y",
            "C:\\x\"",
            "C:\\x\n",
            "C:\\x\r",
            "C:\\x\0",
        ] {
            assert!(validate_path(path.as_bytes(), true).is_err(), "{path}");
        }
    }
}
