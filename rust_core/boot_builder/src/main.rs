use std::path::Path;

fn main() -> anyhow::Result<()> {
    let kernel_path = Path::new("../kernel/target/x86_64-unknown-none/debug/warm_logic_kernel");
    let out_dir = Path::new("../kernel/target/x86_64-unknown-none/debug/");
    let dest_path = out_dir.join("warm_logic_os.bin");

    println!("💿 Creating bootable BIOS image from {:?}", kernel_path);

    let mut bootloader = bootloader::BiosBoot::new(kernel_path);
    bootloader.create_disk_image(&dest_path)?;

    println!("✅ Bootable image created: {:?}", dest_path);
    Ok(())
}
