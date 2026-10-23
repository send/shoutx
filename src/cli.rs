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
pub enum ArtifactRequest {
    File {
        path: Option<OsString>,
    },
    Oci {
        reference: OsString,
        digest: OsString,
    },
}

#[derive(Debug)]
pub struct MaskRequest {
    pub value: Option<OsString>,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum LogKind {
    Debug,
    Group,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum MatcherKind {
    AddFile,
    RemoveFile,
    RemoveOwner,
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
    AzurePath(PathRequest),
    AzureVariable(crate::azure_pipelines::Variable),
    AzureIssue(crate::azure_pipelines::Issue),
    Help,
    Version,
    Write(WriteRequest),
    WritePath(PathRequest),
    Artifact(ArtifactRequest),
    Mask(MaskRequest),
    Log {
        kind: LogKind,
        value: Option<OsString>,
    },
    EndGroup,
    Matcher {
        kind: MatcherKind,
        value: Option<OsString>,
    },
    Annotate(AnnotationRequest),
}

#[derive(Clone, Copy)]
enum Command {
    AzurePath,
    AzureVariable,
    AzureWarning,
    AzureError,
    AddMatcher,
    RemoveMatcher,
    Debug,
    Group,
    EndGroup,
    Artifacts,
    Output,
    Env,
    State,
    Path,
    Mask,
    Notice,
    Warning,
    Error,
}

const COMMANDS: &[(&str, Command)] = &[
    ("azure-pipelines:variable", Command::AzureVariable),
    ("azure-pipelines:warning", Command::AzureWarning),
    ("azure-pipelines:error", Command::AzureError),
    ("azure-pipelines:path", Command::AzurePath),
    ("github-actions:add-matcher", Command::AddMatcher),
    ("github-actions:remove-matcher", Command::RemoveMatcher),
    ("github-actions:debug", Command::Debug),
    ("github-actions:group", Command::Group),
    ("github-actions:endgroup", Command::EndGroup),
    ("github-actions:artifacts", Command::Artifacts),
    ("github-actions:output", Command::Output),
    ("github-actions:env", Command::Env),
    ("github-actions:state", Command::State),
    ("github-actions:path", Command::Path),
    ("github-actions:mask", Command::Mask),
    ("github-actions:notice", Command::Notice),
    ("github-actions:warning", Command::Warning),
    ("github-actions:error", Command::Error),
];

pub fn command_names() -> impl Iterator<Item = &'static str> {
    COMMANDS.iter().map(|(name, _)| *name)
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
    let command = COMMANDS
        .iter()
        .find_map(|(name, kind)| (*name == command).then_some(*kind))
        .ok_or_else(|| ShoutxError::usage("unknown command"))?;
    let destination = match command {
        Command::AzurePath => {
            return parse_path(it.collect()).map(|action| match action {
                Action::WritePath(request) => Action::AzurePath(request),
                other => other,
            });
        }
        Command::AzureVariable => return parse_azure_variable(it.collect()),
        Command::AzureWarning => {
            return parse_azure_issue(crate::azure_pipelines::Severity::Warning, it.collect());
        }
        Command::AzureError => {
            return parse_azure_issue(crate::azure_pipelines::Severity::Error, it.collect());
        }
        Command::AddMatcher => return parse_matcher(MatcherKind::AddFile, it.collect()),
        Command::RemoveMatcher => return parse_remove_matcher(it.collect()),
        Command::Debug => return parse_log(LogKind::Debug, it.collect()),
        Command::Group => return parse_log(LogKind::Group, it.collect()),
        Command::EndGroup => return parse_endgroup(it.collect()),
        Command::Artifacts => return parse_artifacts(it.collect()),
        Command::Output => Destination::Output,
        Command::Env => Destination::Env,
        Command::State => Destination::State,
        Command::Path => return parse_path(it.collect()),
        Command::Mask => return parse_mask(it.collect()),
        Command::Notice => return parse_annotation(AnnotationSeverity::Notice, it.collect()),
        Command::Warning => return parse_annotation(AnnotationSeverity::Warning, it.collect()),
        Command::Error => return parse_annotation(AnnotationSeverity::Error, it.collect()),
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

fn parse_azure_variable(tokens: Vec<OsString>) -> Result<Action, ShoutxError> {
    let mut output = false;
    let mut read_only = false;
    let mut options = true;
    let mut it = tokens.into_iter();
    let name = loop {
        let token = it
            .next()
            .ok_or_else(|| ShoutxError::usage("missing NAME"))?;
        if options {
            match token.to_str() {
                Some("--help") => return Ok(Action::Help),
                Some("--version") => return Ok(Action::Version),
                Some("--") => {
                    options = false;
                    continue;
                }
                Some("--output" | "--read-only") => {
                    let flag = if token == "--output" {
                        &mut output
                    } else {
                        &mut read_only
                    };
                    if *flag {
                        return Err(ShoutxError::usage("duplicate Azure option"));
                    }
                    *flag = true;
                    continue;
                }
                _ if starts_with_ascii_dash(&token) => {
                    return Err(ShoutxError::usage("unknown option"));
                }
                _ => {}
            }
        }
        break token;
    };
    let value = it.next();
    if it.next().is_some() {
        return Err(ShoutxError::usage("too many operands"));
    }
    Ok(Action::AzureVariable(crate::azure_pipelines::Variable {
        name,
        output,
        read_only,
        value,
    }))
}

fn parse_azure_issue(
    severity: crate::azure_pipelines::Severity,
    tokens: Vec<OsString>,
) -> Result<Action, ShoutxError> {
    let mut request = crate::azure_pipelines::Issue {
        severity,
        file: None,
        line: None,
        column: None,
        code: None,
        message: None,
    };
    let mut options = true;
    let mut it = tokens.into_iter();
    while let Some(token) = it.next() {
        if request.message.is_some() {
            return Err(ShoutxError::usage("too many operands"));
        }
        if options {
            let field = match token.to_str() {
                Some("--help") => return Ok(Action::Help),
                Some("--version") => return Ok(Action::Version),
                Some("--") => {
                    options = false;
                    continue;
                }
                Some("--file") => Some(&mut request.file),
                Some("--line") => Some(&mut request.line),
                Some("--column") => Some(&mut request.column),
                Some("--code") => Some(&mut request.code),
                _ => None,
            };
            if let Some(field) = field {
                if field.is_some() {
                    return Err(ShoutxError::usage("duplicate Azure option"));
                }
                *field = Some(
                    it.next()
                        .ok_or_else(|| ShoutxError::usage("missing Azure option operand"))?,
                );
                continue;
            }
            if starts_with_ascii_dash(&token) {
                return Err(ShoutxError::usage("unknown option"));
            }
        }
        request.message = Some(token);
    }
    Ok(Action::AzureIssue(request))
}

fn parse_log(kind: LogKind, tokens: Vec<OsString>) -> Result<Action, ShoutxError> {
    // Only acquisition grammar is shared; mask validation is not invoked here.
    match parse_mask(tokens)? {
        Action::Mask(MaskRequest { value }) => Ok(Action::Log { kind, value }),
        action => Ok(action),
    }
}

fn parse_matcher(kind: MatcherKind, tokens: Vec<OsString>) -> Result<Action, ShoutxError> {
    // Share only the single-value grammar, never mask acceptance rules.
    match parse_mask(tokens)? {
        Action::Mask(MaskRequest { value }) => Ok(Action::Matcher { kind, value }),
        action => Ok(action),
    }
}

fn parse_remove_matcher(tokens: Vec<OsString>) -> Result<Action, ShoutxError> {
    let mut tokens = tokens.into_iter();
    let mode = tokens.next();
    let kind = match mode.as_deref().and_then(OsStr::to_str) {
        Some("--help") => return Ok(Action::Help),
        Some("--version") => return Ok(Action::Version),
        Some("owner") => MatcherKind::RemoveOwner,
        Some("file") => MatcherKind::RemoveFile,
        _ => {
            return Err(ShoutxError::usage(
                "missing or unknown matcher removal mode",
            ));
        }
    };
    parse_matcher(kind, tokens.collect())
}

fn parse_endgroup(tokens: Vec<OsString>) -> Result<Action, ShoutxError> {
    match tokens.first().and_then(|token| token.to_str()) {
        Some("--help") => Ok(Action::Help),
        Some("--version") => Ok(Action::Version),
        _ if tokens.is_empty() || (tokens.len() == 1 && tokens[0] == "--") => Ok(Action::EndGroup),
        _ => Err(ShoutxError::usage("endgroup takes no operands")),
    }
}

fn parse_artifacts(tokens: Vec<OsString>) -> Result<Action, ShoutxError> {
    let variant = tokens.first().and_then(|t| t.to_str());
    match variant {
        Some("--help") => return Ok(Action::Help),
        Some("--version") => return Ok(Action::Version),
        Some("file" | "oci") => {}
        _ => return Err(ShoutxError::usage("missing or unknown artifact variant")),
    }
    let mut operands = Vec::new();
    let mut options = true;
    for token in tokens.iter().skip(1) {
        if options {
            match token.to_str() {
                Some("--help") => return Ok(Action::Help),
                Some("--version") => return Ok(Action::Version),
                Some("--") => {
                    options = false;
                    continue;
                }
                _ if starts_with_ascii_dash(token) => {
                    return Err(ShoutxError::usage("unknown option"));
                }
                _ => options = false,
            }
        }
        operands.push(token.clone());
    }
    match (variant, operands.len()) {
        (Some("file"), 0..=1) => Ok(Action::Artifact(ArtifactRequest::File {
            path: operands.pop(),
        })),
        (Some("oci"), 2) => {
            let digest = operands.pop().unwrap();
            let reference = operands.pop().unwrap();
            Ok(Action::Artifact(ArtifactRequest::Oci { reference, digest }))
        }
        _ => Err(ShoutxError::usage("wrong number of artifact operands")),
    }
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
