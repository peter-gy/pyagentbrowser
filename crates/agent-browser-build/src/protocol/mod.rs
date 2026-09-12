mod generate;
mod model;
mod names;

use crate::source::require_file;
use generate::generate_domain;
use model::*;
use std::{collections::HashSet, fs, path::Path};

pub(crate) fn generate(protocol_dir: &Path, out_dir: &Path) {
    let generator_path = protocol_dir
        .parent()
        .expect("protocol parent")
        .join("build.rs");
    require_file(&generator_path);
    let generator = fs::read_to_string(&generator_path)
        .expect("read upstream protocol generator")
        .replace("\r\n", "\n");
    // Changes to upstream generation require a parity audit of this generator.
    let fingerprint = generator
        .bytes()
        .fold(0xcbf29ce484222325_u64, |hash, byte| {
            (hash ^ u64::from(byte)).wrapping_mul(0x100000001b3)
        });
    assert_eq!(fingerprint, 0x59c5df7f424eb649, "{}: upstream protocol generator changed. Audit protocol generation before updating its fingerprint", generator_path.display());
    let out_path = out_dir.join("cdp_generated.rs");

    let browser_path = protocol_dir.join("browser_protocol.json");
    let js_path = protocol_dir.join("js_protocol.json");

    require_file(&browser_path);
    require_file(&js_path);

    let mut all_domains: Vec<Domain> = Vec::new();

    for path in [&browser_path, &js_path] {
        if !path.exists() {
            continue;
        }
        let content = fs::read_to_string(path).unwrap();
        let protocol: ProtocolSpec = match serde_json::from_str(&content) {
            Ok(p) => p,
            Err(e) => {
                panic!("failed to parse protocol {}: {}", path.display(), e);
            }
        };
        all_domains.extend(protocol.domains);
    }

    // Collect all known type IDs per domain for cross-domain resolution
    let mut domain_types: std::collections::HashMap<String, HashSet<String>> =
        std::collections::HashMap::new();
    for domain in &all_domains {
        let mut types = HashSet::new();
        for td in &domain.types {
            types.insert(td.id.clone());
        }
        domain_types.insert(domain.name.clone(), types);
    }

    // Known recursive struct fields that need Box wrapping
    let recursive_fields: HashSet<(&str, &str, &str)> = [
        ("DOM", "Node", "contentDocument"),
        ("DOM", "Node", "templateContent"),
        ("DOM", "Node", "importedDocument"),
        ("Accessibility", "AXNode", "sources"),
        ("Runtime", "StackTrace", "parent"),
    ]
    .into_iter()
    .collect();

    let mut output = String::new();
    output.push_str("use serde::{Deserialize, Serialize};\n\n");

    for domain in &all_domains {
        generate_domain(domain, &domain_types, &recursive_fields, &mut output);
    }

    fs::write(&out_path, &output).unwrap();
}
