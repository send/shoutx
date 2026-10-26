# Documentation helper. Stdin is the caller-acquired byte stream; tracing off.
# Pass only public flags and NAME as arguments, never the credential.
set_shoutx_secret_variable() {
    local shoutx_binary=$1
    shift
    "$shoutx_binary" azure-pipelines:secret-variable "$@"
}
