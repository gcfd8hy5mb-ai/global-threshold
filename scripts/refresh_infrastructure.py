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
def parse_reliability(raw):
    from html.parser import HTMLParser
    class Rows(HTMLParser):
        def __init__(self): super().__init__(); self.rows=[]; self.row=None; self.cell=None
        def handle_starttag(self,tag,attrs):
            if tag=="tr": self.row=[]
            if tag in ("td","th") and self.row is not None: self.cell=[]
        def handle_data(self,data):
            if self.cell is not None: self.cell.append(data)
        def handle_endtag(self,tag):
            if tag in ("td","th") and self.cell is not None and self.row is not None:
                self.row.append(" ".join("".join(self.cell).split())); self.cell=None
            if tag=="tr" and self.row is not None:
                self.rows.append(self.row); self.row=None
    import math,re
    parser=Rows();parser.feed(raw.decode("utf-8",errors="replace"))
    text=raw.decode("utf-8",errors="replace")
    if not re.search(r"Table\s*11\.1",text,re.I) or "SAIDI" not in text or "SAIFI" not in text: raise ValueError("EIA reliability table not recognized")
    years={}
    for row in parser.rows:
        if len(row)!=16 or not re.fullmatch(r"20\d\d",row[0]): continue
        try:
            y=int(row[0]); a,b,c=(float(v.replace(",","")) for v in row[1:4])
            if 2010<=y<dt.date.today().year and all(math.isfinite(v) and v>=0 for v in (a,b,c)): years[y]={"year":y,"saidi":a,"saifi":b,"caidi":c}
        except ValueError: continue
    if len(years)<2: raise ValueError("Insufficient national annual reliability rows")
    return sorted(years.values(),key=lambda r:r["year"])[-10:]
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
    eia="https://www.eia.gov/electricity/annual/table.php?t=epa_11_01.html"
    try:
        with urllib.request.urlopen(urllib.request.Request(eia,headers={"User-Agent":"Global Threshold public research"}),timeout=25) as r: raw=r.read(3000001)
        if len(raw)>3000000: raise ValueError("EIA response too large")
        snapshot["powerReliability"]={"status":"available","source":eia,"method":"IEEE, all events including major event days","annual":parse_reliability(raw)}
    except Exception as e:
        print("EIA reliability",type(e).__name__,str(e))
        snapshot["powerReliability"]={"status":"retrieval_failed","source":eia}
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(snapshot,indent=2)+"\n")
    if snapshot["aviation"]["status"]!="available": return 1
    return 0
if __name__=="__main__": raise SystemExit(main())
