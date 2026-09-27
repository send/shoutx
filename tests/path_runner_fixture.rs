use std::{env, fs};

use base64::{Engine as _, engine::general_purpose::STANDARD};
use serde::{Deserialize, Serialize};

#[path = "support/runner_path.rs"]
mod runner_path;

use runner_path::{effective, parse};

#[derive(Deserialize, Serialize)]
struct PathCase {
    id: String,
    input: String,
    paths: Vec<String>,
    effective: Vec<String>,
}

#[test]
fn local_path_model_matches_shared_corpus() {
    for case in corpus() {
        let input = STANDARD.decode(&case.input).unwrap();
        let paths = parse(&input).unwrap();
        assert_eq!(encode(&paths), case.paths, "{} paths", case.id);
        assert_eq!(
            encode(&effective(&paths)),
            case.effective,
            "{} effective",
            case.id
        );
    }
}

#[test]
#[ignore = "writes the generated corpus for the pinned runner oracle job"]
fn export_path_corpus() {
    let path = env::var_os("SHOUTX_PATH_CORPUS_PATH").expect("SHOUTX_PATH_CORPUS_PATH is required");
    fs::write(path, serde_json::to_vec_pretty(&corpus()).unwrap()).unwrap();
}

fn corpus() -> Vec<PathCase> {
    [
        ("empty", b"".as_slice()),
        ("lf", b"/a\n/b\n"),
        ("crlf", b"/a\r\n/b\r\n"),
        ("bare-cr", b"/a\r/b\r"),
        ("mixed", b"/a\r\n\r/b\n/c"),
        ("initial-bom", b"\xef\xbb\xbf/a\n"),
        ("embedded-bom", b"/a\n\xef\xbb\xbf/b\n"),
        ("whitespace", b"\n \n\t\n"),
        ("duplicates", b"/a\n/b\n/a\n"),
    ]
    .into_iter()
    .map(|(id, input)| {
        let paths = parse(input).unwrap();
        PathCase {
            id: id.to_owned(),
            input: STANDARD.encode(input),
            effective: encode(&effective(&paths)),
            paths: encode(&paths),
        }
    })
    .collect()
}

fn encode(values: &[Vec<u8>]) -> Vec<String> {
    values.iter().map(|value| STANDARD.encode(value)).collect()
}
