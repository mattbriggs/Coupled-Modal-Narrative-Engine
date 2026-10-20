use serde_json::{json, Value};
use std::io::{BufRead, BufReader, Write};
use std::path::PathBuf;
use std::process::{Child, ChildStdin, ChildStdout, Command, Stdio};
use std::sync::Mutex;
use tauri::Manager;

struct Sidecar {
    child: Child,
    input: ChildStdin,
    output: BufReader<ChildStdout>,
    next_id: u64,
}

impl Sidecar {
    fn start() -> Result<Self, String> {
        let project_root = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../..");
        let (program, args): (PathBuf, Vec<String>) = if let Ok(path) =
            std::env::var("CMNE_SIDECAR_BIN")
        {
            (PathBuf::from(path), vec![])
        } else if cfg!(debug_assertions) {
            (
                PathBuf::from("python3"),
                vec!["-m".into(), "cmne_sidecar.server".into()],
            )
        } else {
            let executable = std::env::current_exe().map_err(|e| e.to_string())?;
            let sibling = executable.with_file_name(if cfg!(windows) {
                "cmne-sidecar.exe"
            } else {
                "cmne-sidecar"
            });
            if sibling.exists() {
                (sibling, vec![])
            } else {
                return Err(
                    "Bundled Python sidecar is missing. Set CMNE_SIDECAR_BIN to its path.".into(),
                );
            }
        };
        let mut command = Command::new(program);
        command
            .args(args)
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::inherit());
        if cfg!(debug_assertions) && std::env::var("CMNE_SIDECAR_BIN").is_err() {
            command.env("PYTHONPATH", project_root.join("src"));
        }
        let mut child = command
            .spawn()
            .map_err(|e| format!("Cannot start Python sidecar: {e}"))?;
        let input = child.stdin.take().ok_or("Sidecar stdin unavailable")?;
        let output = BufReader::new(child.stdout.take().ok_or("Sidecar stdout unavailable")?);
        let mut sidecar = Self {
            child,
            input,
            output,
            next_id: 1,
        };
        let hello = sidecar.call("app.hello", json!({"protocol_version": "1.0"}))?;
        if hello["protocol_version"]
            .as_str()
            .unwrap_or("")
            .split('.')
            .next()
            != Some("1")
        {
            return Err("E-PROTO-001: incompatible sidecar protocol".into());
        }
        Ok(sidecar)
    }

    fn call(&mut self, method: &str, params: Value) -> Result<Value, String> {
        let id = self.next_id;
        self.next_id += 1;
        let request = json!({"jsonrpc": "2.0", "id": id, "method": method, "params": params});
        writeln!(self.input, "{request}")
            .and_then(|_| self.input.flush())
            .map_err(|e| format!("Sidecar write failed: {e}"))?;
        let mut line = String::new();
        let size = self
            .output
            .read_line(&mut line)
            .map_err(|e| format!("Sidecar read failed: {e}"))?;
        if size == 0 {
            return Err("Python sidecar exited unexpectedly".into());
        }
        let response: Value =
            serde_json::from_str(&line).map_err(|e| format!("Invalid sidecar response: {e}"))?;
        if response["id"] != id {
            return Err("E-PROTO-001: mismatched response ID".into());
        }
        if let Some(error) = response.get("error") {
            return Err(serde_json::to_string(error).unwrap_or_else(|_| error.to_string()));
        }
        Ok(response.get("result").cloned().unwrap_or(Value::Null))
    }
}

impl Drop for Sidecar {
    fn drop(&mut self) {
        let _ = self.child.kill();
        let _ = self.child.wait();
    }
}

struct AppState(Mutex<Option<Sidecar>>);

const METHODS: &[&str] = &[
    "app.hello",
    "project.create",
    "project.sample",
    "project.open",
    "project.close",
    "project.get",
    "fixture.validate",
    "fixture.get",
    "fixture.save",
    "contract.validate",
    "contract.get",
    "contract.save",
    "branch.list",
    "branch.fork",
    "branch.compare",
    "events.read",
    "command.submit",
    "graph.get",
    "graph.validate_connection",
    "draft.create",
    "draft.get",
    "draft.patch",
    "draft.compile_preview",
    "draft.seal",
    "draft.delete",
    "scrub.projection",
    "overlay.series",
    "strain.series",
    "trace.query",
    "packet.build",
    "packet.get",
    "run.start",
    "run.status",
    "run.cancel",
    "export.report",
];

#[tauri::command]
fn rpc_call(state: tauri::State<AppState>, method: String, params: Value) -> Result<Value, String> {
    if !METHODS.contains(&method.as_str()) {
        return Err("E-RPC-001: method is not allowed".into());
    }
    let mut guard = state.0.lock().map_err(|_| "Sidecar state is unavailable")?;
    if guard.is_none() {
        *guard = Some(Sidecar::start()?);
    }
    match guard.as_mut().unwrap().call(&method, params.clone()) {
        Ok(result) => Ok(result),
        Err(error) if error.contains("exited unexpectedly") || error.contains("Broken pipe") => {
            *guard = Some(Sidecar::start()?);
            guard.as_mut().unwrap().call(&method, params)
        }
        Err(error) => Err(error),
    }
}

#[tauri::command]
fn default_sample_path(app: tauri::AppHandle) -> Result<String, String> {
    Ok(app
        .path()
        .document_dir()
        .map_err(|e| e.to_string())?
        .join("CMNE")
        .join("Mara and Len")
        .to_string_lossy()
        .to_string())
}

pub fn run() {
    tauri::Builder::default()
        .manage(AppState(Mutex::new(None)))
        .invoke_handler(tauri::generate_handler![rpc_call, default_sample_path])
        .run(tauri::generate_context!())
        .expect("error while running CMNE Workbench");
}
