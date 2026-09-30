use flate2::bufread::DeflateDecoder;
use flate2::bufread::GzDecoder;
use std::collections::BTreeSet;
use std::env;
use std::error::Error;
use std::fs::File;
use std::io::{Cursor, Read, Seek, SeekFrom};
use std::path::Path;

const MAX_ARCHIVE_BYTES: u64 = 256 * 1024 * 1024;
const MAX_EXPANDED_BYTES: u64 = 256 * 1024 * 1024;

type Result<T> = std::result::Result<T, Box<dyn Error>>;

fn invalid(message: impl Into<String>) -> Box<dyn Error> {
    message.into().into()
}

fn expected(root: &str, windows: bool) -> BTreeSet<Vec<u8>> {
    let executable = if windows { "shoutx.exe" } else { "shoutx" };
    [
        format!("{root}/{executable}").into_bytes(),
        format!("{root}/README.md").into_bytes(),
        format!("{root}/LICENSE").into_bytes(),
    ]
    .into_iter()
    .collect()
}

fn check_path(path: &[u8], root: &str, windows: bool) -> Result<()> {
    if !expected(root, windows).contains(path) && path != format!("{root}/").as_bytes() {
        return Err(invalid(format!(
            "unexpected archive path: {}",
            String::from_utf8_lossy(path)
        )));
    }
    Ok(())
}

fn insert_path(paths: &mut BTreeSet<Vec<u8>>, path: &[u8]) -> Result<()> {
    if !paths.insert(path.to_owned()) {
        return Err(invalid(format!(
            "duplicate archive path: {}",
            String::from_utf8_lossy(path)
        )));
    }
    let folded = path.iter().map(u8::to_ascii_lowercase).collect::<Vec<_>>();
    if paths
        .iter()
        .filter(|candidate| candidate.as_slice() != path)
        .any(|candidate| {
            candidate
                .iter()
                .map(u8::to_ascii_lowercase)
                .eq(folded.iter().copied())
        })
    {
        return Err(invalid("case-colliding archive paths"));
    }
    Ok(())
}

fn validate_tar(path: &Path, root: &str) -> Result<()> {
    if path.metadata()?.len() > MAX_ARCHIVE_BYTES {
        return Err(invalid("compressed tar exceeds validator limit"));
    }
    let compressed = std::fs::read(path)?;
    let mut decoder = GzDecoder::new(Cursor::new(&compressed));
    let mut bytes = Vec::new();
    decoder
        .by_ref()
        .take(MAX_EXPANDED_BYTES + 1)
        .read_to_end(&mut bytes)?;
    if bytes.len() as u64 > MAX_EXPANDED_BYTES {
        return Err(invalid("expanded tar exceeds validator limit"));
    }
    if usize::try_from(decoder.into_inner().position())? != compressed.len() {
        return Err(invalid(
            "multiple gzip members or trailing data are not permitted",
        ));
    }
    validate_raw_tar(&bytes, root)?;

    let mut archive = tar::Archive::new(Cursor::new(bytes));
    let mut paths = BTreeSet::new();
    let mut total = 0_u64;
    let mut root_seen = false;
    for entry in archive.entries()? {
        let mut entry = entry?;
        let path = entry.path_bytes().into_owned();
        check_path(&path, root, false)?;
        let kind = entry.header().entry_type();
        if path == format!("{root}/").as_bytes() {
            if std::mem::replace(&mut root_seen, true) {
                return Err(invalid("duplicate top-level directory entry"));
            }
            if !kind.is_dir() {
                return Err(invalid("top-level tar entry is not a directory"));
            }
            if entry.size() != 0 {
                return Err(invalid("top-level tar directory has payload data"));
            }
        } else {
            if !kind.is_file() {
                return Err(invalid("tar payload entry is not a regular file"));
            }
            insert_path(&mut paths, &path)?;
            total = total
                .checked_add(entry.size())
                .ok_or_else(|| invalid("expanded size overflow"))?;
            if total > MAX_EXPANDED_BYTES {
                return Err(invalid("expanded tar exceeds validator limit"));
            }
            std::io::copy(&mut entry, &mut std::io::sink())?;
        }
    }
    if paths != expected(root, false) {
        return Err(invalid("tar does not contain the exact logical file set"));
    }
    Ok(())
}

fn parse_tar_number(field: &[u8]) -> Result<usize> {
    if field.first().is_some_and(|byte| byte & 0x80 != 0) {
        return Err(invalid("base-256 tar sizes are not accepted"));
    }
    let text = field
        .split(|byte| *byte == 0 || *byte == b' ')
        .find(|part| !part.is_empty())
        .unwrap_or_default();
    if text.is_empty() {
        return Ok(0);
    }
    Ok(usize::from_str_radix(std::str::from_utf8(text)?, 8)?)
}

