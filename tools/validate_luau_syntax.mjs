#!/usr/bin/env node
import fs from "node:fs";
import path from "node:path";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
import { Language, Parser } from "web-tree-sitter";

const require = createRequire(import.meta.url);
let languagePromise;

async function loadLanguage() {
  if (!languagePromise) {
    languagePromise = (async () => {
      await Parser.init();
      const wasm = require.resolve("tree-sitter-luau/tree-sitter-luau.wasm");
      return Language.load(wasm);
    })();
  }
  return languagePromise;
}

function syntaxIssues(node, source) {
  const lines = source.split(/\r?\n/);
  const issues = [];
  const visit = current => {
    if (current.isError || current.isMissing) {
      const row = current.startPosition.row;
      issues.push({
        type: current.isMissing ? `missing ${current.type}` : current.type,
        line: row + 1,
        column: current.startPosition.column + 1,
        context: (lines[row] || "").trim().slice(0, 160),
      });
    }
    for (const child of current.children) visit(child);
  };
  visit(node);
  return issues;
}

export async function validateSource(source, label = "<memory>") {
  if (typeof source !== "string") throw new TypeError("source must be a string");
  const language = await loadLanguage();
  const parser = new Parser();
  parser.setLanguage(language);
  const tree = parser.parse(source);
  const issues = syntaxIssues(tree.rootNode, source);
  tree.delete();
  parser.delete();
  return { label, ok: issues.length === 0, issues };
}

export async function validateFiles(files) {
  const results = [];
  for (const file of files) {
    const absolute = path.resolve(file);
    results.push(await validateSource(fs.readFileSync(absolute, "utf8"), absolute));
  }
  return results;
}

async function main() {
  const files = process.argv.slice(2);
  if (!files.length) {
    console.error("Usage: node tools/validate_luau_syntax.mjs <file.lua|file.luau> [...]");
    process.exitCode = 2;
    return;
  }
  const results = await validateFiles(files);
  for (const result of results) {
    if (result.ok) {
      console.log(`PASS ${result.label}`);
      continue;
    }
    console.error(`FAIL ${result.label}`);
    for (const issue of result.issues) {
      console.error(`  ${issue.line}:${issue.column} ${issue.type} ${issue.context}`);
    }
  }
  if (results.some(result => !result.ok)) process.exitCode = 1;
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  main().catch(error => {
    console.error(error.stack || error);
    process.exitCode = 1;
  });
}
