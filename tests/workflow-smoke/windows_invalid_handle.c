#define UNICODE
#define _UNICODE
#include <windows.h>

#include <stdio.h>
#include <string.h>
#include <wchar.h>

static int run_child(const wchar_t *binary, const wchar_t *arguments,
                     BOOL invalid_stdin, BOOL invalid_stdout,
                     DWORD expected_exit, const char *expected_stdout) {
    SECURITY_ATTRIBUTES security = {sizeof(SECURITY_ATTRIBUTES), NULL, TRUE};
    HANDLE read_pipe = NULL;
    HANDLE write_pipe = NULL;
    HANDLE null_handle = CreateFileW(L"NUL", GENERIC_READ | GENERIC_WRITE,
                                     FILE_SHARE_READ | FILE_SHARE_WRITE,
                                     &security, OPEN_EXISTING, 0, NULL);
    if (null_handle == INVALID_HANDLE_VALUE) {
        return 10;
    }
    if (!invalid_stdout) {
        if (!CreatePipe(&read_pipe, &write_pipe, &security, 0) ||
            !SetHandleInformation(read_pipe, HANDLE_FLAG_INHERIT, 0)) {
            CloseHandle(null_handle);
            return 11;
        }
    }

    wchar_t command[32768];
    if (swprintf_s(command, _countof(command), L"\"%ls\" %ls", binary,
                   arguments) < 0) {
        return 12;
    }
    STARTUPINFOW startup = {0};
    startup.cb = sizeof(startup);
    startup.dwFlags = STARTF_USESTDHANDLES;
    startup.hStdInput = invalid_stdin ? INVALID_HANDLE_VALUE : null_handle;
    startup.hStdOutput = invalid_stdout ? INVALID_HANDLE_VALUE : write_pipe;
    startup.hStdError = null_handle;
    PROCESS_INFORMATION process = {0};
    BOOL created = CreateProcessW(binary, command, NULL, NULL, TRUE,
                                  CREATE_UNICODE_ENVIRONMENT, NULL, NULL,
                                  &startup, &process);
    if (write_pipe != NULL) {
        CloseHandle(write_pipe);
        write_pipe = NULL;
    }
    if (!created) {
        if (read_pipe != NULL) CloseHandle(read_pipe);
        CloseHandle(null_handle);
        return 13;
    }
    WaitForSingleObject(process.hProcess, INFINITE);
    DWORD exit_code = 0;
    GetExitCodeProcess(process.hProcess, &exit_code);
    CloseHandle(process.hThread);
    CloseHandle(process.hProcess);
    CloseHandle(null_handle);

    char output[256] = {0};
    DWORD total = 0;
    if (read_pipe != NULL) {
        DWORD count = 0;
        while (total < sizeof(output) &&
               ReadFile(read_pipe, output + total,
                        (DWORD)(sizeof(output) - total), &count, NULL) &&
               count != 0) {
            total += count;
        }
        CloseHandle(read_pipe);
    }
    size_t expected_length = strlen(expected_stdout);
    if (exit_code != expected_exit || total != expected_length ||
        memcmp(output, expected_stdout, expected_length) != 0) {
        return 20;
    }
    return 0;
}

int wmain(int argc, wchar_t **argv) {
    if (argc != 2) {
        fwprintf(stderr, L"usage: windows_invalid_handle.exe SHOUTX\n");
        return 2;
    }
    int status = run_child(argv[1], L"github-actions:output result", TRUE,
                           FALSE, 1, "");
    if (status != 0) return status;
    status = run_child(argv[1], L"github-actions:output result value", TRUE,
                       FALSE, 0, "result=value\n");
    if (status != 0) return status;
    status = run_child(argv[1], L"github-actions:output result value", FALSE,
                       TRUE, 1, "");
    if (status != 0) return status;
    status = run_child(argv[1], L"github-actions:debug", TRUE, FALSE, 1, "");
    if (status != 0) return status;
    status = run_child(argv[1], L"azure-pipelines:secret-variable Credential", TRUE, FALSE, 1, "");
    if (status != 0) return status;
    status = run_child(argv[1], L"azure-pipelines:secret-variable Credential forbidden-argv", TRUE, FALSE, 2, "");
    if (status != 0) return status;
    status = run_child(argv[1], L"github-actions:group", TRUE, FALSE, 1, "");
    if (status != 0) return status;
    status = run_child(argv[1], L"github-actions:debug value", TRUE, FALSE, 0, "::debug::value\n");
    if (status != 0) return status;
    status = run_child(argv[1], L"github-actions:group value", TRUE, FALSE, 0, "::group::value\n");
    if (status != 0) return status;
    status = run_child(argv[1], L"github-actions:endgroup", TRUE, FALSE, 0, "::endgroup::\n");
    if (status != 0) return status;
    const wchar_t *azure_commands[] = {L"azure-pipelines:debug", L"azure-pipelines:group"};
    const wchar_t *azure_values[] = {L"azure-pipelines:debug value", L"azure-pipelines:group value", L"azure-pipelines:endgroup"};
    const char *azure_outputs[] = {"##vso[task.debug]value\n", "##[group]value\n", "##[endgroup]\n"};
    for (int i = 0; i < 2; i++) {
        status = run_child(argv[1], azure_commands[i], TRUE, FALSE, 1, "");
        if (status != 0) return status;
    }
    for (int i = 0; i < 3; i++) {
        status = run_child(argv[1], azure_values[i], TRUE, FALSE, 0, azure_outputs[i]);
        if (status != 0) return status;
        status = run_child(argv[1], azure_values[i], FALSE, TRUE, 1, "");
        if (status != 0) return status;
    }
    const wchar_t *matcher_commands[] = {L"github-actions:add-matcher", L"github-actions:remove-matcher file", L"github-actions:remove-matcher owner"};
    const wchar_t *matcher_values[] = {L"github-actions:add-matcher value", L"github-actions:remove-matcher file value", L"github-actions:remove-matcher owner value"};
    const char *matcher_outputs[] = {"::add-matcher::value\n", "::remove-matcher::value\n", "::remove-matcher owner=value,::\n"};
    for (int i = 0; i < 3; i++) {
        status = run_child(argv[1], matcher_commands[i], TRUE, FALSE, 1, "");
        if (status != 0) return status;
        status = run_child(argv[1], matcher_values[i], TRUE, FALSE, 0, matcher_outputs[i]);
        if (status != 0) return status;
        status = run_child(argv[1], matcher_values[i], FALSE, TRUE, 1, "");
        if (status != 0) return status;
    }
    return 0;
}
