use crate::error::ShoutxError;

pub trait RandomSource {
    fn fill(&mut self, destination: &mut [u8]) -> Result<(), ShoutxError>;
}

pub struct OsRandom;

impl RandomSource for OsRandom {
    fn fill(&mut self, destination: &mut [u8]) -> Result<(), ShoutxError> {
        getrandom::fill(destination)
            .map_err(|_| ShoutxError::failure("failed to generate multiline delimiter"))
    }
}