fn validate_raw_tar(bytes: &[u8], root: &str) -> Result<()> {
    let mut offset = 0_usize;
    let mut end_markers = 0_u8;
    while offset
        .checked_add(512)
        .is_some_and(|end| end <= bytes.len())
    {
        let header = &bytes[offset..offset + 512];
        if header.iter().all(|byte| *byte == 0) {
            end_markers += 1;
            offset += 512;
            if end_markers == 2 {
                if bytes[offset..].iter().any(|byte| *byte != 0) {
                    return Err(invalid("non-zero trailing tar data"));
                }
                return Ok(());
            }
            continue;
        }
        if end_markers != 0 {
            return Err(invalid("tar entry after end marker"));
        }
        match header[156] {
            b'g' => return Err(invalid("global pax metadata is not permitted")),
            b'L' | b'K' => return Err(invalid("GNU path metadata is not permitted")),
            b'x' => return Err(invalid("local pax metadata is not permitted")),
            _ => {}
        }
        let magic = &header[257..263];
        let version = &header[263..265];
        if !((magic == b"ustar\0" && version == b"00") || (magic == b"ustar " && version == b" \0"))
        {
            return Err(invalid("unsupported tar header dialect"));
        }
        if header[345..500].iter().any(|byte| *byte != 0) {
            return Err(invalid("tar prefix field is not permitted"));
        }
        if header[157..257].iter().any(|byte| *byte != 0) {
            return Err(invalid("tar linkname field is not permitted"));
        }
        let name_end = header[..100]
            .iter()
            .position(|byte| *byte == 0)
            .unwrap_or(100);
        if header[name_end..100].iter().any(|byte| *byte != 0) {
            return Err(invalid("malformed tar name padding"));
        }
        check_path(&header[..name_end], root, false)?;
        let size = parse_tar_number(&header[124..136])?;
        let payload_start = offset + 512;
        let payload_end = payload_start
            .checked_add(size)
            .ok_or_else(|| invalid("tar entry size overflow"))?;
        if payload_end > bytes.len() {
            return Err(invalid("truncated tar entry"));
        }
        let padded = size
            .checked_add(511)
            .ok_or_else(|| invalid("tar entry size overflow"))?
            / 512
            * 512;
        let next_offset = payload_start
            .checked_add(padded)
            .ok_or_else(|| invalid("tar offset overflow"))?;
        if next_offset > bytes.len() {
            return Err(invalid("truncated tar entry padding"));
        }
        if bytes[payload_end..next_offset]
            .iter()
            .any(|byte| *byte != 0)
        {
            return Err(invalid("non-zero tar entry padding"));
        }
        offset = next_offset;
    }
    Err(invalid("tar is missing two end markers"))
}

fn u16_at(bytes: &[u8], offset: usize) -> Result<u16> {
    let value = bytes
        .get(offset..offset + 2)
        .ok_or_else(|| invalid("truncated ZIP header"))?;
    Ok(u16::from_le_bytes([value[0], value[1]]))
}

fn u32_at(bytes: &[u8], offset: usize) -> Result<u32> {
    let value = bytes
        .get(offset..offset + 4)
        .ok_or_else(|| invalid("truncated ZIP header"))?;
    Ok(u32::from_le_bytes([value[0], value[1], value[2], value[3]]))
}

