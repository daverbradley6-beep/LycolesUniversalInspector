#!/usr/bin/env python3
"""Lycoles v31: offline, non-executing Luau corpus and dependency intelligence.

Never executes scripts or downloads remote content. Input is a directory of
source files and optionally a JSON map of already-reviewed dependency sources.
Produces a deterministic evidence manifest suitable for human review.
"""
import argparse
import hashlib
import json
import pathlib
import re
from collections import Counter, defaultdict
from urllib.parse import urlparse

VERSION = "31.0"
MAX_FILE_BYTES = 4_000_000
MAX_FILES = 1000
MAX_DEPENDENCIES = 2000
URL = re.compile(r"https?://[^\s\x22\x27<>\\)]+")
LOAD = re.compile(r"\b(?:loadstring|HttpGet|require|getconnections|FireServer|InvokeServer|readfile|writefile|syn\.protect_gui)\b")
SERVICES = re.compile(r"game:GetService\(\s*['\x22]([A-Za-z0-9_]+)['\x22]\s*\)")
GAME_IDS = re.compile(r"\b(?:game\.)?(PlaceId|GameId)\b")
WORKFLOW = {
    "state_read": re.compile(r"\b(?:FindFirstChild|WaitForChild|GetChildren|GetDescendants|\.Value\b|GetAttribute)\b"),
    "ui_event": re.compile(r"\b(?:MouseButton1Click|Activated|InputBegan|InputChanged|ContextActionService)\b"),
    "loop": re.compile(r"\b(?:while|repeat|RunService|Heartbeat|RenderStepped)\b"),
    "lifecycle": re.compile(r"\b(?:Destroy|Disconnect|UnbindAction|CharacterAdded|AncestryChanged)\b"),
    "remote_call": re.compile(r"\b(?:FireServer|InvokeServer)\b"),
    "local_mutation": re.compile(r"\b(?:SetAttribute|\.Value\s*=|\.Position\s*=|\.CFrame\s*=)\b"),
}
OBFUSCATION = ("Luraph Obfuscator", "MoonSec V3", "IronBrew", "Protected by")
SECRET = re.compile(r"(?i)(?:api[_-]?key|token|password|secret)\s*[:=]\s*['\x22][^'\x22]{8,}['\x22]")
LOAD_URL = re.compile(r"(?:loadstring\s*\(\s*)?game:HttpGet\(\s*['\x22](https?://[^'\x22]+)['\x22]")

def digest(blob):
    return hashlib.sha256(blob).hexdigest()

def classify(source):
    if any(marker.lower() in source[:10000].lower() for marker in OBFUSCATION):
        return "protected-opaque"
    lines = [s.strip() for s in source.splitlines() if s.strip() and not s.lstrip().startswith("--")]
    if not lines:
        return "empty-or-comments"
    operational = sum(bool(re.search(r"\b(?:function|Instance\.new|:Connect|for|while|repeat|:FireServer|:InvokeServer)\b", s)) for s in lines)
    return "loader" if LOAD_URL.search(source) and operational < 3 else "implementation"

def analyze(name, source, blob=None):
    if blob is None:
        blob = source.encode("utf-8")
    urls = sorted(set(URL.findall(source)))[:100]
    dependencies = []
    for url in urls:
        host = (urlparse(url).hostname or "").lower()
        dependencies.append({"url":url, "host":host,
                             "kind":"telemetry" if "telemetry" in url.lower() or "analytics" in url.lower()
                             else "remote-source"})
    category = classify(source)
    methods = dict(Counter(LOAD.findall(source)))
    signals = {key:len(rx.findall(source)) for key,rx in WORKFLOW.items()}
    services = sorted(set(SERVICES.findall(source)))
    game_ids = sorted(set(GAME_IDS.findall(source)))
    warnings = []
    if category == "protected-opaque":
        warnings.append("Protected implementation: behavior cannot be verified statically")
    if category == "loader":
        warnings.append("Loader only: advertised features are not implementation evidence")
    if any(d["kind"]=="telemetry" for d in dependencies):
        warnings.append("Contains external telemetry dependency")
    if "getconnections" in methods or "syn.protect_gui" in methods:
        warnings.append("Executor-specific APIs: not portable Roblox APIs")
    if "FireServer" in methods or "InvokeServer" in methods:
        warnings.append("Remote invocation observed: server outcome unverified")
    if SECRET.search(source):
        warnings.append("Potential embedded secret: redact before sharing")
    if len(urls) >= 100:
        warnings.append("Dependency URL list truncated")
    return {
        "file":name, "sha256":digest(blob), "bytes":len(blob),
        "lineCount":source.count("\n")+1 if source else 0,
        "classification":category, "services":services,
        "gameIdentityFields":game_ids, "methods":methods,
        "workflowSignals":signals, "dependencies":dependencies,
        "warnings":warnings,
        "verification":{"staticParsed":True,"executed":False,"gameplayConfirmed":False}
    }

def build(paths):
    entries=[]
    seen={}
    errors=[]
    for path in paths[:MAX_FILES]:
        try:
            size=path.stat().st_size
            if size>MAX_FILE_BYTES:
                errors.append({"file":path.name,"error":"oversized"});continue
            blob=path.read_bytes()
            source=blob.decode("utf-8",errors="replace")
            item=analyze(path.name,source,blob)
            item["duplicateOf"]=seen.get(item["sha256"])
            seen.setdefault(item["sha256"],path.name)
            entries.append(item)
        except (OSError,ValueError) as exc:
            errors.append({"file":path.name,"error":str(exc)[:150]})
    groups=defaultdict(list)
    dependency_groups=defaultdict(list)
    for item in entries:
        groups[item["classification"]].append(item["file"])
        for dep in item["dependencies"]:
            dependency_groups[dep["url"]].append(item["file"])
    return {
        "schemaVersion":VERSION,
        "source":"offline-static-corpus",
        "limits":{"maxFiles":MAX_FILES,"maxFileBytes":MAX_FILE_BYTES},
        "summary":{"files":len(entries),"errors":len(errors),
                   "classifications":{k:len(v) for k,v in sorted(groups.items())},
                   "duplicateFiles":sum(x["duplicateOf"] is not None for x in entries),
                   "sharedDependencies":sum(len(v)>1 for v in dependency_groups.values())},
        "sharedDependencies":[{"url":u,"files":sorted(v)} for u,v in sorted(dependency_groups.items()) if len(v)>1][:MAX_DEPENDENCIES],
        "files":entries,"errors":errors,
        "scopeNotice":"Static source observations only. No remote fetch, execution, gameplay testing or bypass validation."
    }

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("source_dir",type=pathlib.Path)
    p.add_argument("--output",type=pathlib.Path,default=pathlib.Path("build/script-corpus.json"))
    a=p.parse_args()
    if not a.source_dir.is_dir():
        p.error("source_dir must be an existing directory")
    paths=sorted(x for x in a.source_dir.rglob("*") if x.is_file() and x.suffix.lower() in (".lua",".luau",".txt",".md"))
    result=build(paths)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(result,indent=2,ensure_ascii=False,sort_keys=True)+"\n",encoding="utf-8")
    print("Analyzed",result["summary"]["files"],"files;",result["summary"]["errors"],"errors")
    return 0 if not result["errors"] else 2

if __name__=="__main__":
    raise SystemExit(main())
