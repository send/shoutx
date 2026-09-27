use base64::{Engine as _, engine::general_purpose::STANDARD};
use serde::Serialize;
use std::{fs, path::PathBuf};

#[derive(Serialize)]
struct MaskCase {
    id: &'static str,
    command: String,
    value: String,
    masked: Vec<String>,
    unmasked: Vec<String>,
}

fn encode(value: &[u8]) -> String {
    STANDARD.encode(value)
}

fn cases() -> Vec<MaskCase> {
    [
        (
            "plain",
            b"secret".as_slice(),
            vec![b"before secret after".as_slice()],
            vec![b"public".as_slice()],
        ),
        (
            "percent-command-looking",
            b"literal%0A%0D%25%250A::warning::value".as_slice(),
            vec![b"literal%0A%0D%25%250A::warning::value".as_slice()],
            vec![b"warning".as_slice()],
        ),
        (
            "short-common-value",
            b"1".as_slice(),
            vec![b"build 1 of 2".as_slice()],
            vec![b"public".as_slice()],
        ),
        (
            "command-looking-value",
            b"::stop-commands::not-a-token".as_slice(),
            vec![b"::stop-commands::not-a-token".as_slice()],
            vec![b"not-a-token-only".as_slice()],
        ),
        (
            "multibyte-utf8",
            "秘密🔐".as_bytes(),
            vec!["before 秘密🔐 after".as_bytes()],
            vec!["公開".as_bytes()],
        ),
        (
            "trimmed-single-line",
            b" secret ".as_slice(),
            vec![b" secret ".as_slice(), b"secret".as_slice()],
            vec![b"other".as_slice()],
        ),
        (
            "multiline",
            b" first \r\nsecond\n\r third ".as_slice(),
            vec![
                b" first \r\nsecond\n\r third ".as_slice(),
                b"first".as_slice(),
                b"second".as_slice(),
                b"third".as_slice(),
            ],
            vec![b" ".as_slice(), b"  ".as_slice()],
        ),
    ]
    .into_iter()
    .map(|(id, value, masked, unmasked)| MaskCase {
        id,
        command: encode(&shoutx::github_actions::encode_mask(value.to_vec()).unwrap()),
        value: encode(value),
        masked: masked.into_iter().map(encode).collect(),
        unmasked: unmasked.into_iter().map(encode).collect(),
    })
    .collect()
}

#[test]
fn generated_commands_have_one_physical_line() {
    for case in cases() {
        let command = STANDARD.decode(case.command).unwrap();
        assert!(command.starts_with(b"::add-mask::"));
        assert!(command.ends_with(b"\n"));
        assert!(!command[..command.len() - 1].contains(&b'\r'));
        assert!(!command[..command.len() - 1].contains(&b'\n'));
    }
}

#[test]
#[ignore = "writes the generated corpus for the pinned runner oracle job"]
fn export_mask_corpus() {
    let path = PathBuf::from(std::env::var_os("SHOUTX_MASK_CORPUS_PATH").unwrap());
    fs::write(path, serde_json::to_vec_pretty(&cases()).unwrap()).unwrap();
}
