//! Local desktop JSON persistence shared by workspace windows.

use crate::security::random_token_hex;
use serde::{de::DeserializeOwned, Serialize};
use std::fs::{self, File};
use std::io::Write;
use std::path::{Path, PathBuf};
use std::sync::{Mutex, MutexGuard};

pub(crate) struct StateFile {
    name: &'static str,
    label: &'static str,
    mutation: Mutex<()>,
}

impl StateFile {
    pub(crate) const fn new(name: &'static str, label: &'static str) -> Self {
        Self {
            name,
            label,
            mutation: Mutex::new(()),
        }
    }

    pub(crate) fn read<T: Default + DeserializeOwned>(&self) -> T {
        self.path()
            .map(|path| Self::read_at(&path))
            .unwrap_or_default()
    }

    pub(crate) fn update<T: Default + DeserializeOwned + Serialize>(
        &self,
        apply: impl FnOnce(T) -> Result<T, String>,
    ) -> Result<T, String> {
        self.update_at(&self.path()?, apply)
    }

    pub(crate) fn write<T: Serialize>(&self, value: &T) -> Result<(), String> {
        let path = self.path()?;
        let _mutation = self.lock()?;
        self.write_at(&path, value)
    }

    fn path(&self) -> Result<PathBuf, String> {
        let base = dirs::data_local_dir()
            .or_else(dirs::config_dir)
            .ok_or_else(|| "Unable to resolve local application state directory".to_string())?;
        let dir = base.join("lixity").join("desktop");
        fs::create_dir_all(&dir).map_err(|e| format!("Failed creating desktop state dir: {e}"))?;
        Ok(dir.join(self.name))
    }

    fn lock(&self) -> Result<MutexGuard<'_, ()>, String> {
        self.mutation
            .lock()
            .map_err(|_| format!("Another {} update failed", self.label))
    }

    fn read_at<T: Default + DeserializeOwned>(path: &Path) -> T {
        fs::read(path)
            .ok()
            .and_then(|raw| serde_json::from_slice(&raw).ok())
            .unwrap_or_default()
    }

    fn update_at<T: Default + DeserializeOwned + Serialize>(
        &self,
        path: &Path,
        apply: impl FnOnce(T) -> Result<T, String>,
    ) -> Result<T, String> {
        let _mutation = self.lock()?;
        let next = apply(Self::read_at(path))?;
        self.write_at(path, &next)?;
        Ok(next)
    }

    fn write_at<T: Serialize>(&self, path: &Path, value: &T) -> Result<(), String> {
        let json = serde_json::to_vec_pretty(value).map_err(|e| e.to_string())?;
        let stage = path.with_file_name(format!(
            ".lixity-state-{}.part",
            random_token_hex().as_str()
        ));
        let mut file = File::options()
            .write(true)
            .create_new(true)
            .open(&stage)
            .map_err(|e| format!("Failed staging {}: {e}", self.label))?;
        let written = file.write_all(&json).and_then(|_| file.sync_all());
        drop(file);
        let result = written
            .map_err(|e| format!("Failed writing {}: {e}", self.label))
            .and_then(|()| {
                fs::rename(&stage, path)
                    .map_err(|e| format!("Failed replacing {}: {e}", self.label))
            });
        if result.is_err() {
            let _ = fs::remove_file(&stage);
        }
        result
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::Barrier;
    use std::thread;

    struct Fixture(PathBuf);

    impl Fixture {
        fn new() -> Self {
            let path = std::env::temp_dir().join(format!(
                "lixity-desktop-state-test-{}",
                random_token_hex().as_str()
            ));
            fs::create_dir(&path).unwrap();
            Self(path)
        }
    }

    impl Drop for Fixture {
        fn drop(&mut self) {
            let _ = fs::remove_dir_all(&self.0);
        }
    }

    #[test]
    fn parallel_updates_keep_every_change() {
        let fixture = Fixture::new();
        let state = StateFile::new("state.json", "synthetic state");
        let path = fixture.0.join(state.name);
        let participants: usize = 8;
        let ready = Barrier::new(participants);

        thread::scope(|scope| {
            for entry in 0..participants {
                let (state, path, ready) = (&state, &path, &ready);
                scope.spawn(move || {
                    ready.wait();
                    state
                        .update_at(path, |mut entries: Vec<usize>| {
                            entries.push(entry);
                            Ok(entries)
                        })
                        .unwrap();
                });
            }
        });

        let mut entries: Vec<usize> = StateFile::read_at(&path);
        entries.sort_unstable();
        assert_eq!(entries, (0..participants).collect::<Vec<_>>());
        assert_eq!(fs::read_dir(&fixture.0).unwrap().count(), 1);
    }

    #[test]
    fn interrupted_staging_preserves_last_committed_state() {
        let fixture = Fixture::new();
        let state = StateFile::new("state.json", "synthetic state");
        let path = fixture.0.join(state.name);
        let stale = fixture.0.join(".lixity-state-interrupted.part");
        state.write_at(&path, &1_u32).unwrap();
        fs::write(&stale, b"{").unwrap();

        let value = state.update_at(&path, |value: u32| Ok(value + 1)).unwrap();

        assert_eq!(value, 2);
        assert_eq!(StateFile::read_at::<u32>(&path), 2);
        assert_eq!(fs::read(&stale).unwrap(), b"{");
    }

    #[test]
    fn failed_replacement_leaves_destination_and_removes_staging_file() {
        let fixture = Fixture::new();
        let state = StateFile::new("state.json", "synthetic state");
        let path = fixture.0.join(state.name);
        fs::create_dir(&path).unwrap();
        let original = path.join("retained");
        fs::write(&original, b"keep").unwrap();

        assert!(state.write_at(&path, &1_u32).is_err());
        assert_eq!(fs::read(original).unwrap(), b"keep");
        assert_eq!(fs::read_dir(&fixture.0).unwrap().count(), 1);
    }
}
