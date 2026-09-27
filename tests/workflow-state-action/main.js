const { appendFileSync } = require("node:fs");
const { spawnSync } = require("node:child_process");

const suffix = process.platform === "win32" ? ".exe" : "";
const binary = `${process.env.INPUT_BINARY}${suffix}`;
const value = "first\nInjected=bad\n";
const result = spawnSync(
  binary,
  ["github-actions:state", "--multiline", "Result", value],
  { encoding: null },
);
if (result.status !== 0 || result.stderr.length !== 0) {
  throw new Error("shoutx state writer failed");
}
appendFileSync(process.env.GITHUB_STATE, result.stdout);
