use std::ffi::OsString;

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
pub enum Request {
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
