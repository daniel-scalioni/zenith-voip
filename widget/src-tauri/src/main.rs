#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use tauri::{
    api::notification::Notification,
    Manager,
};
use std::sync::Mutex;

struct CallState {
    active: bool,
    call_id: Option<String>,
}

#[tauri::command]
fn show_on_call(state: tauri::State<Mutex<CallState>>, window: tauri::Window) {
    let mut call_state = state.lock().unwrap();
    call_state.active = true;
    window.show().unwrap();
    window.set_focus().unwrap();
}

#[tauri::command]
fn hide_on_call_end(state: tauri::State<Mutex<CallState>>, window: tauri::Window) {
    let mut call_state = state.lock().unwrap();
    call_state.active = false;
    call_state.call_id = None;
    window.hide().unwrap();
}

#[tauri::command]
fn set_call_id(state: tauri::State<Mutex<CallState>>, call_id: String) {
    let mut call_state = state.lock().unwrap();
    call_state.call_id = Some(call_id);
}

fn main() {
    tauri::Builder::default()
        .manage(Mutex::new(CallState {
            active: false,
            call_id: None,
        }))
        .on_window_event(|event| {
            if let tauri::WindowEvent::CloseRequested { .. } = event.event() {
                event.window().hide().unwrap();
            }
        })
        .system_tray(tauri::SystemTray::new().with_menu(
            tauri::SystemTrayMenu::new()
                .add_item(tauri::CustomMenuItem::new("show", "Mostrar"))
                .add_item(tauri::CustomMenuItem::new("quit", "Sair")),
        ))
        .on_system_tray_event(|app, event| match event {
            tauri::SystemTrayEvent::MenuItemClick { id, .. } => {
                match id.as_str() {
                    "show" => {
                        if let Some(window) = app.get_window("main") {
                            window.show().unwrap();
                            window.set_focus().unwrap();
                        }
                    }
                    "quit" => {
                        std::process::exit(0);
                    }
                    _ => {}
                }
            }
            _ => {}
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
