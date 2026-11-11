use std::{
    collections::HashMap,
    path::Path,
    sync::{Arc, Mutex},
};

use serde::{Deserialize, Serialize};
use serde_json::Value;
use tauri::{AppHandle, Emitter, State};
use tauri_plugin_shell::{
    ShellExt,
    process::{CommandChild, CommandEvent},
};

const PROTOCOL_VERSION: u8 = 1;
const WORKER_EVENTS: &[&str] = &[
    "accepted",
    "preview",
    "progress",
    "confirmation_required",
    "file_result",
    "warning",
    "error",
    "completed",
];

#[derive(Clone, Default)]
pub struct WorkerManager {
    children: Arc<Mutex<HashMap<String, CommandChild>>>,
}

#[derive(Clone, Deserialize, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum RequestType {
    Preview,
    Start,
}

#[derive(Clone, Deserialize, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum Operation {
    Rename,
    Lyrics,
    Covers,
    Recognize,
    Albums,
    Revert,
}

#[derive(Clone, Deserialize, Serialize)]
pub struct OperationRequest {
    pub operation: Operation,
    pub directory: String,
    pub recursive: bool,
    pub options: Value,
}

#[derive(Clone, Deserialize, Serialize)]
pub struct JobRequest {
    pub v: u8,
    #[serde(rename = "type")]
    pub request_type: RequestType,
    pub job_id: String,
    pub session_id: String,
    pub request: OperationRequest,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub preview_token: Option<String>,
}

#[derive(Clone, Deserialize, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum ControlType {
    Pause,
    Resume,
    Cancel,
    ConfirmationResponse,
}

#[derive(Clone, Deserialize, Serialize)]
pub struct JobControl {
    pub v: u8,
    #[serde(rename = "type")]
    pub control_type: ControlType,
    pub job_id: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub confirmation_id: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub value: Option<bool>,
}

#[derive(Clone, Deserialize, Serialize)]
pub struct UtilityRequest {
    pub v: u8,
    #[serde(rename = "type")]
    pub request_type: String,
    pub action: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub key: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub value: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub session_id: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub filters: Option<Value>,
}

#[tauri::command]
pub async fn worker_utility(app: AppHandle, request: UtilityRequest) -> Result<Value, String> {
    if request.v != PROTOCOL_VERSION || request.request_type != "utility" {
        return Err("Invalid local utility request.".to_owned());
    }
    if ![
        "history_list",
        "history_detail",
        "history_clear",
        "history_location",
        "credential_status",
        "credential_save",
        "credential_delete",
    ]
    .contains(&request.action.as_str())
    {
        return Err("Unsupported local utility request.".to_owned());
    }
    if request.action.starts_with("credential_") {
        if request.key.as_deref().unwrap_or("acoustid") != "acoustid" {
            return Err("Unsupported credential name.".to_owned());
        }
        if request.action == "credential_save"
            && request
                .value
                .as_ref()
                .is_none_or(|value| value.is_empty() || value.len() > 16384)
        {
            return Err("Enter a valid credential value.".to_owned());
        }
    }

    let command = app
        .shell()
        .sidecar("musren-worker")
        .map_err(|_| "The packaged Python worker is unavailable.".to_owned())?
        .kill_on_drop(true)
        .set_process_group(true);
    let (mut events, mut child) = command
        .spawn()
        .map_err(|_| "Could not start the local utility worker.".to_owned())?;
    let mut line = serde_json::to_vec(&request)
        .map_err(|_| "Could not encode the local utility request.".to_owned())?;
    line.push(b'\n');
    if child.write(&line).is_err() {
        let _ = child.kill();
        return Err("Could not send the local utility request.".to_owned());
    }

    while let Some(event) = events.recv().await {
        match event {
            CommandEvent::Stdout(bytes) => {
                let response: Value = serde_json::from_slice(&bytes)
                    .map_err(|_| "The local utility returned an invalid response.".to_owned())?;
                return response
                    .get("utility_result")
                    .cloned()
                    .ok_or_else(|| "The local utility returned no result.".to_owned());
            }
            CommandEvent::Terminated(_) => break,
            _ => {}
        }
    }
    Err("The local utility exited without returning a result.".to_owned())
}

