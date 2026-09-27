use base64::{Engine as _, engine::general_purpose::STANDARD};
use serde::{Deserialize, Serialize};
use shoutx::{
    ShoutxError,
    cli::{Destination, LineMode, WriteRequest},
    github_actions::{RandomSource, TargetOs},
};
use std::{ffi::OsString, fs};

mod support;

use support::runner_parser::{Platform, parse};

#[derive(Deserialize, Serialize)]
struct CorpusCase {
    id: String,
    input: String,
    success: bool,
    records: Vec<CorpusRecord>,
    #[serde(default)]
    windows_records: Option<Vec<CorpusRecord>>,
}

#[derive(Debug, Deserialize, Eq, PartialEq, Serialize)]
struct CorpusRecord {
    name: String,
    value: String,
}

#[test]
fn local_model_matches_shared_runner_corpus() {
    let corpus = corpus();
    for (platform, windows) in [(Platform::Posix, false), (Platform::Windows, true)] {
        for item in &corpus {
            let input = STANDARD.decode(&item.input).unwrap();
            let actual = parse(&input, platform);
            assert_eq!(actual.is_ok(), item.success, "{}", item.id);
            if let Ok(records) = actual {
                let expected = if windows {
                    item.windows_records.as_ref().unwrap_or(&item.records)
                } else {
                    &item.records
                };
                let encoded: Vec<CorpusRecord> = records
                    .into_iter()
                    .map(|(name, value)| CorpusRecord {
                        name: STANDARD.encode(name),
                        value: STANDARD.encode(value),
                    })
                    .collect();
                assert_eq!(encoded.as_slice(), expected.as_slice(), "{}", item.id);
            }
        }
    }
}

#[test]
#[ignore = "writes the generated corpus for the pinned runner oracle job"]
fn export_runner_corpus() {
    let path = std::env::var_os("SHOUTX_CORPUS_PATH").expect("SHOUTX_CORPUS_PATH is required");
    fs::write(path, serde_json::to_vec_pretty(&corpus()).unwrap()).unwrap();
}

fn corpus() -> Vec<CorpusCase> {
    let mut cases = vec![
        success("empty", b"", &[], None),
        success("single", b"a=1\n", &[(b"a", b"1")], None),
        success("unterminated-single", b"a=1", &[(b"a", b"1")], None),
        success("empty-value", b"a=\n", &[(b"a", b"")], None),
        success("empty-name", b"=value\n", &[(b"", b"value")], None),
        success(
            "equals-before-heredoc",
            b"a=b<<c\n",
            &[(b"a", b"b<<c")],
            None,
        ),
        success(
            "heredoc-before-equals",
            b"a<<b=c\nvalue\nb=c\n",
            &[(b"a", b"value")],
            None,
        ),
        success("empty-multiline", b"a<<X\nX\n", &[(b"a", b"")], None),
        success(
            "multiple-records",
            b"a=1\n\nb<<X\ntwo\nlines\nX\nc=3\n",
            &[(b"a", b"1"), (b"b", b"two\nlines"), (b"c", b"3")],
            None,
        ),
        success("utf8-bom", b"\xef\xbb\xbfa=1\n", &[(b"a", b"1")], None),
        success(
            "platform-crlf",
            b"a<<X\r\nv\r\nX\r\n",
            &[(b"a", b"v\r")],
            Some(&[(b"a", b"v")]),
        ),
        success(
            "windows-trailing-bare-cr",
            b"a<<X\nv\r\r\nX\n",
            &[(b"a", b"v\r\r")],
            Some(&[(b"a", b"v\r")]),
        ),
        failure("invalid-header", b"invalid\n"),
        failure("empty-delimiter", b"a<<\n"),
        failure("empty-heredoc-name", b"<<X\nX\n"),
        failure("missing-marker", b"a<<X\nvalue\n"),
        failure("marker-after-unterminated-value", b"a<<X\nvalue"),
        failure("trailing-invalid-record", b"a<<X\nv\nX\ninvalid\n"),
    ];

    for index in 0_u8..128 {
        let name = format!("generated_{index}");
        let mut value = generated_value(index);
        let target_os = if index % 2 == 0 {
            TargetOs::Windows
        } else {
            TargetOs::Linux
        };
        if target_os == TargetOs::Windows && index % 4 == 0 {
            value.push('\r');
        } else if value.ends_with('\r') {
            value.push('x');
        }
        if index % 16 == 0 {
            value.push_str("SHOUTX_");
            value.push_str(&format!("{index:02x}").repeat(32));
        }
        let mut random = SequenceRandom(index);
        let mut input = shoutx::github_actions::encode_with(
            WriteRequest {
                destination: Destination::Output,
                mode: LineMode::Multiline,
                name: OsString::from(&name),
                value: None,
            },
            value.as_bytes().to_vec(),
            target_os,
            &mut random,
        )
        .unwrap();
        input.extend_from_slice(b"after=ok\n");
        let expected = vec![
            (name.into_bytes(), value.into_bytes()),
            (b"after".to_vec(), b"ok".to_vec()),
        ];
        let target_platform = if target_os == TargetOs::Windows {
            Platform::Windows
        } else {
            Platform::Posix
        };
        assert_eq!(parse(&input, target_platform).unwrap(), expected);
        cases.push(success_owned_platform(
            format!("generated-{index:03}"),
            input,
        ));
    }
    cases
}

