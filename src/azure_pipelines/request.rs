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

#[derive(Clone, Copy, Debug)]
pub enum LogKind {
    Debug,
    Group,
}

#[derive(Clone, Copy, Debug)]
pub enum BuildMetadata {
    Number,
    Tag,
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

#[derive(Clone, Copy, Debug)]
pub enum FileKind {
    Summary,
    UploadFile,
}
