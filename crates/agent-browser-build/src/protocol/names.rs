pub(super) fn to_pascal_case(s: &str) -> String {
    let mut result = String::new();
    let mut capitalize = true;
    for c in s.chars() {
        if c == '_' || c == '-' || c == '.' {
            capitalize = true;
        } else if capitalize {
            result.push(c.to_ascii_uppercase());
            capitalize = false;
        } else {
            result.push(c);
        }
    }
    result
}

pub(super) fn to_snake_case(s: &str) -> String {
    let mut result = String::new();
    let chars: Vec<char> = s.chars().collect();
    for (i, &c) in chars.iter().enumerate() {
        if c.is_uppercase() && i > 0 {
            // Only insert underscore at transitions from lowercase to uppercase,
            // or when an uppercase sequence ends (e.g. "DOM" -> "dom", not "d_o_m")
            let prev_upper = chars[i - 1].is_uppercase();
            let next_lower = chars.get(i + 1).is_some_and(|n| n.is_lowercase());
            if !prev_upper || next_lower {
                result.push('_');
            }
        }
        result.push(c.to_ascii_lowercase());
    }
    result
}

/// Resolve a $ref type reference. Cross-domain refs like "Page.FrameId" become
/// `super::cdp_page::FrameId`. Same-domain refs are used directly.
pub(super) fn is_rust_keyword(s: &str) -> bool {
    matches!(
        s,
        "type"
            | "self"
            | "Self"
            | "super"
            | "move"
            | "ref"
            | "fn"
            | "mod"
            | "use"
            | "pub"
            | "let"
            | "mut"
            | "const"
            | "static"
            | "if"
            | "else"
            | "for"
            | "while"
            | "loop"
            | "match"
            | "return"
            | "break"
            | "continue"
            | "as"
            | "in"
            | "impl"
            | "trait"
            | "struct"
            | "enum"
            | "where"
            | "async"
            | "await"
            | "dyn"
            | "box"
            | "yield"
            | "override"
            | "crate"
            | "extern"
    )
}
