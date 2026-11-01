#!/usr/bin/env python3
"""v46 automatic bounded sampling and console-transcript import."""
import argparse
import json
import re
from pathlib import Path
from adaptive_probe_v44 import paths, analyze, generate as generate_v44
from evidence_compiler_v45 import compile_contracts

BEGIN="LYCOLES_V44_RECEIPT_BEGIN"
END="LYCOLES_V44_RECEIPT_END"
MAX_BYTES=16_000_000

def extract(text):
    if len(text.encode("utf-8"))>MAX_BYTES:
        raise ValueError("Transcript too large")
    # Console prefix and surrounding logs are permitted, but never execute transcript text.
    matches=[]
    pos=0
    while True:
        b=text.find(BEGIN,pos)
        if b<0:break
        e=text.find(END,b+len(BEGIN))
        if e<0:break
        chunk=text[b+len(BEGIN):e]
        candidates=[line.strip() for line in chunk.splitlines() if line.strip()]
        for line in candidates:
            start=line.find('{"')
            if start<0:continue
            try:
                obj=json.loads(line[start:])
            except json.JSONDecodeError:
                continue
            if isinstance(obj,dict) and obj.get("schemaVersion")=="44.0":
                matches.append(obj)
        pos=e+len(END)
    if not matches:
        # Also accept a raw JSON receipt file.
        try:
            raw=json.loads(text.lstrip("\ufeff"))
        except json.JSONDecodeError as ex:
            raise ValueError("No complete v44 receipt found") from ex
        if not isinstance(raw,dict) or raw.get("schemaVersion")!="44.0":
            raise ValueError("Not a v44 receipt")
        matches=[raw]
    return matches[-1]

def generate_auto(manifest, interval=4, count=6):
    if type(interval) is not int or not 3<=interval<=30:
        raise ValueError("Invalid interval")
    if type(count) is not int or not 2<=count<=8:
        raise ValueError("Invalid snapshot count")
    script=generate_v44(manifest)
    # Preserve v44's inspector and receipt schema, replace manual click callback
    start=script.index('btn.Activated:Connect(function()')
    script=script[:start]+'''
-- v46: automatically sample while the player uses the game normally.
-- Each snapshot is read-only and the last one emits a single complete receipt.
btn.Text="Lycoles v46 | Automatic collection started"
task.spawn(function()
 for index=1, AUTO_COUNT do
  if not gui.Parent then return end
  local checks={}
  local found=0
  for _,path in ipairs(cfg.paths) do
   local check=inspect(path)
   if check.found then found+=1 end
   table.insert(checks,check)
  end
  table.insert(snapshots,{index=index,checks=checks})
  btn.Text="Lycoles v46 | "..index.."/"..AUTO_COUNT.." samples; "..found.." visible"
  if index<AUTO_COUNT then task.wait(AUTO_INTERVAL) end
 end
 emit()
 btn.Text="Lycoles v46 | Finished: copy receipt from console"
end)
'''
    return script.replace("AUTO_COUNT",str(count)).replace("AUTO_INTERVAL",str(interval))

def process(manifest, transcript):
    receipt=extract(transcript)
    report=analyze(manifest,receipt)
    contracts=compile_contracts(manifest,report)
    return receipt,report,contracts

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("manifest",type=Path)
    p.add_argument("--console",type=Path)
    p.add_argument("--output",type=Path,default=Path("build"))
    p.add_argument("--interval",type=int,default=4)
    p.add_argument("--count",type=int,default=6)
    args=p.parse_args()
    if args.manifest.stat().st_size>8_000_000:raise ValueError("Manifest too large")
    manifest=json.loads(args.manifest.read_text(encoding="utf-8-sig"))
    script=generate_auto(manifest,args.interval,args.count)
    args.output.mkdir(parents=True,exist_ok=True)
    (args.output/"auto-probe-v46.luau").write_text(script,encoding="utf-8")
    print("Generated automatic probe for",len(paths(manifest)),"paths")
    if args.console:
        if args.console.stat().st_size>MAX_BYTES:raise ValueError("Transcript too large")
        receipt,report,contracts=process(manifest,args.console.read_text(encoding="utf-8-sig"))
        for name,obj in (("receipt-v46.json",receipt),("adaptive-report-v44.json",report),("evidence-contracts-v45.json",contracts)):
            (args.output/name).write_text(json.dumps(obj,indent=2,sort_keys=True)+"\n",encoding="utf-8")
        print("Imported",report["snapshotsAnalyzed"],"snapshots and compiled",contracts["featureCount"],"feature contracts")
if __name__=="__main__":main()