#[allow(clippy::too_many_lines)]
fn validate_zip(path: &Path, root: &str) -> Result<()> {
    let mut file = File::open(path)?;
    let file_len = file.metadata()?.len();
    if file_len > MAX_ARCHIVE_BYTES {
        return Err(invalid("ZIP archive exceeds validator limit"));
    }
    let mut archive = zip::ZipArchive::new(&mut file)?;
    if archive.offset() != 0 {
        return Err(invalid("prepended ZIP data is not permitted"));
    }
    let mut paths = BTreeSet::new();
    let mut total = 0_u64;
    let mut root_seen = false;
    let mut local_spans = Vec::new();
    let mut central_spans = Vec::new();
    for index in 0..archive.len() {
        let entry = archive.by_index_raw(index)?;
        if entry.encrypted() {
            return Err(invalid("encrypted ZIP entry"));
        }
        let name = entry.name_raw().to_vec();
        check_path(&name, root, true)?;

        let mut local = File::open(path)?;
        local.seek(SeekFrom::Start(entry.header_start()))?;
        let mut header = [0_u8; 30];
        local.read_exact(&mut header)?;
        if header[..4] != [0x50, 0x4b, 0x03, 0x04] {
            return Err(invalid("invalid ZIP local header signature"));
        }
        let local_flags = u16_at(&header, 6)?;
        if local_flags & 9 != 0 {
            return Err(invalid("encrypted or data-descriptor ZIP local entry"));
        }
        let local_method = u16_at(&header, 8)?;
        let allowed_flags = 0x0800 | if local_method == 8 { 0x0006 } else { 0 };
        if local_flags & !allowed_flags != 0 {
            return Err(invalid("unsupported ZIP general-purpose flags"));
        }
        let local_version_needed = u16_at(&header, 4)?;
        let local_modified_time = u16_at(&header, 10)?;
        let local_modified_date = u16_at(&header, 12)?;
        let local_crc = u32_at(&header, 14)?;
        let local_compressed = u32_at(&header, 18)?;
        let local_size = u32_at(&header, 22)?;
        let name_len = usize::from(u16_at(&header, 26)?);
        let extra_len = usize::from(u16_at(&header, 28)?);
        if extra_len != 0 {
            return Err(invalid("ZIP local extra metadata is not permitted"));
        }
        let mut local_name = vec![0_u8; name_len];
        local.read_exact(&mut local_name)?;
        let mut central = File::open(path)?;
        central.seek(SeekFrom::Start(entry.central_header_start()))?;
        let mut central_header = [0_u8; 46];
        central.read_exact(&mut central_header)?;
        if central_header[..4] != [0x50, 0x4b, 0x01, 0x02] {
            return Err(invalid("invalid ZIP central header signature"));
        }
        let central_flags = u16_at(&central_header, 8)?;
        if central_flags != local_flags {
            return Err(invalid("ZIP local and central flags disagree"));
        }
        let central_method = u16_at(&central_header, 10)?;
        let central_version_needed = u16_at(&central_header, 6)?;
        let central_modified_time = u16_at(&central_header, 12)?;
        let central_modified_date = u16_at(&central_header, 14)?;
        let central_crc = u32_at(&central_header, 16)?;
        let central_compressed = u32_at(&central_header, 20)?;
        let central_size = u32_at(&central_header, 24)?;
        let central_name_len = usize::from(u16_at(&central_header, 28)?);
        let central_extra_len = usize::from(u16_at(&central_header, 30)?);
        let central_comment_len = usize::from(u16_at(&central_header, 32)?);
        if central_extra_len != 0 || central_comment_len != 0 {
            return Err(invalid(
                "ZIP central extra metadata or comment is not permitted",
            ));
        }
        if u16_at(&central_header, 34)? != 0 {
            return Err(invalid("multi-disk ZIP is not permitted"));
        }
        let mut central_name = vec![0_u8; central_name_len];
        central.read_exact(&mut central_name)?;
        if local_name != central_name || local_name != name {
            return Err(invalid("ZIP local and central names disagree"));
        }
        let parsed_method = match entry.compression() {
            zip::CompressionMethod::Stored => 0,
            zip::CompressionMethod::Deflated => 8,
            _ => return Err(invalid("unsupported ZIP compression method")),
        };
        if local_method != central_method
            || local_method != parsed_method
            || local_version_needed != central_version_needed
            || local_modified_time != central_modified_time
            || local_modified_date != central_modified_date
            || local_crc != central_crc
            || local_crc != entry.crc32()
            || local_compressed != central_compressed
            || u64::from(local_compressed) != entry.compressed_size()
            || local_size != central_size
            || u64::from(local_size) != entry.size()
        {
            return Err(invalid("ZIP local and central metadata disagree"));
        }
        local.seek(SeekFrom::Current(i64::try_from(extra_len)?))?;
        let local_end = entry
            .header_start()
            .checked_add(30 + u64::try_from(name_len + extra_len)?)
            .and_then(|start| start.checked_add(entry.compressed_size()))
            .ok_or_else(|| invalid("ZIP local span overflow"))?;
        local_spans.push((entry.header_start(), local_end));
        let central_end = entry
            .central_header_start()
            .checked_add(
                46 + u64::try_from(central_name_len + central_extra_len + central_comment_len)?,
            )
            .ok_or_else(|| invalid("ZIP central span overflow"))?;
        central_spans.push((entry.central_header_start(), central_end));

        if name == format!("{root}/").as_bytes() {
            if std::mem::replace(&mut root_seen, true) {
                return Err(invalid("duplicate top-level directory entry"));
            }
            if !entry.is_dir() {
                return Err(invalid("top-level ZIP entry is not a directory"));
            }
            if entry.size() != 0 {
                return Err(invalid("top-level ZIP directory has payload data"));
            }
        } else {
            if !entry.is_file() {
                return Err(invalid("ZIP payload entry is not a regular file"));
            }
            insert_path(&mut paths, &name)?;
            total = total
                .checked_add(entry.size())
                .ok_or_else(|| invalid("expanded size overflow"))?;
            if total > MAX_EXPANDED_BYTES {
                return Err(invalid("expanded ZIP exceeds validator limit"));
            }
        }
    }
    drop(archive);
    validate_zip_layout(&mut file, file_len, &mut local_spans, &mut central_spans)?;
    validate_zip_payloads(path, root)?;
    if paths != expected(root, true) {
        return Err(invalid("ZIP does not contain the exact logical file set"));
    }
    Ok(())
}

fn validate_zip_payloads(path: &Path, root: &str) -> Result<()> {
    let mut file = File::open(path)?;
    let mut archive = zip::ZipArchive::new(&mut file)?;
    let mut total = 0_u64;
    for index in 0..archive.len() {
        let mut entry = archive.by_index(index)?;
        check_path(entry.name_raw(), root, true)?;
        let compression = entry.compression();
        let data_start = entry.data_start();
        let compressed_size = entry.compressed_size();
        let expected_size = entry.size();
        let copied = std::io::copy(
            &mut entry.by_ref().take(MAX_EXPANDED_BYTES - total + 1),
            &mut std::io::sink(),
        )?;
        total = total
            .checked_add(copied)
            .ok_or_else(|| invalid("expanded size overflow"))?;
        if total > MAX_EXPANDED_BYTES {
            return Err(invalid("expanded ZIP exceeds validator limit"));
        }
        if copied != entry.size() {
            return Err(invalid("expanded ZIP size disagrees with metadata"));
        }
        drop(entry);
        if compression == zip::CompressionMethod::Deflated {
            validate_raw_deflate(path, data_start, compressed_size, expected_size)?;
        }
    }
    Ok(())
}

