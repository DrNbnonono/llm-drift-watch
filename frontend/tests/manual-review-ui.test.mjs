import assert from "node:assert/strict";
import fs from "node:fs";
import test from "node:test";

const source = fs.readFileSync(new URL("../src/RunItemsPage.jsx", import.meta.url), "utf8");

test("per-item detail exposes manual review form and audit history", () => {
  assert.match(source, /人工复核/);
  assert.match(source, /manual-review/);
  assert.match(source, /复核历史/);
  assert.match(source, /required/);
});
