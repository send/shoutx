use super::stdout_start_table::START_RANGES;

// Input has already passed strict UTF-8 validation. Inspect only its start;
// no suffix scan, normalization, allocation or consumer-locale inference.
fn is_allowed_boundary_byte(byte: u8) -> bool {
    matches!(byte, b' '..=b'~' | b'\r' | b'\n')
}

pub(super) fn has_allowed_data_prefix(value: &str) -> bool {
    let Some(byte) = value.as_bytes().first().copied() else {
        return false;
    };
    if byte.is_ascii() {
        return is_allowed_boundary_byte(byte);
    }
    let Some(first) = value.chars().next() else {
        return false;
    };
    let scalar = u32::from(first);
    START_RANGES
        .binary_search_by(|&(start, end)| {
            if scalar < start {
                std::cmp::Ordering::Greater
            } else if scalar > end {
                std::cmp::Ordering::Less
            } else {
                std::cmp::Ordering::Equal
            }
        })
        .is_ok()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn allowlist_is_closed_over_all_unicode_scalars() {
        assert!(!has_allowed_data_prefix(""));
        let table: serde_json::Value = serde_json::from_str(include_str!(
            "../../tests/unicode-policy-probe/start-candidate.json"
        ))
        .unwrap();
        let mut membership = vec![false; 0x110000];
        for range in table["ranges"].as_array().unwrap() {
            let start = range[0].as_u64().unwrap() as usize;
            let end = range[1].as_u64().unwrap() as usize;
            for allowed in &mut membership[start..=end] {
                assert!(!*allowed);
                *allowed = true;
            }
        }
        assert_eq!(membership.iter().filter(|&&v| v).count(), 1_105_522);
        for scalar in 0..=0x10ffff {
            let Some(character) = char::from_u32(scalar) else {
                continue;
            };
            let mut bytes = [0; 4];
            let value = character.encode_utf8(&mut bytes);
            let expected = membership[scalar as usize];
            assert_eq!(has_allowed_data_prefix(value), expected, "U+{scalar:04X}");
        }
    }
}
