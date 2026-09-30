use base64::{Engine as _, engine::general_purpose::STANDARD};
use serde::Serialize;
use std::{fs, path::PathBuf};

#[derive(Serialize)]
struct MaskCase {
    id: String,
    command: String,
    value: String,
    masked: Vec<String>,
    unmasked: Vec<String>,
}

fn encode(value: &[u8]) -> String {
    STANDARD.encode(value)
}

fn cases() -> Vec<MaskCase> {
    let mut cases: Vec<_> = [
        (
            "plain",
            b"secret".as_slice(),
            vec![b"before secret after".as_slice()],
            vec![b"public".as_slice()],
        ),
        (
            "interior-combining",
            "e\u{0301} ##[warning]literal".as_bytes(),
            vec!["e\u{0301} ##[warning]literal".as_bytes()],
            vec![b"public".as_slice()],
        ),
        (
            "format-before-combining",
            "a\u{200b}\u{0301}secret ##[warning]literal".as_bytes(),
            vec!["a\u{200b}\u{0301}secret ##[warning]literal".as_bytes()],
            vec![b"public".as_slice()],
        ),
        (
            "bom-before-combining",
            "a\u{feff}\u{0301}secret".as_bytes(),
            vec!["a\u{feff}\u{0301}secret".as_bytes()],
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
            "a秘密🔐".as_bytes(),
            vec!["before a秘密🔐 after".as_bytes()],
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
        id: id.to_owned(),
        command: encode(&shoutx::github_actions::encode_mask(value.to_vec()).unwrap()),
        value: encode(value),
        masked: masked.into_iter().map(encode).collect(),
        unmasked: unmasked.into_iter().map(encode).collect(),
    })
    .collect();
    for (id, prefix) in [
        ("zwj", "\u{200d}"),
        ("zwnj", "\u{200c}"),
        ("transparent-chain", "\u{200c}\u{200d}\u{e0020}\u{e007f}"),
        (
            "transparent-control-before-combining",
            "\u{200d}\u{200b}\u{0301}",
        ),
        ("tag-space", "\u{e0020}"),
        ("cancel-tag", "\u{e007f}"),
        ("space-before-combining", " \u{0301}"),
    ] {
        let value = format!("a{prefix}secret ##[warning]literal");
        cases.push(MaskCase {
            id: id.to_owned(),
            command: encode(
                &shoutx::github_actions::encode_mask(value.as_bytes().to_vec()).unwrap(),
            ),
            value: encode(value.as_bytes()),
            masked: vec![encode(value.as_bytes())],
            unmasked: vec![encode(b"public")],
        });
    }
    for first in (b' '..=b'~').chain(*b"\r\n") {
        for (index, tail) in [
            "\u{0301}",
            "\u{200d}\u{0301}",
            "\u{0e33}",
            "\u{0eb3}",
            "\u{1f3fb}",
            "\u{e0020}\u{1f3fb}",
            "日本語😀",
            "\u{10ffff}",
        ]
        .into_iter()
        .enumerate()
        {
            let value = format!("{}{tail} ##[warning]literal::tail", char::from(first));
            cases.push(MaskCase {
                id: format!("ascii-boundary-{first}-{index}"),
                command: encode(
                    &shoutx::github_actions::encode_mask(value.as_bytes().to_vec()).unwrap(),
                ),
                value: encode(value.as_bytes()),
                masked: vec![encode(value.as_bytes())],
                unmasked: vec![encode(b"public")],
            });
        }
    }
    cases
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
