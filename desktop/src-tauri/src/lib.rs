mod jobs;

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .manage(jobs::WorkerManager::default())
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_shell::init())
        .invoke_handler(tauri::generate_handler![
            jobs::start_job,
            jobs::send_control,
            jobs::worker_utility
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
