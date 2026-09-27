const expected = "first\nInjected=bad\n";
if (process.env.STATE_Result !== expected) {
  throw new Error("state value did not round trip");
}
if (process.env.STATE_Injected !== undefined) {
  throw new Error("state value injected a second key");
}
