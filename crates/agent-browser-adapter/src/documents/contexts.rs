use std::collections::HashMap;

use serde_json::Value;

use crate::native::cdp::types::CdpEvent;

#[derive(Clone)]
pub(crate) struct DocumentContext {
    pub id: i64,
    pub unique_id: Option<String>,
}

#[derive(Default)]
pub(crate) struct Contexts {
    documents: HashMap<(String, String), DocumentContext>,
}

impl Contexts {
    pub fn document(&self, session: &str, frame: &str) -> Option<DocumentContext> {
        self.documents
            .get(&(session.to_owned(), frame.to_owned()))
            .cloned()
    }

    pub fn apply(&mut self, event: &CdpEvent) {
        let session = event.session_id.as_deref().unwrap_or("");
        match event.method.as_str() {
            "Runtime.executionContextCreated" => {
                let context = &event.params["context"];
                let aux = &context["auxData"];
                if aux["isDefault"].as_bool() != Some(true) {
                    return;
                }
                if let (Some(frame), Some(id)) = (aux["frameId"].as_str(), context["id"].as_i64()) {
                    self.documents.insert(
                        (session.to_owned(), frame.to_owned()),
                        DocumentContext {
                            id,
                            unique_id: context["uniqueId"].as_str().map(str::to_owned),
                        },
                    );
                }
            }
            "Runtime.executionContextDestroyed" => {
                let id = event.params["executionContextId"].as_i64();
                self.documents
                    .retain(|(owner, _), context| owner != session || Some(context.id) != id);
            }
            "Runtime.executionContextsCleared" => {
                self.documents.retain(|(owner, _), _| owner != session);
            }
            "Target.detachedFromTarget" => {
                if let Some(detached) = event.params.get("sessionId").and_then(Value::as_str) {
                    self.documents.retain(|(owner, _), _| owner != detached);
                }
            }
            _ => {}
        }
    }
}
