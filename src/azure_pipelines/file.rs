use super::{
    path_syntax::windows_absolute, record::record, request::FileKind, validation::validate_text,
};
use crate::{ShoutxError, input::VALUE_LIMIT};

pub fn encode_file(kind: FileKind, value: &[u8]) -> Result<Vec<u8>, ShoutxError> {
    validate_file_path(value, cfg!(windows))?;
    record(
        match kind {
            FileKind::Summary => b"task.uploadsummary",
            FileKind::UploadFile => b"task.uploadfile",
        },
        &[],
        value,
    )
}

fn validate_file_path(value: &[u8], windows: bool) -> Result<(), ShoutxError> {
    validate_text(value, VALUE_LIMIT, false)?;
    if value.contains(&b'\r') || value.contains(&b'\n') {
        return Err(ShoutxError::failure(
            "Azure file path contains a line boundary",
        ));
    }
    let separator = |b: &u8| *b == b'/' || windows && *b == b'\\';
    let absolute = if windows {
        let drive = value.len() >= 3 && value[0].is_ascii_alphabetic() && value[1] == b':';
        if value.iter().enumerate().any(|(i, b)| {
            *b < 32
                || matches!(b, b'"' | b'<' | b'>' | b'|' | b'?' | b'*')
                || *b == b':' && !(drive && i == 1)
        }) {
            return Err(ShoutxError::failure("invalid Azure file path syntax"));
        }
        windows_absolute(value) && (drive || value[2..].split(separator).count() >= 3)
    } else {
        value.starts_with(b"/")
    };
    let basename = value.rsplit(separator).next().unwrap_or_default();
    if !absolute || basename.is_empty() || matches!(basename, b"." | b"..") {
        return Err(ShoutxError::failure("invalid Azure file path syntax"));
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::validate_file_path;

    #[test]
    fn file_path_dialects_do_not_apply_path_list_policy() {
        for path in ["/a:b;c]", "/a/../b", "/ space ", "/a\\", "/a\t"] {
            assert!(validate_file_path(path.as_bytes(), false).is_ok(), "{path}");
        }
        for path in [
            "C:/file;]",
            "z:\\space ",
            "//host/share/file",
            "\\\\host\\share\\α😀",
            "C:/a/../b",
        ] {
            assert!(validate_file_path(path.as_bytes(), true).is_ok(), "{path}");
        }
        for path in [
            "C:/",
            "C:relative",
            "/file",
            "//host/share",
            "//host/share/",
            "//./share/file",
            "//?/share/file",
            "//host//file",
            "C:/file:stream",
            "C:/a?",
            "C:/a*",
            "C:/a<",
            "C:/a>",
            "C:/a|",
            "C:/a\"",
            "C:/a\t",
            "C:/a\u{1f}",
            "C:/.",
            "C:/..",
        ] {
            assert!(validate_file_path(path.as_bytes(), true).is_err(), "{path}");
        }
    }
}