fn validate_raw_deflate(
    path: &Path,
    data_start: u64,
    compressed_size: u64,
    expected_size: u64,
) -> Result<()> {
    let mut file = File::open(path)?;
    file.seek(SeekFrom::Start(data_start))?;
    let compressed_len = usize::try_from(compressed_size)?;
    let mut compressed = vec![0_u8; compressed_len];
    file.read_exact(&mut compressed)?;
    let mut decoder = DeflateDecoder::new(Cursor::new(&compressed));
    let expanded = std::io::copy(
        &mut decoder.by_ref().take(MAX_EXPANDED_BYTES + 1),
        &mut std::io::sink(),
    )?;
    if expanded != expected_size {
        return Err(invalid("raw deflate size disagrees with ZIP metadata"));
    }
    if usize::try_from(decoder.into_inner().position())? != compressed.len() {
        return Err(invalid("data after deflate end marker is not permitted"));
    }
    Ok(())
}

fn validate_zip_layout(
    file: &mut File,
    file_len: u64,
    local_spans: &mut [(u64, u64)],
    central_spans: &mut [(u64, u64)],
) -> Result<()> {
    if file_len < 22 {
        return Err(invalid("ZIP end record not found"));
    }
    file.seek(SeekFrom::End(-22))?;
    let mut end = [0_u8; 22];
    file.read_exact(&mut end)?;
    if end[..4] != *b"PK\x05\x06" || u16_at(&end, 20)? != 0 {
        return Err(invalid("ZIP comment or trailing data is not permitted"));
    }
    let entries_on_disk = usize::from(u16_at(&end, 8)?);
    let entries_total = usize::from(u16_at(&end, 10)?);
    let central_size = u64::from(u32_at(&end, 12)?);
    let central_start = u64::from(u32_at(&end, 16)?);
    if u16_at(&end, 4)? != 0
        || u16_at(&end, 6)? != 0
        || entries_on_disk != local_spans.len()
        || entries_total != local_spans.len()
    {
        return Err(invalid("ZIP end-record entry count disagrees"));
    }

    local_spans.sort_unstable();
    central_spans.sort_unstable();
    let mut position = 0_u64;
    for &(start, finish) in local_spans.iter().chain(central_spans.iter()) {
        if start != position || finish < start {
            return Err(invalid("prepended, interstitial, or overlapping ZIP data"));
        }
        position = finish;
    }
    if central_spans.first().map(|span| span.0) != Some(central_start)
        || position != file_len - 22
        || position - central_start != central_size
    {
        return Err(invalid("ZIP central-directory layout disagrees"));
    }
    Ok(())
}

fn run() -> Result<()> {
    let mut args = env::args_os().skip(1);
    let archive = args.next().ok_or_else(|| invalid("missing archive path"))?;
    let root = args
        .next()
        .ok_or_else(|| invalid("missing expected root"))?
        .into_string()
        .map_err(|_| invalid("expected root is not UTF-8"))?;
    if args.next().is_some() {
        return Err(invalid("unexpected argument"));
    }
    let path = Path::new(&archive);
    let name = path
        .file_name()
        .and_then(|name| name.to_str())
        .ok_or_else(|| invalid("archive filename is not UTF-8"))?;
    if name.ends_with(".tar.gz") {
        validate_tar(path, &root)
    } else if path.extension().is_some_and(|extension| extension == "zip") {
        validate_zip(path, &root)
    } else {
        Err(invalid("archive must end in .tar.gz or .zip"))
    }
}

fn main() {
    if run().is_err() {
        eprintln!("archive validation failed");
        std::process::exit(1);
    }
}

#[cfg(test)]
mod tests {
    use super::{validate_raw_tar, validate_tar, validate_zip};
    use flate2::Compression;
    use flate2::write::{DeflateEncoder, GzEncoder};
    use std::fs;
    use std::io::{Cursor, Write};
    use std::path::PathBuf;
    use std::sync::atomic::{AtomicU64, Ordering};

    const ROOT: &str = "shoutx-v0.0.0-test";
    static NEXT_FILE: AtomicU64 = AtomicU64::new(0);

    fn temporary(extension: &str) -> PathBuf {
        let sequence = NEXT_FILE.fetch_add(1, Ordering::Relaxed);
        std::env::temp_dir().join(format!(
            "shoutx-archive-validator-{}-{sequence}.{extension}",
            std::process::id()
        ))
    }

    fn octal(field: &mut [u8], value: usize) {
        let text = format!("{:0width$o}\0", value, width = field.len() - 1);
        field.copy_from_slice(text.as_bytes());
    }

    fn tar_entry(name: &str, kind: u8, contents: &[u8]) -> Vec<u8> {
        let mut header = [0_u8; 512];
        header[..name.len()].copy_from_slice(name.as_bytes());
        octal(
            &mut header[100..108],
            if kind == b'5' { 0o755 } else { 0o644 },
        );
        octal(&mut header[108..116], 0);
        octal(&mut header[116..124], 0);
        octal(&mut header[124..136], contents.len());
        octal(&mut header[136..148], 0);
        header[148..156].fill(b' ');
        header[156] = kind;
        header[257..263].copy_from_slice(b"ustar\0");
        header[263..265].copy_from_slice(b"00");
        let checksum: usize = header.iter().map(|byte| usize::from(*byte)).sum();
        let checksum_text = format!("{checksum:06o}\0 ");
        header[148..156].copy_from_slice(checksum_text.as_bytes());
        let mut result = header.to_vec();
        result.extend_from_slice(contents);
        result.resize(result.len().div_ceil(512) * 512, 0);
        result
    }

