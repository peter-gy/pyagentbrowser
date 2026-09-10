#[allow(dead_code)]
#[derive(serde::Deserialize)]
pub(super) struct ProtocolSpec {
    pub(super) domains: Vec<Domain>,
}

#[allow(dead_code)]
#[derive(serde::Deserialize, Clone)]
pub(super) struct Domain {
    #[serde(rename = "domain")]
    pub(super) name: String,
    #[serde(default)]
    pub(super) types: Vec<TypeDef>,
    #[serde(default)]
    pub(super) commands: Vec<Command>,
    #[serde(default)]
    pub(super) events: Vec<Event>,
}

#[allow(dead_code)]
#[derive(serde::Deserialize, Clone)]
pub(super) struct TypeDef {
    pub(super) id: String,
    #[serde(rename = "type", default)]
    pub(super) type_kind: String,
    #[serde(default)]
    pub(super) properties: Vec<Property>,
    #[serde(rename = "enum", default)]
    pub(super) enum_values: Vec<String>,
    #[serde(default)]
    pub(super) description: Option<String>,
}

#[allow(dead_code)]
#[derive(serde::Deserialize, Clone)]
pub(super) struct Command {
    pub(super) name: String,
    #[serde(default)]
    pub(super) parameters: Vec<Property>,
    #[serde(default)]
    pub(super) returns: Vec<Property>,
    #[serde(default)]
    pub(super) description: Option<String>,
}

#[allow(dead_code)]
#[derive(serde::Deserialize, Clone)]
pub(super) struct Event {
    pub(super) name: String,
    #[serde(default)]
    pub(super) parameters: Vec<Property>,
    #[serde(default)]
    pub(super) description: Option<String>,
}

#[allow(dead_code)]
#[derive(serde::Deserialize, Clone)]
pub(super) struct Property {
    pub(super) name: String,
    #[serde(rename = "type", default)]
    pub(super) type_kind: Option<String>,
    #[serde(rename = "$ref", default)]
    pub(super) ref_type: Option<String>,
    #[serde(default)]
    pub(super) optional: bool,
    #[serde(default)]
    pub(super) description: Option<String>,
    #[serde(default)]
    pub(super) items: Option<Box<ItemType>>,
    #[serde(rename = "enum", default)]
    pub(super) enum_values: Vec<String>,
}

#[allow(dead_code)]
#[derive(serde::Deserialize, Clone)]
pub(super) struct ItemType {
    #[serde(rename = "type", default)]
    pub(super) type_kind: Option<String>,
    #[serde(rename = "$ref", default)]
    pub(super) ref_type: Option<String>,
}
