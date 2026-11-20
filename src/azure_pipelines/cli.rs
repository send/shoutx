use super::request::*;
use crate::{
    ShoutxError,
    cli::{
        CommandSpec, InvalidOperandEncoding, Parsed, parse_empty, parse_value,
        starts_with_ascii_dash,
    },
};
use std::ffi::OsString;
type Action = Parsed<Request>;
#[derive(Clone, Copy)]
enum Command {
    Summary,
    UploadFile,
    Debug,
    Group,
    EndGroup,
    BuildNumber,
    BuildTag,
    Mask,
    Variable,
    SecretVariable,
    Warning,
    Error,
    Path,
}

const COMMANDS: &[CommandSpec<Command>] = &[
    CommandSpec {
        name: "azure-pipelines:summary",
        kind: Command::Summary,
        section: 0,
        order: 0,
        usage: &[" [PATH]"],
    },
    CommandSpec {
        name: "azure-pipelines:uploadfile",
        kind: Command::UploadFile,
        section: 0,
        order: 1,
        usage: &[" [PATH]"],
    },
    CommandSpec {
        name: "azure-pipelines:debug",
        kind: Command::Debug,
        section: 0,
        order: 2,
        usage: &[" [MESSAGE]"],
    },
    CommandSpec {
        name: "azure-pipelines:group",
        kind: Command::Group,
        section: 0,
        order: 3,
        usage: &[" [TITLE]"],
    },
    CommandSpec {
        name: "azure-pipelines:endgroup",
        kind: Command::EndGroup,
        section: 0,
        order: 4,
        usage: &[""],
    },
    CommandSpec {
        name: "azure-pipelines:build-number",
        kind: Command::BuildNumber,
        section: 0,
        order: 11,
        usage: &[" [NUMBER]"],
    },
    CommandSpec {
        name: "azure-pipelines:build-tag",
        kind: Command::BuildTag,
        section: 0,
        order: 12,
        usage: &[" [TAG]"],
    },
    CommandSpec {
        name: "azure-pipelines:mask",
        kind: Command::Mask,
        section: 0,
        order: 10,
        usage: &[" [--each-line]"],
    },
    CommandSpec {
        name: "azure-pipelines:variable",
        kind: Command::Variable,
        section: 0,
        order: 5,
        usage: &[" [--output] [--read-only] NAME [VALUE]"],
    },
    CommandSpec {
        name: "azure-pipelines:secret-variable",
        kind: Command::SecretVariable,
        section: 0,
        order: 6,
        usage: &[" [--output] [--read-only] NAME"],
    },
    CommandSpec {
        name: "azure-pipelines:warning",
        kind: Command::Warning,
        section: 0,
        order: 7,
        usage: &[" [--file FILE] [--line N] [--column N] [--code CODE] [MESSAGE]"],
    },
    CommandSpec {
        name: "azure-pipelines:error",
        kind: Command::Error,
        section: 0,
        order: 8,
        usage: &["   [--file FILE] [--line N] [--column N] [--code CODE] [MESSAGE]"],
    },
    CommandSpec {
        name: "azure-pipelines:path",
        kind: Command::Path,
        section: 0,
        order: 9,
        usage: &[" [PATH]"],
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
    match command {
        Command::Summary | Command::UploadFile => Ok(parse_value(
            tokens,
            InvalidOperandEncoding::Immediate,
        )?
        .map(|value| Request::File {
            kind: if matches!(command, Command::Summary) {
                super::FileKind::Summary
            } else {
                super::FileKind::UploadFile
            },
            value,
        })),
        Command::Debug | Command::Group => {
            Ok(
                parse_value(tokens, InvalidOperandEncoding::Immediate)?.map(|value| Request::Log {
                    kind: if matches!(command, Command::Debug) {
                        super::LogKind::Debug
                    } else {
                        super::LogKind::Group
                    },
                    value,
                }),
            )
        }
        Command::EndGroup => {
            Ok(parse_empty(tokens, "endgroup takes no operands")?.map(|()| Request::EndGroup))
        }
        Command::BuildNumber | Command::BuildTag => Ok(parse_value(
            tokens,
            InvalidOperandEncoding::Immediate,
        )?
        .map(|value| Request::BuildMetadata {
            kind: if matches!(command, Command::BuildNumber) {
                super::BuildMetadata::Number
            } else {
                super::BuildMetadata::Tag
            },
            value,
        })),
        Command::Path => Ok(parse_value(tokens, InvalidOperandEncoding::Immediate)?
            .map(|value| Request::Path { value })),
        Command::Mask => parse_azure_mask(tokens),
        Command::Variable => parse_azure_variable(tokens),
        Command::SecretVariable => match parse_azure_variable(tokens)? {
            Action::Command(Request::Variable(request)) if request.value.is_none() => {
                Ok(Action::Command(Request::SecretVariable(request)))
            }
            Action::Command(Request::Variable(_)) => {
                Err(ShoutxError::usage("secret variable takes stdin only"))
            }
            other => Ok(other),
        },
        Command::Warning => parse_azure_issue(super::Severity::Warning, tokens),
        Command::Error => parse_azure_issue(super::Severity::Error, tokens),
    }
}
fn parse_azure_mask(tokens: Vec<OsString>) -> Result<Action, ShoutxError> {
    let mut each_line = false;
    let mut options = true;
    for token in tokens {
        match (options, token.to_str()) {
            (true, Some("--help")) => return Ok(Action::Help),
            (true, Some("--version")) => return Ok(Action::Version),
            (true, Some("--")) => options = false,
            (true, Some("--each-line")) if !each_line => each_line = true,
            _ => return Err(ShoutxError::usage("invalid Azure mask argument")),
        }
    }
    Ok(Action::Command(Request::Mask { each_line }))
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
    Ok(Action::Command(Request::Variable(
        crate::azure_pipelines::Variable {
            name,
            output,
            read_only,
            value,
        },
    )))
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
    Ok(Action::Command(Request::Issue(request)))
}

pub(crate) fn help(out: &mut String) {
    crate::cli::help_section(
        out,
        COMMANDS,
        0,
        "\nAzure Pipelines commands:\n",
    );
}
