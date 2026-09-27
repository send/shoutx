use std::fmt;

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum ErrorClass {
    Usage,
    Failure,
}

#[derive(Debug)]
pub struct ShoutxError {
    class: ErrorClass,
    message: &'static str,
}

impl ShoutxError {
    pub const fn usage(message: &'static str) -> Self {
        Self {
            class: ErrorClass::Usage,
            message,
        }
    }

    pub const fn failure(message: &'static str) -> Self {
        Self {
            class: ErrorClass::Failure,
            message,
        }
    }

    pub const fn class(&self) -> ErrorClass {
        self.class
    }
    pub const fn message(&self) -> &'static str {
        self.message
    }
}

impl fmt::Display for ShoutxError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str(self.message)
    }
}

impl std::error::Error for ShoutxError {}
