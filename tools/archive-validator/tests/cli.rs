use std::fs;
use std::process::Command;
use std::sync::atomic::{AtomicU64, Ordering};

static NEXT_FILE: AtomicU64 = AtomicU64::new(0);

#[test]
fn invalid_archive_has_stable_process_contract() {
    let sequence = NEXT_FILE.fetch_add(1, Ordering::Relaxed);
    let archive = std::env::temp_dir().join(format!(
        "shoutx-archive-validator-cli-{}-{sequence}.tar.gz",
        std::process::id()
    ));
    fs::write(&archive, b"not a gzip archive").unwrap();

    let output = Command::new(env!("CARGO_BIN_EXE_shoutx-archive-validator"))
        .arg(&archive)
        .arg("shoutx-v0.0.0-test")
        .output()
        .unwrap();

    assert_eq!(output.status.code(), Some(1));
    assert!(output.stdout.is_empty());
    assert_eq!(output.stderr, b"archive validation failed\n");
    fs::remove_file(archive).unwrap();
}
