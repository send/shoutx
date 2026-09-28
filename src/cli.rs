use std::ffi::{OsStr, OsString};

use crate::error::ShoutxError;

#[cfg(unix)]
fn strip_os_prefix(value: &OsStr, prefix: &[u8]) -> Option<OsString> {
    use std::os::unix::ffi::{OsStrExt, OsStringExt};
    value
        .as_bytes()
        .strip_prefix(prefix)
        .map(|rest| OsString::from_vec(rest.to_vec()))
}

#[cfg(unix)]
fn starts_with_ascii_dash(value: &OsStr) -> bool {
    use std::os::unix::ffi::OsStrExt;
    value.as_bytes().first() == Some(&b'-')
}

#[cfg(windows)]
fn strip_os_prefix(value: &OsStr, prefix: &[u8]) -> Option<OsString> {
    use std::os::windows::ffi::{OsStrExt, OsStringExt};
    let wide: Vec<u16> = value.encode_wide().collect();
    let prefix: Vec<u16> = prefix.iter().map(|byte| u16::from(*byte)).collect();
    wide.strip_prefix(&prefix[..]).map(OsString::from_wide)
}

#[cfg(windows)]
fn starts_with_ascii_dash(value: &OsStr) -> bool {
    use std::os::windows::ffi::OsStrExt;
    value.encode_wide().next() == Some(u16::from(b'-'))
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum Destination {
    Output,
    Env,
    State,
}

#[derive(Debug, Eq, PartialEq)]
pub enum LineMode {
    Default,
    FirstLine,
    Join(Vec<u8>),
    Multiline,
}

#[derive(Debug)]
pub struct WriteRequest {
    pub destination: Destination,
    pub mode: LineMode,
    pub name: OsString,
    pub value: Option<OsString>,
}

#[derive(Debug)]
pub struct PathRequest {
    pub value: Option<OsString>,
}

#[derive(Debug)]
pub struct MaskRequest {
    pub value: Option<OsString>,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum AnnotationSeverity {
    Notice,
    Warning,
    Error,
}

#[derive(Debug)]
pub struct AnnotationRequest {
    pub severity: AnnotationSeverity,
    pub title: Option<OsString>,
    pub file: Option<OsString>,
    pub line: Option<OsString>,
    pub end_line: Option<OsString>,
    pub column: Option<OsString>,
    pub end_column: Option<OsString>,
    pub message: Option<OsString>,
}

#[derive(Debug)]
pub enum Action {
    Help,
    Version,
    Write(WriteRequest),
    WritePath(PathRequest),
    Mask(MaskRequest),
    Annotate(AnnotationRequest),
}

fn text(value: &OsStr) -> Result<&str, ShoutxError> {
    value
        .to_str()
        .ok_or_else(|| ShoutxError::usage("command line contains invalid UTF-8"))
}

pub fn parse(args: Vec<OsString>) -> Result<Action, ShoutxError> {
    let mut it = args.into_iter();
    let command = it
        .next()
        .ok_or_else(|| ShoutxError::usage("missing command"))?;
    let command = text(&command)?;
    if command == "--help" {
        return Ok(Action::Help);
    }
    if command == "--version" {
        return Ok(Action::Version);
    }
    if command == "github-actions:path" {
        return parse_path(it.collect());
    }
    if command == "github-actions:mask" {
        return parse_mask(it.collect());
    }
    if let Some(severity) = match command {
        "github-actions:notice" => Some(AnnotationSeverity::Notice),
        "github-actions:warning" => Some(AnnotationSeverity::Warning),
        "github-actions:error" => Some(AnnotationSeverity::Error),
        _ => None,
    } {
        return parse_annotation(severity, it.collect());
    }
    let destination = match command {
        "github-actions:output" => Destination::Output,
        "github-actions:env" => Destination::Env,
        "github-actions:state" => Destination::State,
        _ => return Err(ShoutxError::usage("unknown command")),
    };

    let tokens: Vec<OsString> = it.collect();
    let mut i = 0;
    let mut mode = LineMode::Default;
    let mut mode_set = false;
    let mut join_separator = None;
    let mut options = true;
    let name;
    loop {
        let token = tokens
            .get(i)
            .ok_or_else(|| ShoutxError::usage("missing NAME"))?;
        let token_text = token.to_str();
        if options && token_text == Some("--") {
            options = false;
            i += 1;
            continue;
        }
        if options && token_text == Some("--help") {
            return Ok(Action::Help);
        }
        if options && token_text == Some("--version") {
            return Ok(Action::Version);
        }
        if options && token_text == Some("--multiline") {
            if mode_set {
                return Err(ShoutxError::usage("line modes are mutually exclusive"));
            }
            mode = LineMode::Multiline;
            mode_set = true;
            i += 1;
            continue;
        }
        if options {
            if let Some(separator) = strip_os_prefix(token, b"--join-lines-with=") {
                if mode_set {
                    return Err(ShoutxError::usage("line modes are mutually exclusive"));
                }
                mode = LineMode::Join(Vec::new());
                join_separator = Some(separator);
                mode_set = true;
                i += 1;
                continue;
            }
        }
        if options && (token_text == Some("--first-line") || token_text == Some("--join-lines")) {
            if mode_set {
                return Err(ShoutxError::usage("line modes are mutually exclusive"));
            }
            mode = if token_text == Some("--first-line") {
                LineMode::FirstLine
            } else {
                LineMode::Join(b" ".to_vec())
            };
            mode_set = true;
            i += 1;
            continue;
        }
        if options && token_text == Some("--join-lines-with") {
            if mode_set {
                return Err(ShoutxError::usage("line modes are mutually exclusive"));
            }
            let separator = tokens
                .get(i + 1)
                .ok_or_else(|| ShoutxError::usage("missing join separator"))?;
            mode = LineMode::Join(Vec::new());
            join_separator = Some(separator.clone());
            mode_set = true;
            i += 2;
            continue;
        }
        if options && starts_with_ascii_dash(token) {
            return Err(ShoutxError::usage("unknown option"));
        }
        name = token.clone();
        i += 1;
        break;
    }
    let value = match tokens.len() - i {
        0 => None,
        1 => Some(tokens[i].clone()),
        _ => return Err(ShoutxError::usage("too many operands")),
    };
    if let Some(separator) = join_separator {
        mode = LineMode::Join(os_bytes(&separator)?.to_vec());
    }
    Ok(Action::Write(WriteRequest {
        destination,
        mode,
        name,
        value,
    }))
}

fn parse_annotation(
    severity: AnnotationSeverity,
    tokens: Vec<OsString>,
) -> Result<Action, ShoutxError> {
    let mut request = AnnotationRequest {
        severity,
        title: None,
        file: None,
        line: None,
        end_line: None,
        column: None,
        end_column: None,
        message: None,
    };
    let mut options = true;
    let mut i = 0;
    while i < tokens.len() {
        let token = &tokens[i];
        let token_text = token.to_str();
        if request.message.is_none() && options && token_text == Some("--") {
            options = false;
            i += 1;
            continue;
        }
        if request.message.is_none() && options && token_text == Some("--help") {
            return Ok(Action::Help);
        }
        if request.message.is_none() && options && token_text == Some("--version") {
            return Ok(Action::Version);
        }
        let field = if request.message.is_none() && options {
            match token_text {
                Some("--title") => Some(&mut request.title),
                Some("--file") => Some(&mut request.file),
                Some("--line") => Some(&mut request.line),
                Some("--end-line") => Some(&mut request.end_line),
                Some("--column") => Some(&mut request.column),
                Some("--end-column") => Some(&mut request.end_column),
                _ => None,
            }
        } else {
            None
        };
        if let Some(field) = field {
            if field.is_some() {
                return Err(ShoutxError::usage("duplicate annotation option"));
            }
            let operand = tokens
                .get(i + 1)
                .ok_or_else(|| ShoutxError::usage("missing annotation option operand"))?;
            *field = Some(operand.clone());
            i += 2;
            continue;
        }
        if request.message.is_none() && options && starts_with_ascii_dash(token) {
            return Err(ShoutxError::usage("unknown option"));
        }
        if request.message.is_some() {
            return Err(ShoutxError::usage("too many operands"));
        }
        request.message = Some(token.clone());
        i += 1;
    }
    Ok(Action::Annotate(request))
}

fn parse_mask(tokens: Vec<OsString>) -> Result<Action, ShoutxError> {
    let mut options = true;
    let mut value = None;
    for token in tokens {
        let token_text = token.to_str();
        if value.is_none() && options && token_text == Some("--") {
            options = false;
            continue;
        }
        if value.is_none() && options && token_text == Some("--help") {
            return Ok(Action::Help);
        }
        if value.is_none() && options && token_text == Some("--version") {
            return Ok(Action::Version);
        }
        if value.is_none() && options && starts_with_ascii_dash(&token) {
            return Err(ShoutxError::usage("unknown option"));
        }
        if value.is_some() {
            return Err(ShoutxError::usage("too many operands"));
        }
        value = Some(token);
    }
    Ok(Action::Mask(MaskRequest { value }))
}

fn parse_path(tokens: Vec<OsString>) -> Result<Action, ShoutxError> {
    let mut options = true;
    let mut value = None;
    for token in tokens {
        let token_text = token.to_str();
        if value.is_none() && options && token_text == Some("--") {
            options = false;
            continue;
        }
        if value.is_none() && options && token_text == Some("--help") {
            return Ok(Action::Help);
        }
        if value.is_none() && options && token_text == Some("--version") {
            return Ok(Action::Version);
        }
        if value.is_none() && options && starts_with_ascii_dash(&token) {
            return Err(ShoutxError::usage("unknown option"));
        }
        if value.is_some() {
            return Err(ShoutxError::usage("too many operands"));
        }
        value = Some(token);
    }
    Ok(Action::WritePath(PathRequest { value }))
}

pub fn os_bytes(value: &OsStr) -> Result<&[u8], ShoutxError> {
    value
        .to_str()
        .map(str::as_bytes)
        .ok_or_else(|| ShoutxError::failure("input is not valid UTF-8"))
}
