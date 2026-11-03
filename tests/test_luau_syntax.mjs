import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { spawnSync } from "node:child_process";
import test from "node:test";
import { fileURLToPath } from "node:url";
import { validateFiles, validateSource } from "../tools/validate_luau_syntax.mjs";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

function assertValid(results) {
  const failures = results.filter(result => !result.ok);
  assert.deepEqual(failures, [], JSON.stringify(failures, null, 2));
}

test("parser rejects malformed Luau", async () => {
  const result = await validateSource("local broken = function(\n", "malformed fixture");
  assert.equal(result.ok, false);
  assert.ok(result.issues.length > 0);
});

test("checked-in Luau sources parse", async () => {
  const files = fs.readdirSync(ROOT)
    .filter(name => name.endsWith(".lua"))
    .map(name => path.join(ROOT, name));
  files.push(path.join(ROOT, "client", "client_observation_collector_v101.lua"));
  assertValid(await validateFiles(files));
});

test("representative generated Luau artifacts parse", async t => {
  const output = fs.mkdtempSync(path.join(os.tmpdir(), "lycoles-luau-"));
  t.after(() => fs.rmSync(output, { recursive: true, force: true }));
  const script = String.raw`
import sys
from pathlib import Path
root=Path(sys.argv[2])
out=Path(sys.argv[1])
sys.path.insert(0,str(root/'tools'))
from balanced_discovery_v54 import generate as balanced
from interactive_runner_v82 import generate as runner
from release_pipeline_v104 import build, luau
from integrated_pipeline_v106 import generate as integrated
from integrated_pipeline_v107 import generate as identity_integrated
from generate_admin_commands import render as admin_commands
from generate_egg_autofarm import render as egg_autofarm
place=85896571713843
inspection={'placeId':place,'objects':[
 {'path':['PlayerGui','HUD','Coins'],'className':'TextLabel'},
 {'path':['Players','PlayerStats','Wins'],'className':'IntValue'},
 {'path':['Workspace','Chest','Prompt'],'className':'ProximityPrompt'},
]}
(out/'v54.luau').write_text(balanced(place),encoding='utf-8')
contract={'placeId':place,'contracts':[{'id':'inspect','approved':True,'executionEnabled':False,'input':['gui',[
 {'name':'HUD','className':'ScreenGui','ordinal':1},
 {'name':'Inspect','className':'TextButton','ordinal':1},
]]}]}
(out/'v82.luau').write_text(runner(contract,place)[0],encoding='utf-8')
(out/'v104.luau').write_text(luau(build(inspection,place)),encoding='utf-8')
(out/'admin.luau').write_text(admin_commands(place),encoding='utf-8')
egg=egg_autofarm({'schemaVersion':'111.action-capabilities.1','placeId':place,
 'claims':{'sourceAuthenticityVerified':False,'causalityProven':False,'serverAuthorityVerified':False,
  'runtimeVerified':False,'gameplayVerified':False,'actionOutcomesVerified':False},
 'eggHatching':{'automaticSingleTrialReady':True,'targets':[{
  'label':'Rainbow Egg','path':'Workspace.Rendered.Rainbow Egg.Prompt.ProximityPrompt',
  'controlType':'ProximityPrompt.Triggered','evidenceTier':'temporal-state-increment-observed',
  'observedTriggers':1,'incrementObservations':1,'outcomeKeys':['leaderstats.🥚 Hatches'],
  'causalityProven':False,'runtimeVerified':False,'gameplayVerified':False} ]}})
(out/'egg.luau').write_text(egg,encoding='utf-8')
(out/'egg-admin.luau').write_text(egg+'\n'+admin_commands(place),encoding='utf-8')
integrated(inspection,place,out/'v106')
identity_integrated({'placeId':place,'observations':[
 {'path':['Workspace','Stats','Coins'],'pathIdentity':[
  {'name':'Workspace','className':'Workspace','ordinal':1},
  {'name':'Stats','className':'Folder','ordinal':1},
  {'name':'Coins','className':'IntValue','ordinal':2},
 ],'className':'IntValue'},
]},place,out/'v107')
`;
  const generated = spawnSync("python", ["-B", "-c", script, output, ROOT], {
    cwd: ROOT,
    encoding: "utf8",
    env: { ...process.env, PYTHONDONTWRITEBYTECODE: "1" },
  });
  assert.equal(generated.status, 0, generated.stderr || generated.stdout);
  const files = [
    path.join(output, "v54.luau"),
    path.join(output, "v82.luau"),
    path.join(output, "v104.luau"),
    path.join(output, "admin.luau"),
    path.join(output, "egg.luau"),
    path.join(output, "egg-admin.luau"),

    path.join(output, "v106", "LycolesFunctionalObserver.client.lua"),
    path.join(output, "v107", "LycolesFunctionalObserver.client.lua"),
  ];
  assertValid(await validateFiles(files));
});
