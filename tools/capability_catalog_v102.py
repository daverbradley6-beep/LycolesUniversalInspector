#!/usr/bin/env python3
"""v102 inspect client-visible object inventories and compile an evidence-based capability catalog.

No game-side writes, remote invocation, exploit discovery or anti-cheat bypass.
"""
import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from inspection_adapter_v101 import adapt
from client_observer_compiler_v100 import generate, audit

RULES={
 "TextLabel":("display","Text"),
 "TextButton":("visible_button","Text"),
 "ImageButton":("visible_button","Visible"),
 "TextBox":("text_input","Text"),
 "IntValue":("value","Value"),
 "NumberValue":("value","Value"),
 "BoolValue":("value","Value"),
 "StringValue":("value","Value"),
 "ProximityPrompt":("proximity_prompt","Enabled"),
 "ClickDetector":("click_detector","Name"),
 "Tool":("equippable_tool","Name"),
 "ScreenGui":("screen_gui","Enabled"),
}
CAPABILITIES={"display","visible_button","text_input","value","proximity_prompt",
              "click_detector","equippable_tool","screen_gui"}
def classify(document,place_id,max_items=150):
    if not isinstance(document,(dict,list)):
        raise ValueError("invalid inspection export")
    if isinstance(document,list):
        rows=document
    else:
        rows=next((document[k] for k in ("objects","instances","entries","observations")
                   if isinstance(document.get(k),list)),None)
    if rows is None:raise ValueError("missing object collection")
    prepared=[]
    catalog=[]
    rejected=Counter()
    for i,row in enumerate(rows):
        if not isinstance(row,dict):
            rejected["invalid_row"]+=1
            continue
        class_name=row.get("className",row.get("class"))
        if class_name not in RULES:
            rejected["unsupported_class"]+=1
            continue
        kind,prop=RULES[class_name]
        path=row.get("path",row.get("fullName",row.get("fullPath")))
        item={"id":"Detected"+str(i+1),"path":path,"property":prop,
              "label":str(class_name)+" "+str(row.get("name",""))}
        try:
            report,_=adapt([item],place_id,1)
        except (ValueError,TypeError):
            rejected["invalid_path"]+=1
            continue
        observation=report["observations"][0]
        observation["label"]=observation["label"][:100]
        prepared.append(observation)
        catalog.append({"id":observation["id"],"className":class_name,
                        "path":observation["path"],"capability":kind,
                        "property":prop,"actionGenerated":False,
                        "verifiedInGame":False})
        if len(prepared)>=max_items:break
    if not prepared:
        raise ValueError("no supported inspectable objects")
    report={"schemaVersion":"100.client-observations",
            "placeId":place_id,"observations":prepared}
    return report,{"schemaVersion":"102.catalog","placeId":place_id,
                   "capabilities":catalog,"counts":dict(sorted(Counter(
                       x["capability"] for x in catalog).items())),
                   "rejections":dict(sorted(rejected.items())),
                   "actionGeneration":False,"verifiedInGame":False}

def build(document,place_id,output,max_items=150):
    report,catalog=classify(document,place_id,max_items)
    root=Path(output)
    generate(report,root)
    result=audit(root)
    if not result["ok"]:
        raise RuntimeError("v100 artifact audit failed: "+repr(result["issues"]))
    payload=(json.dumps(catalog,sort_keys=True,indent=2,ensure_ascii=False)+"\n").encode("utf-8")
    (root/"capabilities-v102.json").write_bytes(payload)
    digest=hashlib.sha256(payload).hexdigest()
    return {"schemaVersion":"102.build","placeId":place_id,
            "capabilityCount":len(catalog["capabilities"]),
            "capabilitySha256":digest,"v100AuditPassed":True,
            "verifiedInGame":False}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--inspection",type=Path,required=True)
    p.add_argument("--place-id",type=int,required=True)
    p.add_argument("--output",type=Path,default=Path("build/release-v102"))
    p.add_argument("--max-items",type=int,default=150)
    args=p.parse_args()
    source=json.loads(args.inspection.read_text(encoding="utf-8-sig"))
    print(json.dumps(build(source,args.place_id,args.output,args.max_items)))
if __name__=="__main__":
    main()
