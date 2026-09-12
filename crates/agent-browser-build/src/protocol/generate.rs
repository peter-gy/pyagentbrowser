use super::{model::*, names::*};
use std::{
    collections::HashSet,
    fmt::{Arguments, Write as _},
};

fn resolve_ref(
    r: &str,
    current_domain: &str,
    domain_types: &std::collections::HashMap<String, HashSet<String>>,
) -> String {
    let parts: Vec<&str> = r.split('.').collect();
    if parts.len() == 2 {
        let ref_domain = parts[0];
        let ref_type = parts[1];
        if ref_domain == current_domain {
            to_pascal_case(ref_type)
        } else {
            if domain_types
                .get(ref_domain)
                .is_some_and(|t| t.contains(ref_type))
            {
                format!(
                    "super::cdp_{}::{}",
                    to_snake_case(ref_domain),
                    to_pascal_case(ref_type)
                )
            } else {
                // Fall back to serde_json::Value for unknown cross-domain refs
                "serde_json::Value".to_string()
            }
        }
    } else {
        to_pascal_case(r)
    }
}

fn map_type_in_domain(
    prop: &Property,
    current_domain: &str,
    domain_types: &std::collections::HashMap<String, HashSet<String>>,
) -> String {
    if let Some(ref r) = prop.ref_type {
        let type_name = resolve_ref(r, current_domain, domain_types);
        if prop.optional {
            format!("Option<{}>", type_name)
        } else {
            type_name
        }
    } else if let Some(ref t) = prop.type_kind {
        let base = match t.as_str() {
            "string" => "String".to_string(),
            "integer" => "i64".to_string(),
            "number" => "f64".to_string(),
            "boolean" => "bool".to_string(),
            "object" => "serde_json::Value".to_string(),
            "any" => "serde_json::Value".to_string(),
            "array" => {
                if let Some(ref items) = prop.items {
                    let inner = if let Some(ref r) = items.ref_type {
                        resolve_ref(r, current_domain, domain_types)
                    } else {
                        match items.type_kind.as_deref().unwrap_or("any") {
                            "string" => "String".to_string(),
                            "integer" => "i64".to_string(),
                            "number" => "f64".to_string(),
                            "boolean" => "bool".to_string(),
                            _ => "serde_json::Value".to_string(),
                        }
                    };
                    format!("Vec<{}>", inner)
                } else {
                    "Vec<serde_json::Value>".to_string()
                }
            }
            _ => "serde_json::Value".to_string(),
        };
        if prop.optional {
            format!("Option<{}>", base)
        } else {
            base
        }
    } else if prop.optional {
        "Option<serde_json::Value>".to_string()
    } else {
        "serde_json::Value".to_string()
    }
}

fn write_generated(output: &mut String, args: Arguments<'_>) {
    output
        .write_fmt(args)
        .expect("writing generated Rust to String should not fail");
}

