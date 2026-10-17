use crate::{error::ShoutxError, input::VALUE_LIMIT};

fn validate(value: &[u8]) -> Result<&str, ShoutxError> {
    if value.len() > VALUE_LIMIT {
        return Err(ShoutxError::failure("artifact field exceeds size limit"));
    }
    let text = std::str::from_utf8(value)
        .map_err(|_| ShoutxError::failure("artifact field is not valid UTF-8"))?;
    if value.contains(&0) {
        return Err(ShoutxError::failure("artifact field contains NUL"));
    }
    Ok(text)
}

fn validate_semantic(value: &[u8]) -> Result<(), ShoutxError> {
    if value.is_empty() {
        return Err(ShoutxError::failure("artifact field is empty"));
    }
    if value.iter().any(|b| matches!(b, b'\r' | b'\n' | b'=')) {
        return Err(ShoutxError::failure(
            "artifact field contains a record delimiter",
        ));
    }
    Ok(())
}

// Explicit Unicode White_Space set used by the declared consumer contract.
// Do not silently change acceptance with the Rust toolchain's Unicode version.
fn trailing_whitespace(c: char) -> bool {
    matches!(c, '\u{0009}'..='\u{000d}' | '\u{0020}' | '\u{0085}' |
        '\u{00a0}' | '\u{1680}' | '\u{2000}'..='\u{200a}' |
        '\u{2028}' | '\u{2029}' | '\u{202f}' | '\u{205f}' | '\u{3000}')
}

fn record(parts: &[&[u8]]) -> Result<Vec<u8>, ShoutxError> {
    let size = parts
        .iter()
        .try_fold(1usize, |size, part| {
            size.checked_add(part.len()).filter(|n| *n <= VALUE_LIMIT)
        })
        .ok_or_else(|| ShoutxError::failure("artifact record exceeds size limit"))?;
    let mut result = Vec::with_capacity(size);
    for part in parts {
        result.extend_from_slice(part);
    }
    result.push(b'\n');
    Ok(result)
}

pub fn encode_file(mut path: Vec<u8>) -> Result<Vec<u8>, ShoutxError> {
    validate(&path)?;
    super::normalize::strip_final(&mut path);
    validate_semantic(&path)?;
    if validate(&path)?
        .chars()
        .next_back()
        .is_some_and(trailing_whitespace)
    {
        return Err(ShoutxError::failure("artifact path ends in whitespace"));
    }
    record(&[b"file://", &path])
}

pub fn encode_oci(reference: &[u8], digest: &[u8]) -> Result<Vec<u8>, ShoutxError> {
    validate(reference)?;
    validate_semantic(reference)?;
    // Bound and validate before copying either operand. OCI never strips framing.
    validate(digest)?;
    let hex = [
        (b"sha256:".as_slice(), 64),
        (b"sha384:".as_slice(), 96),
        (b"sha512:".as_slice(), 128),
    ]
    .into_iter()
    .find_map(|(prefix, length)| {
        digest
            .strip_prefix(prefix)
            .filter(|hex| hex.len() == length)
    })
    .filter(|hex| {
        hex.iter()
            .all(|b| b.is_ascii_digit() || (b'a'..=b'f').contains(b))
    });
    if hex.is_none() {
        return Err(ShoutxError::failure("invalid artifact digest"));
    }
    record(&[b"oci://", reference, b"@", digest])
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn explicit_file_scheme_preserves_data_and_one_terminal_boundary() {
        for path in [
            "report",
            "../report",
            "#name",
            "oci://name@digest",
            " Ελληνικά_日本語_😀",
            "a\u{feff}",
            "a\u{200b}",
        ] {
            for ending in ["", "\n", "\r", "\r\n"] {
                assert_eq!(
                    encode_file(format!("{path}{ending}").into_bytes()).unwrap(),
                    format!("file://{path}\n").as_bytes()
                );
            }
        }
    }

    #[test]
    fn rejects_empty_delimiters_invalid_encoding_and_trailing_whitespace() {
        for path in [
            b"".as_slice(),
            b"\n",
            b"a\n\n",
            b"a\rnext",
            b"a=b",
            b"a\0",
            b"\xff",
        ] {
            assert!(encode_file(path.to_vec()).is_err());
        }
        for c in [
            '\t', ' ', '\u{85}', '\u{a0}', '\u{1680}', '\u{2000}', '\u{200a}', '\u{2028}',
            '\u{2029}', '\u{202f}', '\u{205f}', '\u{3000}',
        ] {
            assert!(encode_file(format!("a{c}").into_bytes()).is_err());
        }
    }

    #[test]
    fn oci_is_typed_and_never_normalizes() {
        for (algorithm, length) in [("sha256", 64), ("sha384", 96), ("sha512", 128)] {
            let digest = format!("{algorithm}:{}", "a".repeat(length));
            for reference in [
                "registry:5000/name:tag",
                "file://path",
                "a@b",
                " 日本語 😀 ",
            ] {
                assert_eq!(
                    encode_oci(reference.as_bytes(), digest.as_bytes()).unwrap(),
                    format!("oci://{reference}@{digest}\n").as_bytes()
                );
            }
            for reference in ["", "a\n", "a\r", "a=b", "a\0"] {
                assert!(encode_oci(reference.as_bytes(), digest.as_bytes()).is_err());
            }
            for bad in [
                digest.to_uppercase(),
                format!("{digest}\n"),
                format!("{digest}a"),
                digest[..digest.len() - 1].to_string(),
            ] {
                assert!(encode_oci(b"a", bad.as_bytes()).is_err());
            }
        }
    }

    #[test]
    fn encoded_limit_includes_all_framing() {
        for size in [VALUE_LIMIT - 1, VALUE_LIMIT] {
            assert_eq!(encode_file(vec![b'a'; size - 8]).unwrap().len(), size);
            let digest = format!("sha256:{}", "a".repeat(64));
            assert_eq!(
                encode_oci(&vec![b'a'; size - 8 - digest.len()], digest.as_bytes())
                    .unwrap()
                    .len(),
                size
            );
        }
        assert!(encode_file(vec![b'a'; VALUE_LIMIT - 7]).is_err());
        assert!(encode_file(vec![b'a'; VALUE_LIMIT + 1]).is_err());
        let digest = format!("sha256:{}", "a".repeat(64));
        assert!(
            encode_oci(
                &vec![b'a'; VALUE_LIMIT - 7 - digest.len()],
                digest.as_bytes()
            )
            .is_err()
        );
    }
}