    fn gzip_tar(tar: &[u8]) -> Vec<u8> {
        let mut gzip = GzEncoder::new(Vec::new(), Compression::default());
        gzip.write_all(tar).unwrap();
        gzip.finish().unwrap()
    }

    fn raw_tar(global_pax: Option<&[u8]>) -> Vec<u8> {
        let mut tar = Vec::new();
        if let Some(pax) = global_pax {
            tar.extend(tar_entry("GlobalHead.0", b'g', pax));
        }
        tar.extend(tar_entry(&format!("{ROOT}/"), b'5', b""));
        for name in ["shoutx", "README.md", "LICENSE"] {
            tar.extend(tar_entry(&format!("{ROOT}/{name}"), b'0', name.as_bytes()));
        }
        tar.resize(tar.len() + 1024, 0);
        gzip_tar(&tar)
    }

    fn error_message(result: super::Result<()>) -> String {
        result.unwrap_err().to_string()
    }

    fn push_u16(bytes: &mut Vec<u8>, value: u16) {
        bytes.extend_from_slice(&value.to_le_bytes());
    }

    fn push_u32(bytes: &mut Vec<u8>, value: u32) {
        bytes.extend_from_slice(&value.to_le_bytes());
    }

    fn raw_zip(local_name_override: Option<&[u8]>, encrypted: bool) -> Vec<u8> {
        raw_zip_with_method(local_name_override, encrypted, false)
    }

    fn raw_zip_with_method(
        local_name_override: Option<&[u8]>,
        encrypted: bool,
        deflated: bool,
    ) -> Vec<u8> {
        struct Central {
            name: Vec<u8>,
            crc: u32,
            size: u32,
            compressed_size: u32,
            method: u16,
            offset: u32,
        }
        let mut bytes = Vec::new();
        let mut central = Vec::new();
        for (index, leaf) in ["shoutx.exe", "README.md", "LICENSE"]
            .into_iter()
            .enumerate()
        {
            let name = format!("{ROOT}/{leaf}").into_bytes();
            let local_name = if index == 0 {
                local_name_override.unwrap_or(&name)
            } else {
                &name
            };
            let contents = leaf.as_bytes();
            let compressed = if deflated {
                let mut encoder = DeflateEncoder::new(Vec::new(), Compression::default());
                encoder.write_all(contents).unwrap();
                encoder.finish().unwrap()
            } else {
                contents.to_vec()
            };
            let method = if deflated { 8 } else { 0 };
            let crc = crc32fast::hash(contents);
            let offset = u32::try_from(bytes.len()).unwrap();
            bytes.extend_from_slice(b"PK\x03\x04");
            push_u16(&mut bytes, 20);
            push_u16(&mut bytes, u16::from(encrypted));
            push_u16(&mut bytes, method);
            push_u16(&mut bytes, 0);
            push_u16(&mut bytes, 0);
            push_u32(&mut bytes, crc);
            push_u32(&mut bytes, u32::try_from(compressed.len()).unwrap());
            push_u32(&mut bytes, u32::try_from(contents.len()).unwrap());
            push_u16(&mut bytes, u16::try_from(local_name.len()).unwrap());
            push_u16(&mut bytes, 0);
            bytes.extend_from_slice(local_name);
            bytes.extend_from_slice(&compressed);
            central.push(Central {
                name,
                crc,
                size: u32::try_from(contents.len()).unwrap(),
                compressed_size: u32::try_from(compressed.len()).unwrap(),
                method,
                offset,
            });
        }
        let central_offset = u32::try_from(bytes.len()).unwrap();
        for entry in &central {
            bytes.extend_from_slice(b"PK\x01\x02");
            push_u16(&mut bytes, 0x0314);
            push_u16(&mut bytes, 20);
            push_u16(&mut bytes, u16::from(encrypted));
            push_u16(&mut bytes, entry.method);
            push_u16(&mut bytes, 0);
            push_u16(&mut bytes, 0);
            push_u32(&mut bytes, entry.crc);
            push_u32(&mut bytes, entry.compressed_size);
            push_u32(&mut bytes, entry.size);
            push_u16(&mut bytes, u16::try_from(entry.name.len()).unwrap());
            push_u16(&mut bytes, 0);
            push_u16(&mut bytes, 0);
            push_u16(&mut bytes, 0);
            push_u16(&mut bytes, 0);
            push_u32(&mut bytes, 0o100_644 << 16);
            push_u32(&mut bytes, entry.offset);
            bytes.extend_from_slice(&entry.name);
        }
        let central_size = u32::try_from(bytes.len()).unwrap() - central_offset;
        bytes.extend_from_slice(b"PK\x05\x06");
        push_u16(&mut bytes, 0);
        push_u16(&mut bytes, 0);
        push_u16(&mut bytes, 3);
        push_u16(&mut bytes, 3);
        push_u32(&mut bytes, central_size);
        push_u32(&mut bytes, central_offset);
        push_u16(&mut bytes, 0);
        bytes
    }

