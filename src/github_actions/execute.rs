use super::{
    request::{ArtifactRequest, Request},
    *,
};
use crate::{
    input::{os_bytes, read_value},
    provider::Context,
};
impl Request {
    pub(crate) fn encode(self, context: &mut impl Context) -> Result<Vec<u8>, ShoutxError> {
        const MISSING: &str = "VALUE omitted while stdin is a terminal";
        match self {
            Self::EndGroup => Ok(b"::endgroup::\n".to_vec()),
            Self::Matcher { kind, value } => {
                encode_matcher(kind, read_value(value.as_ref(), context, MISSING)?)
            }
            Self::Log { kind, value } => {
                encode_log(kind, read_value(value.as_ref(), context, MISSING)?)
            }
            Self::Artifact(ArtifactRequest::File { path }) => encode_artifact_file(read_value(
                path.as_ref(),
                context,
                "PATH omitted while stdin is a terminal",
            )?),
            Self::Artifact(ArtifactRequest::Oci { reference, digest }) => {
                encode_artifact_oci(os_bytes(&reference)?, os_bytes(&digest)?)
            }
            Self::Write(request) => {
                validate_request(&request)?;
                let value = read_value(request.value.as_ref(), context, MISSING)?;
                let target_os = TargetOs::from_runner_os(context.env_var("RUNNER_OS").as_deref());
                encode_with(request, value, target_os, &mut OsRandom)
            }
            Self::WritePath(request) => {
                let target_os = TargetOs::from_runner_os(context.env_var("RUNNER_OS").as_deref());
                if target_os == TargetOs::Unknown {
                    return Err(ShoutxError::failure("unknown target runner OS"));
                }
                encode_path(
                    read_value(request.value.as_ref(), context, MISSING)?,
                    target_os,
                )
            }
            Self::Mask(request) => {
                encode_mask(read_value(request.value.as_ref(), context, MISSING)?)
            }
            Self::Annotate(request) => {
                let value = read_value(
                    request.message.as_ref(),
                    context,
                    "MESSAGE omitted while stdin is a terminal",
                )?;
                encode_annotation(request, value)
            }
        }
    }
}
