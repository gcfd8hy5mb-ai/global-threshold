import datetime as dt
import json, pathlib, urllib.request, xml.etree.ElementTree as ET
URL="https://nasstatus.faa.gov/api/airport-status-information"
OUT=pathlib.Path("data/infrastructure.json")
def parse(raw):
    root=ET.fromstring(raw)
    if root.tag!="AIRPORT_STATUS_INFORMATION": raise ValueError("Unexpected FAA schema")
    stamp=root.findtext("Update_Time")
    if not stamp: raise ValueError("Missing FAA update timestamp")
    # Public aggregate counts only: no individual facility details.
    groups={}
    for group in root.findall("Delay_type"):
        name=group.findtext("Name")
        if not name: raise ValueError("Missing delay category")
        count=sum(1 for node in group.iter() if node.tag=="ARPT")
        groups[name]=groups.get(name,0)+count
    return {"sourceUpdated":stamp,"categories":[{"label":k,"reportedEntries":v} for k,v in sorted(groups.items())]}
def main():
    now=dt.datetime.now(dt.timezone.utc).isoformat()
    try:
        with urllib.request.urlopen(urllib.request.Request(URL,headers={"User-Agent":"Global Threshold public research"}),timeout=25) as r:
            raw=r.read(2000001)
        if len(raw)>2000000: raise ValueError("FAA response too large")
        report=parse(raw)
        snapshot={"generatedAt":now,"aviation":{"status":"available",**report}}
    except Exception as e:
        print(type(e).__name__,str(e))
        snapshot={"generatedAt":now,"aviation":{"status":"retrieval_failed"}}
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(snapshot,indent=2)+"\n")
    if snapshot["aviation"]["status"]!="available": return 1
    return 0
if __name__=="__main__": raise SystemExit(main())