    fn zip_with_deflated_directory() -> Vec<u8> {
        let cursor = Cursor::new(Vec::new());
        let mut writer = zip::ZipWriter::new(cursor);
        let options = zip::write::SimpleFileOptions::default()
            .compression_method(zip::CompressionMethod::Deflated);
        writer.start_file(format!("{ROOT}/"), options).unwrap();
        for leaf in ["shoutx.exe", "README.md", "LICENSE"] {
            writer
                .start_file(format!("{ROOT}/{leaf}"), options)
                .unwrap();
            writer.write_all(leaf.as_bytes()).unwrap();
        }
        writer.finish().unwrap().into_inner()
    }

    #[test]
    fn accepts_independently_constructed_archives() {
        let tar = temporary("tar.gz");
        let zip = temporary("zip");
        let deflated_zip = temporary("zip");
        let directory_zip = temporary("zip");
        fs::write(&tar, raw_tar(None)).unwrap();
        fs::write(&zip, raw_zip(None, false)).unwrap();
        fs::write(&deflated_zip, raw_zip_with_method(None, false, true)).unwrap();
        fs::write(&directory_zip, zip_with_deflated_directory()).unwrap();
        assert!(validate_tar(&tar, ROOT).is_ok());
        assert!(validate_zip(&zip, ROOT).is_ok());
        assert!(validate_zip(&deflated_zip, ROOT).is_ok());
        assert!(validate_zip(&directory_zip, ROOT).is_ok());
        fs::remove_file(tar).unwrap();
        fs::remove_file(zip).unwrap();
        fs::remove_file(deflated_zip).unwrap();
        fs::remove_file(directory_zip).unwrap();
    }

    #[test]
    fn rejects_path_affecting_global_pax_metadata() {
        let tar = temporary("tar.gz");
        fs::write(&tar, raw_tar(Some(b"13 path=evil\n"))).unwrap();
        assert_eq!(
            error_message(validate_tar(&tar, ROOT)),
            "global pax metadata is not permitted"
        );
        fs::remove_file(tar).unwrap();
    }

    #[test]
    fn rejects_zip_local_central_name_disagreement() {
        let zip = temporary("zip");
        let replacement = format!("{ROOT}/README.md");
        fs::write(&zip, raw_zip(Some(replacement.as_bytes()), false)).unwrap();
        assert_eq!(
            error_message(validate_zip(&zip, ROOT)),
            "ZIP local and central names disagree"
        );
        fs::remove_file(zip).unwrap();
    }

    #[test]
    fn rejects_zip_local_central_version_and_timestamp_disagreement() {
        let path = temporary("zip");

        let mut version = raw_zip(None, false);
        let eocd = version.len() - 22;
        let central_start = usize::try_from(super::u32_at(&version[eocd..], 16).unwrap()).unwrap();
        version[central_start + 6..central_start + 8].copy_from_slice(&21_u16.to_le_bytes());
        fs::write(&path, version).unwrap();
        assert_eq!(
            error_message(validate_zip(&path, ROOT)),
            "ZIP local and central metadata disagree"
        );

        let mut timestamp = raw_zip(None, false);
        let eocd = timestamp.len() - 22;
        let central_start =
            usize::try_from(super::u32_at(&timestamp[eocd..], 16).unwrap()).unwrap();
        timestamp[central_start + 12..central_start + 14].copy_from_slice(&1_u16.to_le_bytes());
        fs::write(&path, timestamp).unwrap();
        assert_eq!(
            error_message(validate_zip(&path, ROOT)),
            "ZIP local and central metadata disagree"
        );
        fs::remove_file(path).unwrap();
    }

    #[test]
    fn rejects_encryption_and_trailing_data() {
        let encrypted = temporary("zip");
        fs::write(&encrypted, raw_zip(None, true)).unwrap();
        assert_eq!(
            error_message(validate_zip(&encrypted, ROOT)),
            "encrypted ZIP entry"
        );
        fs::remove_file(encrypted).unwrap();

        let trailing = temporary("zip");
        let mut bytes = raw_zip(None, false);
        bytes.extend_from_slice(b"trailing");
        fs::write(&trailing, bytes).unwrap();
        assert_eq!(
            error_message(validate_zip(&trailing, ROOT)),
            "ZIP comment or trailing data is not permitted"
        );
        fs::remove_file(trailing).unwrap();

        let descriptor = temporary("zip");
        let mut bytes = raw_zip(None, false);
        let eocd = bytes.len() - 22;
        let central_start = usize::try_from(super::u32_at(&bytes[eocd..], 16).unwrap()).unwrap();
        bytes[6..8].copy_from_slice(&8_u16.to_le_bytes());
        bytes[central_start + 8..central_start + 10].copy_from_slice(&8_u16.to_le_bytes());
        fs::write(&descriptor, bytes).unwrap();
        assert_eq!(
            error_message(validate_zip(&descriptor, ROOT)),
            "encrypted or data-descriptor ZIP local entry"
        );
        fs::remove_file(descriptor).unwrap();
    }