fn generated_value(seed: u8) -> String {
    const PARTS: [&str; 10] = [
        "a",
        "雪",
        "\n",
        "\r",
        "\r\n",
        "=",
        "<<",
        "SHOUTX_0000000000000000000000000000000",
        "\u{feff}",
        "\u{2028}",
    ];
    let mut state = u64::from(seed) + 1;
    let mut value = String::new();
    for _ in 0..32 {
        state = state
            .wrapping_mul(6_364_136_223_846_793_005)
            .wrapping_add(1);
        value.push_str(PARTS[(state as usize) % PARTS.len()]);
    }
    value
}

struct SequenceRandom(u8);

impl RandomSource for SequenceRandom {
    fn fill(&mut self, destination: &mut [u8]) -> Result<(), ShoutxError> {
        destination.fill(self.0);
        self.0 = self.0.wrapping_add(1);
        Ok(())
    }
}

fn success(
    id: &str,
    input: &[u8],
    records: &[(&[u8], &[u8])],
    windows_records: Option<&[(&[u8], &[u8])]>,
) -> CorpusCase {
    CorpusCase {
        id: id.to_owned(),
        input: STANDARD.encode(input),
        success: true,
        records: encode_records(records),
        windows_records: windows_records.map(encode_records),
    }
}

fn success_owned_platform(id: String, input: Vec<u8>) -> CorpusCase {
    let records = encode_owned_records(parse(&input, Platform::Posix).unwrap());
    let windows = encode_owned_records(parse(&input, Platform::Windows).unwrap());
    let windows_records = (windows != records).then_some(windows);
    CorpusCase {
        id,
        input: STANDARD.encode(input),
        success: true,
        records,
        windows_records,
    }
}

fn encode_owned_records(records: Vec<(Vec<u8>, Vec<u8>)>) -> Vec<CorpusRecord> {
    records
        .into_iter()
        .map(|(name, value)| CorpusRecord {
            name: STANDARD.encode(name),
            value: STANDARD.encode(value),
        })
        .collect()
}

fn failure(id: &str, input: &[u8]) -> CorpusCase {
    CorpusCase {
        id: id.to_owned(),
        input: STANDARD.encode(input),
        success: false,
        records: Vec::new(),
        windows_records: None,
    }
}

fn encode_records(records: &[(&[u8], &[u8])]) -> Vec<CorpusRecord> {
    records
        .iter()
        .map(|(name, value)| CorpusRecord {
            name: STANDARD.encode(name),
            value: STANDARD.encode(value),
        })
        .collect()
}
