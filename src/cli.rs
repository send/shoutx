use crate::{ShoutxError, input::os_bytes};
use std::ffi::{OsStr, OsString};

#[derive(Debug)]
pub enum Parsed<T> {
    Help,
    Version,
    Command(T),
}
impl<T> Parsed<T> {
    pub fn map<U>(self, f: impl FnOnce(T) -> U) -> Parsed<U> {
        match self {
            Self::Help => Parsed::Help,
            Self::Version => Parsed::Version,
            Self::Command(value) => Parsed::Command(f(value)),
        }
    }
}

pub(crate) struct CommandSpec<T> {
    pub name: &'static str,
    pub kind: T,
    pub section: usize,
    pub order: usize,
    pub usage: &'static [&'static str],
}

pub(crate) fn help_section<T>(
    out: &mut String,
    commands: &[CommandSpec<T>],
    section: usize,
    heading: &str,
) {
    out.push_str(heading);
    let mut commands: Vec<_> = commands.iter().filter(|c| c.section == section).collect();
    commands.sort_by_key(|c| c.order);
    for command in commands {
        for usage in command.usage {
            out.push_str("  shoutx ");
            out.push_str(command.name);
            out.push_str(usage);
            out.push('\n');
        }
    }
}

// The caller selects when to reject an invalid first operand; this preserves
// each command's validation precedence without naming providers here.
pub(crate) enum InvalidOperandEncoding {
    Deferred,
    Immediate,
}

#[cfg(unix)]
pub(crate) fn strip_os_prefix(value: &OsStr, prefix: &[u8]) -> Option<OsString> {
    use std::os::unix::ffi::{OsStrExt, OsStringExt};
    value
        .as_bytes()
        .strip_prefix(prefix)
        .map(|rest| OsString::from_vec(rest.to_vec()))
}

#[cfg(unix)]
pub(crate) fn starts_with_ascii_dash(value: &OsStr) -> bool {
    use std::os::unix::ffi::OsStrExt;
    value.as_bytes().first() == Some(&b'-')
}

#[cfg(windows)]
pub(crate) fn strip_os_prefix(value: &OsStr, prefix: &[u8]) -> Option<OsString> {
    use std::os::windows::ffi::{OsStrExt, OsStringExt};
    let wide: Vec<u16> = value.encode_wide().collect();
    let prefix: Vec<u16> = prefix.iter().map(|byte| u16::from(*byte)).collect();
    wide.strip_prefix(&prefix[..]).map(OsString::from_wide)
}

#[cfg(windows)]
pub(crate) fn starts_with_ascii_dash(value: &OsStr) -> bool {
    use std::os::windows::ffi::OsStrExt;
    value.encode_wide().next() == Some(u16::from(b'-'))
}

pub(crate) fn parse_value(
    tokens: Vec<OsString>,
    encoding: InvalidOperandEncoding,
) -> Result<Parsed<Option<OsString>>, ShoutxError> {
    let mut options = true;
    let mut value = None;
    for token in tokens {
        let token_text = token.to_str();
        if matches!(encoding, InvalidOperandEncoding::Immediate)
            && value.is_none()
            && token_text.is_none()
        {
            os_bytes(&token)?;
        }
        if value.is_none() && options && token_text == Some("--") {
            options = false;
            continue;
        }
        if value.is_none() && options && token_text == Some("--help") {
            return Ok(Parsed::Help);
        }
        if value.is_none() && options && token_text == Some("--version") {
            return Ok(Parsed::Version);
        }
        if value.is_none() && options && starts_with_ascii_dash(&token) {
            return Err(ShoutxError::usage("unknown option"));
        }
        if value.is_some() {
            return Err(ShoutxError::usage("too many operands"));
        }
        value = Some(token);
    }
    Ok(Parsed::Command(value))
}
pub(crate) fn parse_empty(
    tokens: Vec<OsString>,
    error: &'static str,
) -> Result<Parsed<()>, ShoutxError> {
    match tokens.first().and_then(|token| token.to_str()) {
        Some("--help") => Ok(Parsed::Help),
        Some("--version") => Ok(Parsed::Version),
        _ if tokens.is_empty() || (tokens.len() == 1 && tokens[0] == "--") => {
            Ok(Parsed::Command(()))
        }
        _ => Err(ShoutxError::usage(error)),
    }
}

pub fn command_names() -> impl Iterator<Item = &'static str> {
    crate::provider::command_names()
}
pub fn parse(args: Vec<OsString>) -> Result<Parsed<crate::provider::Invocation>, ShoutxError> {
    let mut args = args.into_iter();
    let command = args
        .next()
        .ok_or_else(|| ShoutxError::usage("missing command"))?;
    let command = command
        .to_str()
        .ok_or_else(|| ShoutxError::usage("command line contains invalid UTF-8"))?;
    match command {
        "--help" => Ok(Parsed::Help),
        "--version" => Ok(Parsed::Version),
        _ => crate::provider::parse(command, args.collect()),
    }
}
