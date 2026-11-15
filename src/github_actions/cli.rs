use super::request::*;
use crate::{
    ShoutxError,
    cli::{
        CommandSpec, InvalidOperandEncoding, Parsed, parse_empty, parse_value,
        starts_with_ascii_dash, strip_os_prefix,
    },
    input::os_bytes,
};
use std::ffi::{OsStr, OsString};
type Action = Parsed<Request>;
#[derive(Clone, Copy)]
enum Command {
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

const COMMANDS: &[CommandSpec<Command>] = &[
    CommandSpec {
        name: "github-actions:add-matcher",
        kind: Command::AddMatcher,
        section: 2,
        order: 0,
        usage: &[" [PATH]"],
    },
    CommandSpec {
        name: "github-actions:remove-matcher",
        kind: Command::RemoveMatcher,
        section: 2,
        order: 1,
        usage: &[" owner [OWNER]", " file [PATH]"],
    },
    CommandSpec {
        name: "github-actions:debug",
        kind: Command::Debug,
        section: 2,
        order: 2,
        usage: &[" [MESSAGE]"],
    },
    CommandSpec {
        name: "github-actions:group",
        kind: Command::Group,
        section: 2,
        order: 3,
        usage: &[" [TITLE]"],
    },
    CommandSpec {
        name: "github-actions:endgroup",
        kind: Command::EndGroup,
        section: 2,
        order: 4,
        usage: &[""],
    },
    CommandSpec {
        name: "github-actions:artifacts",
        kind: Command::Artifacts,
        section: 1,
        order: 0,
        usage: &[" file [PATH]", " oci REFERENCE DIGEST"],
    },
    CommandSpec {
        name: "github-actions:output",
        kind: Command::Output,
        section: 0,
        order: 0,
        usage: &[
            " [--first-line | --join-lines | --join-lines-with STRING | --multiline] NAME [VALUE]",
        ],
    },
    CommandSpec {
        name: "github-actions:env",
        kind: Command::Env,
        section: 0,
        order: 1,
        usage: &[
            "    [--first-line | --join-lines | --join-lines-with STRING | --multiline] NAME [VALUE]",
        ],
    },
    CommandSpec {
        name: "github-actions:state",
        kind: Command::State,
        section: 0,
        order: 2,
        usage: &[
            "  [--first-line | --join-lines | --join-lines-with STRING | --multiline] NAME [VALUE]",
        ],
    },
    CommandSpec {
        name: "github-actions:path",
        kind: Command::Path,
        section: 0,
        order: 3,
        usage: &["   [VALUE]"],
    },
    CommandSpec {
        name: "github-actions:mask",
        kind: Command::Mask,
        section: 2,
        order: 5,
        usage: &["   [VALUE]"],
    },
    CommandSpec {
        name: "github-actions:notice",
        kind: Command::Notice,
        section: 2,
        order: 6,
        usage: &[
            "  [--title TITLE] [--file FILE] [--line N] [--end-line N] [--column N] [--end-column N] [MESSAGE]",
        ],
    },
    CommandSpec {
        name: "github-actions:warning",
        kind: Command::Warning,
        section: 2,
        order: 7,
        usage: &[
            " [--title TITLE] [--file FILE] [--line N] [--end-line N] [--column N] [--end-column N] [MESSAGE]",
        ],
    },
    CommandSpec {
        name: "github-actions:error",
        kind: Command::Error,
        section: 2,
        order: 8,
        usage: &[
            "   [--title TITLE] [--file FILE] [--line N] [--end-line N] [--column N] [--end-column N] [MESSAGE]",
        ],
    },
];

pub(crate) fn command_names() -> impl Iterator<Item = &'static str> {
    COMMANDS.iter().map(|c| c.name)
}
pub(crate) fn parse(command: &str, tokens: Vec<OsString>) -> Result<Action, ShoutxError> {
    let command = COMMANDS
        .iter()
        .find(|c| c.name == command)
        .ok_or_else(|| ShoutxError::usage("unknown command"))?
        .kind;
    let it = tokens.into_iter();
    let destination = match command {
        Command::AddMatcher => return parse_matcher(MatcherKind::AddFile, it.collect()),
        Command::RemoveMatcher => return parse_remove_matcher(it.collect()),
        Command::Debug => return parse_log(LogKind::Debug, it.collect()),
        Command::Group => return parse_log(LogKind::Group, it.collect()),
        Command::EndGroup => {
            return parse_empty(it.collect(), "endgroup takes no operands")
                .map(|p| p.map(|()| Request::EndGroup));
        }
        Command::Artifacts => return parse_artifacts(it.collect()),
        Command::Output => Destination::Output,
        Command::Env => Destination::Env,
        Command::State => Destination::State,
        Command::Path => {
            return parse_value(it.collect(), InvalidOperandEncoding::Deferred)
                .map(|p| p.map(|value| Request::WritePath(PathRequest { value })));
        }
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
    Ok(Action::Command(Request::Write(WriteRequest {
        destination,
        mode,
        name,
        value,
    })))
}

fn parse_log(kind: LogKind, tokens: Vec<OsString>) -> Result<Action, ShoutxError> {
    Ok(parse_value(tokens, InvalidOperandEncoding::Deferred)?
        .map(|value| Request::Log { kind, value }))
}
fn parse_matcher(kind: MatcherKind, tokens: Vec<OsString>) -> Result<Action, ShoutxError> {
    Ok(parse_value(tokens, InvalidOperandEncoding::Deferred)?
        .map(|value| Request::Matcher { kind, value }))
}
fn parse_mask(tokens: Vec<OsString>) -> Result<Action, ShoutxError> {
    Ok(parse_value(tokens, InvalidOperandEncoding::Deferred)?
        .map(|value| Request::Mask(MaskRequest { value })))
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
        (Some("file"), 0..=1) => Ok(Action::Command(Request::Artifact(ArtifactRequest::File {
            path: operands.pop(),
        }))),
        (Some("oci"), 2) => {
            let digest = operands.pop().unwrap();
            let reference = operands.pop().unwrap();
            Ok(Action::Command(Request::Artifact(ArtifactRequest::Oci {
                reference,
                digest,
            })))
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
    Ok(Action::Command(Request::Annotate(request)))
}

pub(crate) fn help(out: &mut String) {
    crate::cli::help_section(out, COMMANDS, 0, "Usage:\n");
    out.push_str("  shoutx --help\n  shoutx --version\n");
    crate::cli::help_section(
        out,
        COMMANDS,
        1,
        "\nGitHub Actions artifact declarations:\n",
    );
    crate::cli::help_section(out, COMMANDS, 2, "\nGitHub Actions stdout commands:\n");
}