#[tauri::command]
pub fn start_job(
    app: AppHandle,
    manager: State<'_, WorkerManager>,
    request: JobRequest,
) -> Result<(), String> {
    validate_request(&request)?;
    let job_id = request.job_id.clone();
    let mut children = manager
        .children
        .lock()
        .map_err(|_| "Worker manager is unavailable.".to_owned())?;
    if children.contains_key(&job_id) {
        return Err("A job with this ID is already active.".to_owned());
    }

    let command = app
        .shell()
        .sidecar("musren-worker")
        .map_err(|_| "The packaged Python worker is unavailable.".to_owned())?
        .kill_on_drop(true)
        .set_process_group(true);
    let (mut events, mut child) = command
        .spawn()
        .map_err(|_| "Could not start the Python worker.".to_owned())?;
    let mut request_line =
        serde_json::to_vec(&request).map_err(|_| "Could not encode the job request.".to_owned())?;
    request_line.push(b'\n');
    if child.write(&request_line).is_err() {
        let _ = child.kill();
        return Err("Could not send the job request to the worker.".to_owned());
    }

    children.insert(job_id.clone(), child);
    drop(children);

    let children = Arc::clone(&manager.children);
    tauri::async_runtime::spawn(async move {
        while let Some(event) = events.recv().await {
            match event {
                CommandEvent::Stdout(bytes) => match serde_json::from_slice::<Value>(&bytes) {
                    Ok(value) if valid_worker_event(&value, &job_id) => {
                        let _ = app.emit("job-event", value);
                    }
                    _ => {
                        let _ = app.emit(
                            "job-event",
                            serde_json::json!({
                                "v": PROTOCOL_VERSION,
                                "job_id": job_id,
                                "type": "worker_protocol_error"
                            }),
                        );
                    }
                },
                CommandEvent::Stderr(_) => {}
                CommandEvent::Terminated(_) => break,
                _ => {}
            }
        }

        let _ = app.emit(
            "job-event",
            serde_json::json!({
                "v": PROTOCOL_VERSION,
                "job_id": job_id,
                "type": "process_exit"
            }),
        );
        if let Ok(mut children) = children.lock() {
            children.remove(&job_id);
        }
    });
    Ok(())
}

#[tauri::command]
pub fn send_control(manager: State<'_, WorkerManager>, control: JobControl) -> Result<(), String> {
    if control.v != PROTOCOL_VERSION || control.job_id.is_empty() {
        return Err("Invalid worker control message.".to_owned());
    }
    if matches!(control.control_type, ControlType::ConfirmationResponse)
        && (control
            .confirmation_id
            .as_deref()
            .unwrap_or_default()
            .is_empty()
            || control.value.is_none())
    {
        return Err("Confirmation responses require an ID and value.".to_owned());
    }

    let mut line = serde_json::to_vec(&control)
        .map_err(|_| "Could not encode the worker control.".to_owned())?;
    line.push(b'\n');
    let mut children = manager
        .children
        .lock()
        .map_err(|_| "Worker manager is unavailable.".to_owned())?;
    let child = children
        .get_mut(&control.job_id)
        .ok_or_else(|| "The requested job is not active.".to_owned())?;
    child
        .write(&line)
        .map_err(|_| "Could not send a control to the worker.".to_owned())
}

fn validate_request(request: &JobRequest) -> Result<(), String> {
    if request.v != PROTOCOL_VERSION || request.job_id.trim().is_empty() {
        return Err("Invalid worker protocol version or job ID.".to_owned());
    }
    if request.job_id.len() > 128 {
        return Err("Job IDs cannot exceed 128 characters.".to_owned());
    }
    if !valid_session_id(&request.session_id) {
        return Err("Invalid history session ID.".to_owned());
    }
    if !Path::new(&request.request.directory).is_dir() {
        return Err("Choose an existing directory.".to_owned());
    }
    if !request.request.options.is_object() {
        return Err("Invalid operation options.".to_owned());
    }
    match &request.request_type {
        RequestType::Preview if request.preview_token.is_some() => {
            return Err("Preview requests cannot include a preview token.".to_owned());
        }
        RequestType::Start => {
            let Some(token) = request.preview_token.as_deref() else {
                return Err("A fresh preview is required before renaming.".to_owned());
            };
            if token.len() != 64 || !token.bytes().all(|character| character.is_ascii_hexdigit()) {
                return Err("The preview token is invalid. Run a new preview.".to_owned());
            }
        }
        RequestType::Preview => {}
    }
    Ok(())
}

fn valid_session_id(value: &str) -> bool {
    if value.len() != 36 {
        return false;
    }
    value.bytes().enumerate().all(|(index, character)| {
        if [8, 13, 18, 23].contains(&index) {
            character == b'-'
        } else {
            character.is_ascii_hexdigit()
        }
    })
}

fn valid_worker_event(event: &Value, job_id: &str) -> bool {
    event.get("v").and_then(Value::as_u64) == Some(u64::from(PROTOCOL_VERSION))
        && event.get("job_id").and_then(Value::as_str) == Some(job_id)
        && event
            .get("type")
            .and_then(Value::as_str)
            .is_some_and(|kind| WORKER_EVENTS.contains(&kind))
}
