use unicode_general_category::{GeneralCategory, get_general_category};

pub(super) fn has_separator_sensitive_prefix(value: &str) -> bool {
    value.chars().next().is_some_and(|character| {
        matches!(
            get_general_category(character),
            GeneralCategory::NonspacingMark
                | GeneralCategory::SpacingMark
                | GeneralCategory::EnclosingMark
                | GeneralCategory::ModifierLetter
        )
    })
}
