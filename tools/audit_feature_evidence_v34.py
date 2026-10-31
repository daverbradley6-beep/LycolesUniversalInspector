#!/usr/bin/env python3
"""v34: compare v32 feature hypotheses with independently extracted lexical evidence.

Conservative review gate. Only claims static corroboration, never execution.
"""
import argparse,json,pathlib
def audit(feature_report,lexical_corpus):
    if feature_report.get("schemaVersion")!="32.0" or lexical_corpus.get("schemaVersion")!="34.0":
        raise ValueError("Expected v32 feature intelligence and v34 lexical corpus")
    reports={r.get("file"):r for r in lexical_corpus.get("reports",[]) if isinstance(r,dict)}
    results=[]
    for feature in feature_report.get("features",[]):
        filename=feature.get("sourceFile")
        evidence=reports.get(filename)
        name=feature.get("name")
        if not evidence:
            status="missing-source-evidence";matched=[]
        elif feature.get("sourceSha256")!=evidence.get("sha256"):
            status="source-hash-mismatch";matched=[]
        else:
            matched=[f for f in evidence.get("functions",[]) if f.get("name")==name]
            if name=="<top-level>":
                status="requires-manual-review"
            else:
                status="lexically-corroborated" if matched else "function-not-found"
        results.append({"featureId":feature.get("id"),"sourceFile":filename,"name":name,
                        "status":status,"matchedDefinitions":matched,
                        "runtimeVerified":False,"serverOutcomeVerified":False})
    return {"schemaVersion":"34.0","source":"offline-evidence-audit",
            "summary":{"features":len(results),"lexicallyCorroborated":sum(x["status"]=="lexically-corroborated" for x in results)},
            "features":results,"approvedForGameplayAutomation":False,
            "notice":"Lexical corroboration is not gameplay verification or permission to execute unknown actions."}
def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("feature_report",type=pathlib.Path)
    p.add_argument("lexical_report",type=pathlib.Path)
    p.add_argument("--output",type=pathlib.Path,default=pathlib.Path("build/evidence-audit-v34.json"))
    a=p.parse_args()
    result=audit(json.loads(a.feature_report.read_text(encoding="utf-8")),
                 json.loads(a.lexical_report.read_text(encoding="utf-8")))
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print("Corroborated",result["summary"]["lexicallyCorroborated"],"of",result["summary"]["features"],"static feature definitions")
if __name__=="__main__":main()
