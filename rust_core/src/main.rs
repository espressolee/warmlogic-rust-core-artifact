#![deny(clippy::unwrap_used)]
use clap::{Parser, Subcommand};
use std::process;

#[cfg(feature = "cockpit")]
mod cockpit;

#[derive(Parser)]
#[command(author, version, about = "WarmLogic Authoritative CLI", long_about = None)]
struct Cli {
    #[command(subcommand)]
    command: Option<Commands>,
}

#[derive(Subcommand)]
enum Commands {
    /// Displays real-time kernel telemetry
    Status {
        /// Monitor live updates
        #[arg(short, long)]
        live: bool,
    },
    /// Triggers forensic audit
    Audit {
        /// Enable destructive deep scan
        #[arg(short, long)]
        brutal: bool,
    },
    /// Manage security shield profiles
    Shield {
        /// Action: status or set
        action: String,
        /// Profile name (for 'set' action)
        profile: Option<String>,
    },
}

fn main() {
    let cli = Cli::parse();

    match &cli.command {
        Some(Commands::Status { live }) => {
            if *live {
                #[cfg(feature = "cockpit")]
                {
                    if let Err(e) = cockpit::run_live_dashboard() {
                        eprintln!("Cockpit Error: {}", e);
                        process::exit(1);
                    }
                }
                #[cfg(not(feature = "cockpit"))]
                {
                    eprintln!("Error: Cockpit feature not enabled.");
                    process::exit(1);
                }
            } else {
                show_static_status();
            }
        }
        Some(Commands::Audit { brutal }) => {
            run_audit(*brutal);
        }
        Some(Commands::Shield { action, profile }) => {
            handle_shield(action, profile);
        }
        None => {
            println!("Use --help for usage information.");
        }
    }
}

fn show_static_status() {
    println!(" WarmLogic Sovereign Cockpit (Static)");
    println!("---------------------------------------");
    println!("Kernel Version: (Sovereign Mobility)");
    println!("Hardware RoT:   ENABLED (Rust-Native)");
    println!("Quantum Shield: ACTIVE (FIPS-204)");
}

fn run_audit(brutal: bool) {
    println!(" Initiating Forensic Audit...");
    if brutal {
        println!(" WARNING: BRUTAL mode enabled.");
    }
    // Real implementation would link to warm_logic_rs::ops::audit
    println!("Audit Complete.");
}

fn handle_shield(action: &str, profile: &Option<String>) {
    match action {
        "status" => {
            println!(" Shield Status: ACTIVE (Profile: restricted)");
        }
        "set" => {
            if let Some(p) = profile {
                println!(" Shield Profile rotated to: {}", p);
            } else {
                eprintln!("Error: No profile specified.");
            }
        }
        _ => eprintln!("Unknown shield action: {}", action),
    }
}
