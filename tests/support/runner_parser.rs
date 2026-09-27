#[derive(Clone, Copy)]
pub enum Platform {
    Posix,
    Windows,
}

pub type Record = (Vec<u8>, Vec<u8>);

pub fn parse(input: &[u8], platform: Platform) -> Result<Vec<Record>, &'static str> {
    std::str::from_utf8(input).map_err(|_| "invalid UTF-8")?;
    let mut records = Vec::new();
    let mut index = 0;
    while let Some((line, _)) = read_line(input, &mut index, platform) {
        if line.is_empty() {
            continue;
        }
        let equals = find(line, b"=");
        let heredoc = find(line, b"<<");
        if equals.is_some_and(|at| heredoc.is_none_or(|marker| at < marker)) {
            let at = equals.expect("checked above");
            records.push((line[..at].to_vec(), line[at + 1..].to_vec()));
        } else if heredoc.is_some_and(|at| equals.is_none_or(|marker| at < marker)) {
            let at = heredoc.expect("checked above");
            let name = &line[..at];
            let delimiter = &line[at + 2..];
            if name.is_empty() || delimiter.is_empty() {
                return Err("empty multiline name or delimiter");
            }
            let start = index;
            let mut end = index;
            loop {
                let Some((candidate, newline_len)) = read_line(input, &mut index, platform) else {
                    return Err("matching delimiter not found");
                };
                if candidate == delimiter {
                    break;
                }
                let Some(newline_len) = newline_len else {
                    return Err("EOF marker missing newline");
                };
                end = index - newline_len;
            }
            records.push((name.to_vec(), input[start..end].to_vec()));
        } else {
            return Err("invalid record header");
        }
    }
    Ok(records)
}

fn find(haystack: &[u8], needle: &[u8]) -> Option<usize> {
    haystack
        .windows(needle.len())
        .position(|window| window == needle)
}

fn read_line<'a>(
    input: &'a [u8],
    index: &mut usize,
    platform: Platform,
) -> Option<(&'a [u8], Option<usize>)> {
    if *index >= input.len() {
        return None;
    }
    let start = *index;
    let relative_lf = input[start..].iter().position(|byte| *byte == b'\n');
    let Some(relative_lf) = relative_lf else {
        *index = input.len();
        return Some((&input[start..], None));
    };
    let lf = start + relative_lf;
    *index = lf + 1;
    if matches!(platform, Platform::Windows) && lf > start && input[lf - 1] == b'\r' {
        Some((&input[start..lf - 1], Some(2)))
    } else {
        Some((&input[start..lf], Some(1)))
    }
}
