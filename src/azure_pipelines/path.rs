use super::{path_syntax::windows_absolute, record::record, validation::validate_text};
use crate::{ShoutxError, input::VALUE_LIMIT};

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

#[cfg(test)]
mod tests {
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
