#!/usr/bin/env python3
"""v52 one-command offline build and deterministic smoke checks.

No claim of arbitrary-game automation: gameplay mechanics require authorized APIs.
"""
import argparse,json,subprocess,sys,tempfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
from adaptive_probe_v44 import paths
from auto_pipeline_v46 import generate_auto
from feature_dashboard_v47 import generate as dashboard
from passive_observer_v48 import generate as observer,analyze as analyze48
from feature_synthesizer_v49 import synthesize
from action_contract_v50 import generate as actions
from auto_actions_v51 import compile_auto

def synthetic_receipt(manifest):
    pp=paths(manifest)
    snapshots=[]
    for i in range(1,4):
        checks=[{"path":p,"present":True,"className":"IntValue","value":str(i if p.startswith("Players.LocalPlayer.") else 1)} for p in pp]
        snapshots.append({"index":i,"checks":checks})
    return {"schemaVersion":"48.0","placeId":manifest["placeId"],"scanId":manifest["scanId"],
            "sourceFingerprint":manifest["sourceFingerprint"],"clientReceiptUntrusted":True,
            "observations":snapshots}

def build(manifest,out,receipt=None):
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    outputs={}
    def save(name,value):
        target=out/name
        target.write_text(value,encoding="utf-8")
        outputs[name]=target
    save("auto-probe-v46.luau",generate_auto(manifest))
    save("feature-dashboard-v47.luau",dashboard(manifest))
    save("passive-observer-v48.luau",observer(manifest))
    if receipt is not None:
        report=analyze48(manifest,receipt)
        candidates=synthesize(manifest,report)
        contract,audit=compile_auto(manifest,report)
        for name,obj in (("state-changes-v48.json",report),("feature-candidates-v49.json",candidates),
                         ("auto-actions-v51.json",contract),("auto-actions-audit-v51.json",audit)):
            save(name,json.dumps(obj,indent=2,sort_keys=True)+"\n")
        if contract["actions"]:
            save("auto-actions-v51.luau",actions(contract))
        else:
            stale=out/"auto-actions-v51.luau"
            if stale.exists():stale.unlink()
    return outputs

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest",type=Path,default=Path("build/generation-manifest-v42.json"))
    parser.add_argument("--receipt",type=Path)
    parser.add_argument("--output",type=Path,default=Path("build/release-v52"))
    parser.add_argument("--self-test",action="store_true")
    parser.add_argument("--test-suite",action="store_true")
    args=parser.parse_args()
    if args.test_suite:
        result=subprocess.run([sys.executable,"-m","unittest","discover","-s","tests","-p","test_v*.py"],cwd=ROOT,check=False)
        if result.returncode:raise SystemExit(result.returncode)
    if args.manifest.stat().st_size>8_000_000:raise ValueError("Manifest too large")
    manifest=json.loads(args.manifest.read_text(encoding="utf-8-sig"))
    receipt=None
    if args.receipt:
        if args.receipt.stat().st_size>16_000_000:raise ValueError("Receipt too large")
        receipt=json.loads(args.receipt.read_text(encoding="utf-8-sig"))
    elif args.self_test:
        receipt=synthetic_receipt(manifest)
    outputs=build(manifest,args.output,receipt)
    if args.self_test:
        if not (args.output/"feature-candidates-v49.json").exists():raise RuntimeError("Missing synthesis")
        if not (args.output/"auto-actions-v51.json").exists():raise RuntimeError("Missing action contract")
        report=json.loads((args.output/"auto-actions-audit-v51.json").read_text(encoding="utf-8"))
        if report["inventoryPaths"]!=len(paths(manifest)):raise RuntimeError("Inventory mismatch")
        print("Synthetic offline smoke test passed. NOT a live gameplay validation.")
    print("v52 produced",len(outputs),"artifacts in",args.output)
if __name__=="__main__":main()
