use unicode_general_category::{GeneralCategory, get_general_category};

// Shared by research-only V2 data writers. This blocks observed boundary
// failures, not every culture/backend-dependent parser failure.
pub(super) fn has_sensitive_data_prefix(value: &str) -> bool {
    value.chars().next().is_some_and(|character| {
        matches!(
            character,
            '\u{0e33}' | '\u{0eb3}' | '\u{1f3fb}'..='\u{1f3ff}'
        ) || matches!(
            get_general_category(character),
            GeneralCategory::NonspacingMark
                | GeneralCategory::SpacingMark
                | GeneralCategory::EnclosingMark
                | GeneralCategory::ModifierLetter
        )
    })
}
