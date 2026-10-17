use base64::{Engine as _, engine::general_purpose::STANDARD};
use serde::Serialize;
use shoutx::{cli::MatcherKind, github_actions::encode_matcher};

#[derive(Serialize)]
struct Case {
    wire: String,
    command: &'static str,
    data: String,
    owner: Option<String>,
}

fn cases() -> Vec<Case> {
    let mut result = Vec::new();
    for (kind, command) in [
        (MatcherKind::AddFile, "add-matcher"),
        (MatcherKind::RemoveFile, "remove-matcher"),
    ] {
        for data in [
            "matcher.json",
            "./α_العربية_हिन्दी_日本語_😀.json",
            "file%0A.json",
            "file\r\n::warning::literal",
            "file##[error]literal",
            "A\u{301}\u{200d}tail",
            " file ",
        ] {
            result.push(Case {
                wire: STANDARD.encode(encode_matcher(kind, data.as_bytes().to_vec()).unwrap()),
                command,
                data: data.into(),
                owner: None,
            });
        }
    }
    for owner in [
        "target",
        " ",
        "\t",
        "a ",
        "a\u{a0}",
        "a\u{301}",
        "\u{200b}",
        "\u{301}",
        "Ελληνικά_العربية_हिन्दी_日本語_😀",
        "%0A",
        "a,b::c=d",
        "a==b",
        "a\r\nb",
        "a\n",
        "##[warning]x",
        "-x",
    ] {
        result.push(Case {
            wire: STANDARD.encode(
                encode_matcher(MatcherKind::RemoveOwner, format!("{owner}\n").into_bytes())
                    .unwrap(),
            ),
            command: "remove-matcher",
            data: String::new(),
            owner: Some(owner.into()),
        });
    }
    result
}

#[test]
fn fresh_corpus_has_one_line_per_command() {
    let cases = cases();
    assert_eq!(cases.len(), 30);
    for item in cases {
        let wire = STANDARD.decode(item.wire).unwrap();
        assert_eq!(wire.iter().filter(|byte| **byte == b'\n').count(), 1);
        assert!(!wire.contains(&b'\r'));
    }
}

#[test]
#[ignore = "exports fresh producer records for the pinned runner"]
fn export_matcher_corpus() {
    let path = std::env::var_os("SHOUTX_MATCHER_CORPUS_PATH").expect("missing corpus path");
    std::fs::write(path, serde_json::to_vec(&cases()).unwrap()).unwrap();
}
