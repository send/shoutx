//! Shared Windows absolute-path syntax; destination admission remains local.

pub(super) fn windows_absolute(value: &[u8]) -> bool {
    let separator = |b: u8| matches!(b, b'/' | b'\\');
    if value.len() >= 3 && value[0].is_ascii_alphabetic() && value[1] == b':' && separator(value[2])
    {
        return true;
    }
    if value.len() < 5 || !separator(value[0]) || !separator(value[1]) {
        return false;
    }
    let mut components = value[2..].split(|b| separator(*b));
    let valid = |part: &[u8]| !part.is_empty() && part != b"." && part != b"?";
    components.next().is_some_and(valid) && components.next().is_some_and(valid)
}
