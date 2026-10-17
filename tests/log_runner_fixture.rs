use base64::{Engine as _, engine::general_purpose::STANDARD};
use serde::Serialize;
use shoutx::{cli::LogKind, github_actions::encode_log};

#[derive(Serialize)]
struct Case {
    wire: String,
    command: &'static str,
    data: String,
}

fn cases() -> Vec<Case> {
    let mut cases = Vec::new();
    for (command, kind) in [("debug", LogKind::Debug), ("group", LogKind::Group)] {
        for start in ["", " ", "A", "Ε", "ع", "क", "日", "😀", "𐐀"] {
            for tail in [
                "",
                "literal%0A::error::x##[warning]tail",
                "\u{301}\u{200d}x",
            ] {
                let data = format!("{start}{tail}");
                let Ok(wire) = encode_log(kind, data.clone().into_bytes()) else {
                    continue;
                };
                cases.push(Case {
                    wire: STANDARD.encode(wire),
                    command,
                    data,
                });
            }
        }
    }
    for data in [
        "a\r\nb\rc\n\n",
        "\n::error::literal\n##[endgroup]literal",
        "A\u{85}\u{2028}\u{2029}tail",
    ] {
        // Append framing so all data line endings are retained by the producer.
        let wire = encode_log(LogKind::Debug, format!("{data}\n").into_bytes()).unwrap();
        cases.push(Case {
            wire: STANDARD.encode(wire),
            command: "debug",
            data: data.into(),
        });
    }
    cases.push(Case {
        wire: STANDARD.encode(b"::endgroup::\n"),
        command: "endgroup",
        data: String::new(),
    });
    cases
}

#[test]
fn corpus_has_explicit_commands_and_one_wire_line() {
    let cases = cases();
    assert_eq!(cases.len(), 56);
    for case in cases {
        let wire = STANDARD.decode(case.wire).unwrap();
        assert!(wire.starts_with(format!("::{}::", case.command).as_bytes()));
        assert_eq!(wire.iter().filter(|byte| **byte == b'\n').count(), 1);
        assert!(!wire.contains(&b'\r'));
    }
}

#[test]
#[ignore = "exports fresh producer records for the pinned runner"]
fn export_log_corpus() {
    let path = std::env::var_os("SHOUTX_LOG_CORPUS_PATH").expect("missing corpus path");
    std::fs::write(path, serde_json::to_vec(&cases()).unwrap()).unwrap();
}
