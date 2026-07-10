import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

test("selected bank filter pills use black text", async () => {
  const css = await readFile(new URL("../src/styles.css", import.meta.url), "utf8");
  const activeRule = css.match(/\.bank-pill\.is-active\s*\{([^}]*)\}/s);

  assert.ok(activeRule, "expected the selected bank pill CSS rule");
  assert.match(activeRule[1], /color:\s*#000\s*;/);
});