    #[test]
    fn rejects_zip_prefix_extra_metadata_and_symlink() {
        let path = temporary("zip");

        let mut prefixed = raw_zip(None, false);
        prefixed.insert(0, 0);
        fs::write(&path, prefixed).unwrap();
        assert_eq!(
            error_message(validate_zip(&path, ROOT)),
            "prepended ZIP data is not permitted"
        );

        let mut extra = raw_zip(None, false);
        let old_eocd = extra.len() - 22;
        let central_start =
            usize::try_from(super::u32_at(&extra[old_eocd..], 16).unwrap()).unwrap();
        let name_len = usize::from(super::u16_at(&extra[central_start..], 28).unwrap());
        extra[central_start + 30..central_start + 32].copy_from_slice(&4_u16.to_le_bytes());
        extra.splice(
            central_start + 46 + name_len..central_start + 46 + name_len,
            [0x99, 0x99, 0, 0],
        );
        let eocd = extra.len() - 22;
        let central_size = super::u32_at(&extra[eocd..], 12).unwrap() + 4;
        extra[eocd + 12..eocd + 16].copy_from_slice(&central_size.to_le_bytes());
        fs::write(&path, extra).unwrap();
        assert_eq!(
            error_message(validate_zip(&path, ROOT)),
            "ZIP central extra metadata or comment is not permitted"
        );

        let mut symlink = raw_zip(None, false);
        let eocd = symlink.len() - 22;
        let central_start = usize::try_from(super::u32_at(&symlink[eocd..], 16).unwrap()).unwrap();
        symlink[central_start + 4..central_start + 6].copy_from_slice(&0x0314_u16.to_le_bytes());
        symlink[central_start + 38..central_start + 42]
            .copy_from_slice(&(0o120_777_u32 << 16).to_le_bytes());
        fs::write(&path, symlink).unwrap();
        assert_eq!(
            error_message(validate_zip(&path, ROOT)),
            "ZIP payload entry is not a regular file"
        );
        fs::remove_file(path).unwrap();
    }

    #[test]
    fn rejects_zip_payload_with_consistently_wrong_crc() {
        let path = temporary("zip");
        let mut bytes = raw_zip(None, false);
        let eocd = bytes.len() - 22;
        let central_start = usize::try_from(super::u32_at(&bytes[eocd..], 16).unwrap()).unwrap();
        bytes[14..18].copy_from_slice(&0_u32.to_le_bytes());
        bytes[central_start + 16..central_start + 20].copy_from_slice(&0_u32.to_le_bytes());
        fs::write(&path, bytes).unwrap();
        let error = error_message(validate_zip(&path, ROOT));
        assert!(error.to_ascii_lowercase().contains("checksum"), "{error}");
        fs::remove_file(path).unwrap();
    }

    #[test]
    fn rejects_data_after_deflate_end_marker() {
        let path = temporary("zip");
        let mut bytes = raw_zip_with_method(None, false, true);
        let first_name_len = usize::from(super::u16_at(&bytes, 26).unwrap());
        let first_compressed = super::u32_at(&bytes, 18).unwrap();
        let insertion = 30 + first_name_len + usize::try_from(first_compressed).unwrap();
        bytes.insert(insertion, 0);
        bytes[18..22].copy_from_slice(&(first_compressed + 1).to_le_bytes());

        let eocd = bytes.len() - 22;
        let old_central = super::u32_at(&bytes[eocd..], 16).unwrap();
        let new_central = old_central + 1;
        bytes[eocd + 16..eocd + 20].copy_from_slice(&new_central.to_le_bytes());
        let mut central = usize::try_from(new_central).unwrap();
        for index in 0..3 {
            if index == 0 {
                let size = super::u32_at(&bytes[central..], 20).unwrap();
                bytes[central + 20..central + 24].copy_from_slice(&(size + 1).to_le_bytes());
            } else {
                let offset = super::u32_at(&bytes[central..], 42).unwrap();
                bytes[central + 42..central + 46].copy_from_slice(&(offset + 1).to_le_bytes());
            }
            let name_len = usize::from(super::u16_at(&bytes[central..], 28).unwrap());
            central += 46 + name_len;
        }

        fs::write(&path, bytes).unwrap();
        assert_eq!(
            error_message(validate_zip(&path, ROOT)),
            "data after deflate end marker is not permitted"
        );
        fs::remove_file(path).unwrap();
    }

    #[test]
    fn accepts_deflate_compressor_option_flags() {
        let path = temporary("zip");
        let mut bytes = raw_zip_with_method(None, false, true);
        bytes[6..8].copy_from_slice(&2_u16.to_le_bytes());
        let eocd = bytes.len() - 22;
        let central = usize::try_from(super::u32_at(&bytes[eocd..], 16).unwrap()).unwrap();
        bytes[central + 8..central + 10].copy_from_slice(&2_u16.to_le_bytes());
        fs::write(&path, bytes).unwrap();
        assert!(validate_zip(&path, ROOT).is_ok());
        fs::remove_file(path).unwrap();
    }

