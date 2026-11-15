use super::{BuildMetadata, FileKind, Issue, LogKind, Variable};
use std::ffi::OsString;

#[derive(Debug)]
pub enum Request {
    Log {
        kind: LogKind,
        value: Option<OsString>,
    },
    File {
        kind: FileKind,
        value: Option<OsString>,
    },
    EndGroup,
    BuildMetadata {
        kind: BuildMetadata,
        value: Option<OsString>,
    },
    Mask {
        each_line: bool,
    },
    Path {
        value: Option<OsString>,
    },
    Variable(Variable),
    SecretVariable(Variable),
    Issue(Issue),
}
