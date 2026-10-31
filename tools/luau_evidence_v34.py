#!/usr/bin/env python3
"""v34: non-executing Luau lexical evidence; no gameplay verification."""
import argparse,hashlib,json,pathlib,re
VERSION="34.0"
MAX_BYTES=4000000
IDENT=re.compile(r"[A-Za-z_][A-Za-z_0-9]*")
LONG=re.compile(r"\[(=*)\[")
API={"FireServer","InvokeServer","Connect","WaitForChild","FindFirstChild","GetAttribute","SetAttribute","Destroy","Disconnect","GetService","GetChildren","GetDescendants"}
def tokens(src):
    if not isinstance(src,str):raise TypeError("Expected source text")
    out=[];i=0;line=1;n=len(src)
    while i<n:
        c=src[i]
        if c=="\n":line+=1;i+=1;continue
        if c.isspace():i+=1;continue
        if src.startswith("--",i):
            m=LONG.match(src,i+2)
            if m:
                close="]"+m.group(1)+"]";j=src.find(close,m.end())
                end=n if j<0 else j+len(close)
                line+=src[i:end].count("\n");i=end
            else:
                j=src.find("\n",i);i=n if j<0 else j
            continue
        m=LONG.match(src,i)
        if m:
            close="]"+m.group(1)+"]";j=src.find(close,m.end())
            end=n if j<0 else j+len(close)
            out.append(("string",src[m.end():n if j<0 else j],line))
            line+=src[i:end].count("\n");i=end;continue
        if c in ("'",'"'):
            start=line;q=c;j=i+1;chars=[]
            while j<n:
                ch=src[j]
                if ch=="\\" and j+1<n:
                    if src[j+1]=="\n":line+=1
                    chars.append(src[j+1]);j+=2;continue
                if ch==q:j+=1;break
                if ch=="\n":line+=1
                chars.append(ch);j+=1
            out.append(("string","".join(chars),start));i=j;continue
        m=IDENT.match(src,i)
        if m:out.append(("identifier",m.group(),line));i=m.end();continue
        out.append(("symbol",c,line));i+=1
    return out
def extract(src,filename="unknown.lua"):
    if len(src.encode("utf-8"))>MAX_BYTES:raise ValueError("File exceeds size limit")
    ts=tokens(src);functions=[];calls=[];lookups=[];services=[];paths=[]
    for i,(kind,value,line) in enumerate(ts):
        if kind!="identifier":continue
        if value=="function" and i+1<len(ts) and ts[i+1][0]=="identifier":
            name=ts[i+1][1];j=i+2
            while j+1<len(ts) and ts[j][1] in (".",":") and ts[j+1][0]=="identifier":
                name+=ts[j][1]+ts[j+1][1];j+=2
            if j<len(ts) and ts[j][1]=="(":functions.append({"name":name,"line":line})
        if value in API and i+1<len(ts) and ts[i+1][1]=="(" and i>0 and ts[i-1][1] in (":","."):
            calls.append({"api":value,"line":line})
            if value in ("WaitForChild","FindFirstChild","GetService") and i+2<len(ts) and ts[i+2][0]=="string":
                item={"value":ts[i+2][1][:100],"line":line}
                if value=="GetService":services.append(item)
                else:lookups.append(item)
        if value in ("workspace","game","Players","PlayerGui","ReplicatedStorage"):
            j=i+1;parts=[value]
            while j+1<len(ts) and ts[j][1]=="." and ts[j+1][0]=="identifier" and len(parts)<13:
                parts.append(ts[j+1][1]);j+=2
            if len(parts)>1:paths.append({"path":".".join(parts),"line":line})
    return {"schemaVersion":VERSION,"source":"offline-lexical-evidence","file":filename,
            "sha256":hashlib.sha256(src.encode()).hexdigest(),"functions":functions,
            "calls":calls,"lookups":lookups,"services":services,"paths":paths,
            "verification":{"executed":False,"runtimeVerified":False,"serverOutcomeVerified":False},
            "limitations":["Lexical evidence is not a Luau AST","No gameplay outcome inferred"]}
def scan(directory):
    root=pathlib.Path(directory)
    if not root.is_dir():raise ValueError("Source directory not found")
    paths=sorted(p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in (".lua",".luau",".txt"))
    if len(paths)>1000:raise ValueError("Too many files")
    reports=[];errors=[]
    for path in paths:
        try:
            if path.stat().st_size>MAX_BYTES:raise ValueError("File exceeds size limit")
            reports.append(extract(path.read_text(encoding="utf-8",errors="replace"),path.relative_to(root).as_posix()))
        except (OSError,ValueError) as exc:errors.append({"file":path.name,"error":str(exc)[:160]})
    return {"schemaVersion":VERSION,"source":"offline-lexical-corpus","reports":reports,"errors":errors,
            "summary":{"files":len(reports),"errors":len(errors)},"runtimeVerified":False}
def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("source_dir",type=pathlib.Path)
    p.add_argument("--output",type=pathlib.Path,default=pathlib.Path("build/luau-evidence-v34.json"))
    a=p.parse_args();report=scan(a.source_dir);a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(report,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print("v34:",report["summary"]["files"],"files;",report["summary"]["errors"],"errors")
    return 2 if report["errors"] else 0
if __name__=="__main__":raise SystemExit(main())
