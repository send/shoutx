pub fn parse(input: &[u8]) -> Result<Vec<Vec<u8>>, &'static str> {
    std::str::from_utf8(input).map_err(|_| "invalid UTF-8")?;
    let input = input.strip_prefix(b"\xef\xbb\xbf").unwrap_or(input);
    let mut paths: Vec<Vec<u8>> = Vec::new();
    let mut start = 0;
    while start < input.len() {
        let mut end = start;
        while end < input.len() && input[end] != b'\r' && input[end] != b'\n' {
            end += 1;
        }
        let line = &input[start..end];
        if !line.is_empty() {
            paths.retain(|path| path.as_slice() != line);
            paths.push(line.to_vec());
        }
        if end == input.len() {
            break;
        }
        start = end + 1;
        if input[end] == b'\r' && start < input.len() && input[start] == b'\n' {
            start += 1;
        }
    }
    Ok(paths)
}

pub fn effective(paths: &[Vec<u8>]) -> Vec<Vec<u8>> {
    paths.iter().rev().cloned().collect()
}
