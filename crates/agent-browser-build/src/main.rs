use std::{env, path::PathBuf, process::ExitCode};

fn main() -> ExitCode {
    let args: Vec<_> = env::args_os().skip(1).collect();
    if args.len() != 2 {
        eprintln!("Usage: agent-browser-build <source-root> <output-dir>");
        return ExitCode::from(2);
    }
    let source = PathBuf::from(&args[0]);
    let output = PathBuf::from(&args[1]);
    std::panic::set_hook(Box::new(|_| {}));
    match agent_browser_build::generate(&source, &output) {
        Ok(report) => {
            println!("{}", serde_json::json!({"success": true, "report": report}));
            ExitCode::SUCCESS
        }
        Err(error) => {
            println!(
                "{}",
                serde_json::json!({"success": false, "error": error.message, "report": error.report})
            );
            ExitCode::FAILURE
        }
    }
}