    #[test]
    fn rejects_ambiguous_tar_metadata_and_trailing_data() {
        let mut gnu = tar_entry("././@LongLink", b'L', b"safe\0");
        gnu.resize(gnu.len() + 1024, 0);
        assert_eq!(
            error_message(validate_raw_tar(&gnu, ROOT)),
            "GNU path metadata is not permitted"
        );

        let pax = b"13 path=safe\n13 path=evil\n";
        let mut local_pax = tar_entry("PaxHeader", b'x', pax);
        local_pax.resize(local_pax.len() + 1024, 0);
        assert_eq!(
            error_message(validate_raw_tar(&local_pax, ROOT)),
            "local pax metadata is not permitted"
        );

        let mut trailing = tar_entry(&format!("{ROOT}/README.md"), b'0', b"readme");
        trailing.resize(trailing.len() + 1024, 0);
        trailing.extend_from_slice(b"non-zero");
        assert_eq!(
            error_message(validate_raw_tar(&trailing, ROOT)),
            "non-zero trailing tar data"
        );

        let mut prefixed = tar_entry(&format!("{ROOT}/shoutx"), b'0', b"binary");
        prefixed[345] = b'x';
        prefixed.resize(prefixed.len() + 1024, 0);
        assert_eq!(
            error_message(validate_raw_tar(&prefixed, ROOT)),
            "tar prefix field is not permitted"
        );

        let mut directory = tar_entry(&format!("{ROOT}/"), b'5', b"payload");
        directory.resize(directory.len() + 1024, 0);
        let path = temporary("tar.gz");
        fs::write(&path, gzip_tar(&directory)).unwrap();
        assert_eq!(
            error_message(validate_tar(&path, ROOT)),
            "top-level tar directory has payload data"
        );
        fs::remove_file(path).unwrap();

        let mut second_member = raw_tar(None);
        second_member.extend(gzip_tar(b"hidden"));
        let path = temporary("tar.gz");
        fs::write(&path, second_member).unwrap();
        assert_eq!(
            error_message(validate_tar(&path, ROOT)),
            "multiple gzip members or trailing data are not permitted"
        );

        let mut empty_member = raw_tar(None);
        empty_member.extend(gzip_tar(b""));
        fs::write(&path, empty_member).unwrap();
        assert_eq!(
            error_message(validate_tar(&path, ROOT)),
            "multiple gzip members or trailing data are not permitted"
        );
        fs::remove_file(path).unwrap();
    }

    #[test]
    fn rejects_nonzero_tar_entry_padding() {
        let mut tar = tar_entry(&format!("{ROOT}/README.md"), b'0', b"readme");
        tar[512 + 6] = b'x';
        tar.resize(tar.len() + 1024, 0);
        assert_eq!(
            error_message(validate_raw_tar(&tar, ROOT)),
            "non-zero tar entry padding"
        );
    }

    #[test]
    fn rejects_tar_links_and_duplicates() {
        let path = temporary("tar.gz");
        let mut tar = tar_entry(&format!("{ROOT}/"), b'5', b"");
        tar.extend(tar_entry(&format!("{ROOT}/shoutx"), b'2', b""));
        tar.extend(tar_entry(&format!("{ROOT}/README.md"), b'0', b"readme"));
        tar.extend(tar_entry(&format!("{ROOT}/LICENSE"), b'0', b"license"));
        tar.resize(tar.len() + 1024, 0);
        fs::write(&path, gzip_tar(&tar)).unwrap();
        assert_eq!(
            error_message(validate_tar(&path, ROOT)),
            "tar payload entry is not a regular file"
        );

        let mut tar = tar_entry(&format!("{ROOT}/"), b'5', b"");
        for name in ["shoutx", "shoutx", "README.md", "LICENSE"] {
            tar.extend(tar_entry(&format!("{ROOT}/{name}"), b'0', name.as_bytes()));
        }
        tar.resize(tar.len() + 1024, 0);
        fs::write(&path, gzip_tar(&tar)).unwrap();
        assert_eq!(
            error_message(validate_tar(&path, ROOT)),
            format!("duplicate archive path: {ROOT}/shoutx")
        );
        fs::remove_file(path).unwrap();
    }

    #[test]
    fn rejects_missing_and_unexpected_tar_members() {
        let path = temporary("tar.gz");
        let mut tar = tar_entry(&format!("{ROOT}/"), b'5', b"");
        for name in ["shoutx", "README.md"] {
            tar.extend(tar_entry(&format!("{ROOT}/{name}"), b'0', name.as_bytes()));
        }
        tar.resize(tar.len() + 1024, 0);
        fs::write(&path, gzip_tar(&tar)).unwrap();
        assert_eq!(
            error_message(validate_tar(&path, ROOT)),
            "tar does not contain the exact logical file set"
        );

        let mut tar = tar_entry(&format!("{ROOT}/"), b'5', b"");
        for name in ["shoutx", "README.md", "LICENSE", "unexpected"] {
            tar.extend(tar_entry(&format!("{ROOT}/{name}"), b'0', name.as_bytes()));
        }
        tar.resize(tar.len() + 1024, 0);
        fs::write(&path, gzip_tar(&tar)).unwrap();
        assert_eq!(
            error_message(validate_tar(&path, ROOT)),
            format!("unexpected archive path: {ROOT}/unexpected")
        );
        fs::remove_file(path).unwrap();
    }
}
