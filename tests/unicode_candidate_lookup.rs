//! Research only: this predicate is not used by the CLI.
use std::hint::black_box;
use std::time::Instant;

fn ranges() -> Vec<[u32; 2]> {
    let table: serde_json::Value =
        serde_json::from_str(include_str!("runner-package/unicode-candidate.json")).unwrap();
    serde_json::from_value(table["ranges"].clone()).unwrap()
}

fn ascii(value: &str) -> bool {
    matches!(value.as_bytes().first(), Some(b' '..=b'~' | b'\r' | b'\n'))
}

// Input is already UTF-8 validated, as in the existing command pipeline.
// No suffix scan, normalization, allocation, or runtime Unicode query.
fn candidate(value: &str, ranges: &[[u32; 2]]) -> bool {
    if ascii(value) {
        return true;
    }
    let Some(first) = value.chars().next() else {
        return false;
    };
    let cp = u32::from(first);
    ranges
        .binary_search_by(|[start, end]| {
            if *end < cp {
                std::cmp::Ordering::Less
            } else if *start > cp {
                std::cmp::Ordering::Greater
            } else {
                std::cmp::Ordering::Equal
            }
        })
        .is_ok()
}

#[test]
fn lookup_matches_table_union_existing_ascii_policy() {
    let ranges = ranges();
    assert_eq!(ranges.len(), 757);
    let mut membership = vec![false; 0x110000];
    for [start, end] in &ranges {
        for cp in *start..=*end {
            assert!(!membership[cp as usize]);
            membership[cp as usize] = true;
        }
    }
    assert_eq!(membership.iter().filter(|v| **v).count(), 142081);
    let mut buffer = [0; 4];
    for cp in 0..=0x10ffff {
        if let Some(ch) = char::from_u32(cp) {
            let value = ch.encode_utf8(&mut buffer);
            assert_eq!(
                candidate(value, &ranges),
                ascii(value) || membership[cp as usize]
            );
        }
    }
    assert!(!candidate("", &ranges));
}

#[test]
#[ignore = "manual release-mode microbenchmark; not a CI timing gate"]
// Only this manual measurement prints results and rejects a debug-mode run.
#[allow(clippy::print_stderr, clippy::assertions_on_constants)]
fn benchmark_candidate_lookup() {
    assert!(!cfg!(debug_assertions), "run with --release");
    let ranges = ranges(); // Deliberately outside timing; not a runtime JSON-loading proposal.
    let iterations = 2_000_000;
    for (name, prefix) in [
        ("ascii", "A"),
        ("japanese", "日"),
        ("emoji", "😀"),
        ("rejected", "\u{301}"),
    ] {
        for length in [16, 4096, 1_048_576] {
            let value = format!("{prefix}{}", "x".repeat(length - prefix.len()));
            for use_candidate in [false, true] {
                let start = Instant::now();
                for _ in 0..iterations {
                    black_box(if use_candidate {
                        candidate(black_box(&value), black_box(&ranges))
                    } else {
                        ascii(black_box(&value))
                    });
                }
                eprintln!(
                    "{name} bytes={length} candidate={use_candidate} ns/lookup={:.2}",
                    start.elapsed().as_nanos() as f64 / f64::from(iterations)
                );
            }
        }
    }
}
