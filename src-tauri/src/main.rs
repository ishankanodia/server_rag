use std::env;
use std::process::{Child, Command, Stdio};
use std::sync::Mutex;
use std::thread;
use std::time::Duration;

use portpicker::pick_unused_port;
use tauri::{AppHandle, Manager, WebviewUrl, WebviewWindowBuilder};

struct ServerProcess(Mutex<Option<Child>>);

fn server_command(app: &AppHandle, port: u16) -> Command {
    let exe_name = if cfg!(target_os = "windows") {
        "_up_/dist/filewhisper-backend.exe"
    } else {
        "_up_/dist/filewhisper-backend"
    };
    let exe_path = app
        .path()
        .resolve(exe_name, tauri::path::BaseDirectory::Resource)
        .expect("backend resource path");
    let mut command = Command::new(exe_path);

    command.env("FILEWHISPER_PORT", port.to_string());
    command.env("RAG_DATA_DIR", app_data_dir());
    command.stdout(Stdio::null());
    command.stderr(Stdio::null());
    command
}

fn app_data_dir() -> String {
    if let Ok(dir) = env::var("FILEWHISPER_DATA_DIR") {
        return dir;
    }
    let base = env::var("HOME")
        .or_else(|_| env::var("USERPROFILE"))
        .unwrap_or_else(|_| ".".to_string());
    format!("{base}/.filewhisper/rag_data")
}

fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .manage(ServerProcess(Mutex::new(None)))
        .setup(|app| {
            let port = if cfg!(debug_assertions) {
                8001
            } else {
                let port = pick_unused_port().unwrap_or(8001);
                let child = server_command(app.handle(), port).spawn()?;
                thread::sleep(Duration::from_secs(2));

                let state = app.state::<ServerProcess>();
                *state.0.lock().expect("server process lock") = Some(child);
                port
            };

            let url = format!("http://127.0.0.1:{port}")
                .parse()
                .expect("valid server URL");
            WebviewWindowBuilder::new(app, "main", WebviewUrl::External(url))
                .title("FileWhisper")
                .inner_size(1100.0, 780.0)
                .min_inner_size(900.0, 640.0)
                .build()?;

            Ok(())
        })
        .on_window_event(|window, event| {
            if let tauri::WindowEvent::CloseRequested { .. } = event {
                let state = window.state::<ServerProcess>();
                let child = state.0.lock().expect("server process lock").take();
                if let Some(mut child) = child {
                    let _ = child.kill();
                }
            }
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
