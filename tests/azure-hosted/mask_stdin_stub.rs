//! Test-only native stdin sink. Never writes captured values to stdout/stderr.
use std::io::{Read, Write};

fn main() {
    let args: Vec<_> = std::env::args_os().skip(1).collect();
    if std::env::var_os("SHOUTX_STUB_SECRET_VARIABLE").is_some() {
        let mut expected = vec!["azure-pipelines:secret-variable"];
        if std::env::var_os("SHOUTX_STUB_OUTPUT").is_some() {
            expected.push("--output");
        }
        if std::env::var_os("SHOUTX_STUB_READ_ONLY").is_some() {
            expected.push("--read-only");
        }
        expected.extend(["--", "Credential"]);
        assert!(args == expected);
    } else {
        assert!(args == ["azure-pipelines:mask"] || args == ["azure-pipelines:mask", "--each-line"]);
    }
    let mut input = Vec::new();
    std::io::stdin().read_to_end(&mut input).unwrap();
    let path = std::env::var_os("SHOUTX_STUB_CAPTURE").unwrap();
    std::fs::File::create(path).unwrap().write_all(&input).unwrap();
    if std::env::var_os("SHOUTX_STUB_FAIL").is_some() {
        std::process::exit(1);
    }
}
