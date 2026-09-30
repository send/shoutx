// Research-only ASCII boundary policy. CR/LF become printable ASCII escapes.
// The encoded header and first encoded data byte stay in 0x20..=0x7e;
// later data is unchanged UTF-8. See the parser compatibility derivation.
pub(super) fn is_allowed_boundary_byte(byte: u8) -> bool {
    matches!(byte, b' '..=b'~' | b'\r' | b'\n')
}

pub(super) fn has_allowed_data_prefix(value: &[u8]) -> bool {
    value.first().copied().is_some_and(is_allowed_boundary_byte)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn allowlist_is_closed_over_all_unicode_scalars() {
        assert!(!has_allowed_data_prefix(b""));
        for scalar in 0..=0x10ffff {
            let Some(character) = char::from_u32(scalar) else {
                continue;
            };
            let mut bytes = [0; 4];
            let value = character.encode_utf8(&mut bytes).as_bytes();
            let expected = (0x20..=0x7e).contains(&scalar) || scalar == 10 || scalar == 13;
            assert_eq!(has_allowed_data_prefix(value), expected, "U+{scalar:04X}");
            assert_eq!(
                value.iter().copied().all(is_allowed_boundary_byte),
                expected
            );
        }
    }
}
