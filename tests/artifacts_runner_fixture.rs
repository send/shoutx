use base64::{Engine as _, engine::general_purpose::STANDARD};
use serde::Serialize;
use shoutx::github_actions::{encode_artifact_file, encode_artifact_oci};

#[derive(Serialize)]
struct Case {
    wire: String,
    name: String,
    digest: String,
    kind: String,
}

fn corpus() -> Vec<Case> {
    let mut cases = Vec::new();
    // The handler fixture creates each file with the known bytes "abc".
    for name in [
        "report",
        "#report",
        " leading",
        "δοκιμή_日本語_😀",
        "a\u{feff}",
        "a\u{200b}",
    ] {
        for ending in ["", "\r\n"] {
            cases.push(Case {
                wire: STANDARD
                    .encode(encode_artifact_file(format!("{name}{ending}").into_bytes()).unwrap()),
                name: name.into(),
                digest: "sha256:ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
                    .into(),
                kind: "file".into(),
            });
        }
    }
    for (algorithm, size) in [("sha256", 64), ("sha384", 96), ("sha512", 128)] {
        for name in [
            "registry:5000/image:tag",
            "a@b",
            "file://path",
            " 日本語_😀 ",
            "a\u{2028}b",
        ] {
            let digest = format!("{algorithm}:{}", "a".repeat(size));
            cases.push(Case {
                wire: STANDARD
                    .encode(encode_artifact_oci(name.as_bytes(), digest.as_bytes()).unwrap()),
                name: name.into(),
                digest,
                kind: "oci".into(),
            });
        }
    }
    cases
}

#[test]
fn producer_corpus_has_single_line_and_explicit_kind() {
    let cases = corpus();
    assert_eq!(cases.len(), 27);
    for case in cases {
        let wire = STANDARD.decode(case.wire).unwrap();
        assert_eq!(wire.iter().filter(|b| **b == b'\n').count(), 1);
        assert!(!wire.contains(&b'\r'));
        assert!(wire.starts_with(format!("{}://", case.kind).as_bytes()));
    }
}

#[test]
#[ignore = "exports fresh producer records for the pinned runner"]
fn export_artifacts_corpus() {
    let path = std::env::var_os("SHOUTX_ARTIFACTS_CORPUS_PATH").expect("missing corpus path");
    std::fs::write(path, serde_json::to_vec(&corpus()).unwrap()).unwrap();
}
