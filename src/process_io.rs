use std::{fs::File, io};

#[cfg(unix)]
pub fn stdin_file() -> io::Result<File> {
    use std::os::fd::AsFd;
    let stdin = io::stdin();
    stdin.as_fd().try_clone_to_owned().map(File::from)
}

#[cfg(unix)]
pub fn stdout_file() -> io::Result<File> {
    use std::os::fd::AsFd;
    let stdout = io::stdout();
    stdout.as_fd().try_clone_to_owned().map(File::from)
}

#[cfg(windows)]
pub fn stdin_file() -> io::Result<File> {
    use std::os::windows::io::AsHandle;
    let stdin = io::stdin();
    stdin.as_handle().try_clone_to_owned().map(File::from)
}

#[cfg(windows)]
pub fn stdout_file() -> io::Result<File> {
    use std::os::windows::io::AsHandle;
    let stdout = io::stdout();
    stdout.as_handle().try_clone_to_owned().map(File::from)
}
