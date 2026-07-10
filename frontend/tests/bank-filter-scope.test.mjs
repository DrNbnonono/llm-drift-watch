import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const sourceUrl = new URL("../src/BankPage.jsx", import.meta.url);

test("bank facets follow the selected version and module", async () => {
  const source = await readFile(sourceUrl, "utf8");

  assert.match(source, /buildQuery\(\{ version: filters\.version, module: filters\.module \}\)/);
  assert.match(source, /api\/bank\/facets\$\{query\}/);
  assert.match(source, /if \(!filters\.module\) return \[\];/);
});

test("module and subtype options include taxonomy labels", async () => {
  const source = await readFile(sourceUrl, "utf8");

  assert.match(source, /api\/dict\/subtypes\?include_inactive=true/);
  assert.match(source, /moduleLabel/);
  assert.match(source, /subtypeLabel/);
});