pub(super) fn generate_domain(
    domain: &Domain,
    domain_types: &std::collections::HashMap<String, HashSet<String>>,
    recursive_fields: &HashSet<(&str, &str, &str)>,
    output: &mut String,
) {
    let mod_name = to_snake_case(&domain.name);
    write_generated(
        output,
        format_args!(
            "#[allow(dead_code, non_snake_case, non_camel_case_types, clippy::enum_variant_names)]\npub mod cdp_{mod_name} {{\n"
        ),
    );
    output.push_str("    use super::*;\n\n");

    for type_def in &domain.types {
        if !type_def.enum_values.is_empty() {
            // Deduplicate enum variants (some CDP enums have duplicated PascalCase forms)
            let mut seen_variants = HashSet::new();
            output.push_str("    #[derive(Debug, Clone, Serialize, Deserialize)]\n");
            write_generated(output, format_args!("    pub enum {} {{\n", type_def.id));
            for val in &type_def.enum_values {
                let mut variant = to_pascal_case(val);
                if variant == "Self" {
                    variant = "SelfValue".to_string();
                }
                if variant.chars().next().is_some_and(|c| c.is_ascii_digit()) {
                    variant = format!("V{}", variant);
                }
                if seen_variants.insert(variant.clone()) {
                    write_generated(
                        output,
                        format_args!("        #[serde(rename = \"{val}\")]\n        {variant},\n"),
                    );
                }
            }
            output.push_str("    }\n\n");
        } else if type_def.type_kind == "object" && !type_def.properties.is_empty() {
            output.push_str(
                "    #[derive(Debug, Clone, Serialize, Deserialize)]\n    #[serde(rename_all = \"camelCase\")]\n",
            );
            write_generated(output, format_args!("    pub struct {} {{\n", type_def.id));
            for prop in &type_def.properties {
                let field_name = to_snake_case(&prop.name);
                let field_name = if is_rust_keyword(&field_name) {
                    format!("r#{}", field_name)
                } else {
                    field_name
                };
                let mut rust_type = map_type_in_domain(prop, &domain.name, domain_types);

                // Wrap recursive fields in Box
                if recursive_fields.contains(&(
                    domain.name.as_str(),
                    type_def.id.as_str(),
                    prop.name.as_str(),
                )) {
                    if rust_type.starts_with("Option<") {
                        let inner = &rust_type[7..rust_type.len() - 1];
                        rust_type = format!("Option<Box<{}>>", inner);
                    } else {
                        rust_type = format!("Box<{}>", rust_type);
                    }
                }

                if prop.optional {
                    output
                        .push_str("        #[serde(skip_serializing_if = \"Option::is_none\")]\n");
                }
                write_generated(
                    output,
                    format_args!("        pub {field_name}: {rust_type},\n"),
                );
            }
            output.push_str("    }\n\n");
        } else if type_def.type_kind == "object" && type_def.properties.is_empty() {
            write_generated(
                output,
                format_args!("    pub type {} = serde_json::Value;\n\n", type_def.id),
            );
        } else if type_def.type_kind == "array" {
            write_generated(
                output,
                format_args!("    pub type {} = Vec<serde_json::Value>;\n\n", type_def.id),
            );
        } else if type_def.type_kind == "string" && type_def.enum_values.is_empty() {
            write_generated(
                output,
                format_args!("    pub type {} = String;\n\n", type_def.id),
            );
        } else if type_def.type_kind == "integer" {
            write_generated(
                output,
                format_args!("    pub type {} = i64;\n\n", type_def.id),
            );
        } else if type_def.type_kind == "number" {
            write_generated(
                output,
                format_args!("    pub type {} = f64;\n\n", type_def.id),
            );
        }
    }

    for cmd in &domain.commands {
        let pascal_name = to_pascal_case(&cmd.name);

        if !cmd.parameters.is_empty() {
            output.push_str(
                "    #[derive(Debug, Clone, Serialize, Deserialize)]\n    #[serde(rename_all = \"camelCase\")]\n",
            );
            write_generated(
                output,
                format_args!("    pub struct {pascal_name}Params {{\n"),
            );
            for param in &cmd.parameters {
                let field_name = to_snake_case(&param.name);
                let field_name = if is_rust_keyword(&field_name) {
                    format!("r#{}", field_name)
                } else {
                    field_name
                };
                let rust_type = map_type_in_domain(param, &domain.name, domain_types);
                if param.optional {
                    output
                        .push_str("        #[serde(skip_serializing_if = \"Option::is_none\")]\n");
                }
                write_generated(
                    output,
                    format_args!("        pub {field_name}: {rust_type},\n"),
                );
            }
            output.push_str("    }\n\n");
        }

        if !cmd.returns.is_empty() {
            output.push_str(
                "    #[derive(Debug, Clone, Serialize, Deserialize)]\n    #[serde(rename_all = \"camelCase\")]\n",
            );
            write_generated(
                output,
                format_args!("    pub struct {pascal_name}Result {{\n"),
            );
            for ret in &cmd.returns {
                let field_name = to_snake_case(&ret.name);
                let field_name = if is_rust_keyword(&field_name) {
                    format!("r#{}", field_name)
                } else {
                    field_name
                };
                let rust_type = map_type_in_domain(ret, &domain.name, domain_types);
                if ret.optional {
                    output
                        .push_str("        #[serde(skip_serializing_if = \"Option::is_none\")]\n");
                }
                write_generated(
                    output,
                    format_args!("        pub {field_name}: {rust_type},\n"),
                );
            }
            output.push_str("    }\n\n");
        }
    }

    for event in &domain.events {
        if !event.parameters.is_empty() {
            let pascal_name = to_pascal_case(&event.name);
            output.push_str(
                "    #[derive(Debug, Clone, Serialize, Deserialize)]\n    #[serde(rename_all = \"camelCase\")]\n",
            );
            write_generated(
                output,
                format_args!("    pub struct {pascal_name}Event {{\n"),
            );
            for param in &event.parameters {
                let field_name = to_snake_case(&param.name);
                let field_name = if is_rust_keyword(&field_name) {
                    format!("r#{}", field_name)
                } else {
                    field_name
                };
                let rust_type = map_type_in_domain(param, &domain.name, domain_types);
                if param.optional {
                    output
                        .push_str("        #[serde(skip_serializing_if = \"Option::is_none\")]\n");
                }
                write_generated(
                    output,
                    format_args!("        pub {field_name}: {rust_type},\n"),
                );
            }
            output.push_str("    }\n\n");
        }
    }

    output.push_str("}\n\n");
}
