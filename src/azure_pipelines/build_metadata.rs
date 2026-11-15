use super::{record::record, request::BuildMetadata, validation::validate_text};
use crate::{ShoutxError, input::VALUE_LIMIT};

pub fn encode_build_metadata(kind: BuildMetadata, value: &[u8]) -> Result<Vec<u8>, ShoutxError> {
    validate_text(value, VALUE_LIMIT, false)?;
    let text = std::str::from_utf8(value)
        .map_err(|_| ShoutxError::failure("Azure field is not valid UTF-8"))?;
    if text.encode_utf16().count() > 255 {
        return Err(ShoutxError::failure("Azure metadata exceeds length limit"));
    }
    if text
        .chars()
        .any(|c| matches!(c, '\u{0}'..='\u{1f}' | '\u{7f}'..='\u{9f}'))
    {
        return Err(ShoutxError::failure(
            "Azure metadata contains a control character",
        ));
    }
    let command: &[u8] = match kind {
        BuildMetadata::Number => {
            if text.ends_with('.')
                || text.chars().any(|c| {
                    matches!(
                        c,
                        '"' | '/' | '\\' | ':' | '<' | '>' | '\'' | '|' | '?' | '@' | '*'
                    )
                })
            {
                return Err(ShoutxError::failure("invalid Azure build number"));
            }
            b"build.updatebuildnumber"
        }
        BuildMetadata::Tag => {
            let whitespace = |c: char| matches!(c, '\u{9}'..='\u{d}' | '\u{20}' | '\u{85}' | '\u{a0}' | '\u{1680}' | '\u{2000}'..='\u{200a}' | '\u{2028}' | '\u{2029}' | '\u{202f}' | '\u{205f}' | '\u{3000}');
            if text.contains(':') || text.starts_with(whitespace) || text.ends_with(whitespace) {
                return Err(ShoutxError::failure("invalid Azure build tag"));
            }
            b"build.addbuildtag"
        }
    };
    record(command, &[], value)
}
