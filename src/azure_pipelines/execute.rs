use super::{request::Request, *};
use crate::{ShoutxError, input::read_value, provider::Context};
impl Request {
    pub(crate) fn encode(self, context: &mut impl Context) -> Result<Vec<u8>, ShoutxError> {
        const MISSING: &str = "VALUE omitted while stdin is a terminal";
        match self {
            Self::File { kind, value } => {
                encode_file(kind, &read_value(value.as_ref(), context, MISSING)?)
            }
            Self::Log { kind, value } => {
                encode_log(kind, &read_value(value.as_ref(), context, MISSING)?)
            }
            Self::EndGroup => Ok(b"##[endgroup]\n".to_vec()),
            Self::BuildMetadata { kind, value } => {
                encode_build_metadata(kind, &read_value(value.as_ref(), context, MISSING)?)
            }
            Self::Mask { each_line } => {
                encode_mask(&read_value(None, context, MISSING)?, each_line)
            }
            Self::Path { value } => encode_path(&read_value(value.as_ref(), context, MISSING)?),
            Self::Variable(request) => {
                validate_variable(&request)?;
                let value = read_value(request.value.as_ref(), context, MISSING)?;
                encode_variable(&request, &value)
            }
            Self::SecretVariable(request) => {
                validate_variable(&request)?;
                let value = read_value(None, context, MISSING)?;
                encode_secret_variable(&request, &value)
            }
            Self::Issue(request) => {
                let value = read_value(request.message.as_ref(), context, MISSING)?;
                encode_issue(&request, &value)
            }
        }
    }
}
