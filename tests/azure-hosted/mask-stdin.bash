# Documentation helper exercised by the hosted fixture, not a shipped command.
# Call only with tracing disabled; stdin is a caller-acquired byte stream.
register_shoutx_mask() {
    local shoutx_binary=$1
    shift
    "$shoutx_binary" azure-pipelines:mask "$@"
}
