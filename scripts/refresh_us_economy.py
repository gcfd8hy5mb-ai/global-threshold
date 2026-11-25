from concurrent.futures import ThreadPoolExecutor
import xml.etree.ElementTree as ET
import zipfile
import csv, json, io, datetime as dt, urllib.request, math, pathlib, time
DEFS = json.loads("[{\"id\":\"CPIAUCNS\",\"label\":\"Inflation (CPI YoY)\",\"frequency\":\"Monthly\",\"unit\":\"%\",\"maxAge\":75,\"source\":\"BLS via FRED\",\"transform\":\"yoy\"},{\"id\":\"UNRATE\",\"label\":\"Unemployment rate\",\"frequency\":\"Monthly\",\"unit\":\"%\",\"maxAge\":75,\"source\":\"BLS via FRED\"},{\"id\":\"A191RL1Q225SBEA\",\"label\":\"Real GDP growth (annualized)\",\"frequency\":\"Quarterly\",\"unit\":\"%\",\"maxAge\":180,\"source\":\"BEA via FRED\"},{\"id\":\"DFF\",\"label\":\"Effective federal funds rate\",\"frequency\":\"Daily\",\"unit\":\"%\",\"maxAge\":10,\"source\":\"Federal Reserve via FRED\"},{\"id\":\"DGS10\",\"label\":\"10-year Treasury yield\",\"frequency\":\"Daily\",\"unit\":\"%\",\"maxAge\":10,\"source\":\"Federal Reserve via FRED\"},{\"id\":\"DCOILWTICO\",\"label\":\"WTI crude oil\",\"frequency\":\"Daily\",\"unit\":\"$/bbl\",\"maxAge\":14,\"source\":\"EIA via FRED\"}]")
DEFS += json.loads("[{\"id\":\"DHHNGSP\",\"label\":\"Henry Hub natural gas\",\"frequency\":\"Daily\",\"unit\":\"$/MMBtu\",\"maxAge\":14,\"source\":\"EIA via FRED\",\"workbook\":\"https://www.eia.gov/dnav/ng/hist_xls/RNGWHHDd.xls\",\"header\":[\"Henry Hub\"]},{\"id\":\"WCESTUS1\",\"label\":\"US commercial crude stocks (excl. SPR)\",\"frequency\":\"Weekly\",\"unit\":\"thousand bbl\",\"maxAge\":21,\"source\":\"EIA direct\",\"workbook\":\"https://www.eia.gov/dnav/pet/hist_xls/WCESTUS1w.xls\",\"header\":[\"crude oil\",\"excluding SPR\"]},{\"id\":\"WCRFPUS2\",\"label\":\"US crude production estimate\",\"frequency\":\"Weekly\",\"unit\":\"thousand bbl/day\",\"maxAge\":21,\"source\":\"EIA direct\",\"workbook\":\"https://www.eia.gov/dnav/pet/hist_xls/WCRFPUS2w.xls\",\"header\":[\"production\",\"crude oil\"]}]")
DEFS += [{"id":"DGS2","label":"2-year Treasury yield","frequency":"Daily","unit":"%","maxAge":10,"source":"US Treasury direct"},{"id":"DGS3MO","label":"3-month Treasury yield","frequency":"Daily","unit":"%","maxAge":10,"source":"US Treasury direct"}]
DEFS += [{"id":"NFCI","label":"National Financial Conditions Index","frequency":"Weekly","unit":"index","maxAge":21,"source":"Chicago Fed via FRED"}]
OUT = pathlib.Path("data/us-economy.json")
def retrieve(d):
    start = (dt.date.today()-dt.timedelta(days=800)).isoformat()
    url = "https://fred.stlouisfed.org/graph/fredgraph.csv?id="+d["id"]+"&cosd="+start
    req = urllib.request.Request(url, headers={"User-Agent":"Global Threshold public economic research/1.0"})
    with urllib.request.urlopen(req,timeout=30) as r:
        reader=csv.reader(io.StringIO(r.read().decode("utf-8-sig")))
        header=next(reader)
        if len(header)!=2 or header[1]!=d["id"]: raise ValueError("Unexpected CSV columns")
        points={}
        for row in reader:
            if len(row)!=2: continue
            try:
                day=dt.date.fromisoformat(row[0]); value=float(row[1])
                if math.isfinite(value) and day<=dt.date.today(): points[day]=value
            except ValueError: continue
    if d.get("transform")=="yoy":
        points={day:(value/points[day.replace(year=day.year-1)]-1)*100 for day,value in points.items() if day.day==1 and day.replace(year=day.year-1) in points and points[day.replace(year=day.year-1)]>0}
    ordered=sorted(points.items(),reverse=True)
    if not ordered: raise ValueError("No valid observations")
    def item(pair): return {"date":pair[0].isoformat(),"value":round(pair[1],4)}
    return {**d,"latest":item(ordered[0]),"prior":item(ordered[1]) if len(ordered)>1 else None,"retrievedAt":dt.datetime.now(dt.timezone.utc).isoformat(),"status":"available"}
def bls_fallback(d):
    series = {"CPIAUCNS":"CUUR0000SA0","UNRATE":"LNS14000000"}[d["id"]]
    year=dt.date.today().year
    payload=json.dumps({"seriesid":[series],"startyear":str(year-2),"endyear":str(year)}).encode()
    req=urllib.request.Request("https://api.bls.gov/publicAPI/v1/timeseries/data/",data=payload,headers={"Content-Type":"application/json","User-Agent":"Global Threshold research"})
    with urllib.request.urlopen(req,timeout=20) as r:
        result=json.load(r)
    if result.get("status")!="REQUEST_SUCCEEDED": raise ValueError("BLS request failed")
    points={}
    for x in result["Results"]["series"][0]["data"]:
        if x["period"] not in [f"M{i:02d}" for i in range(1,13)]: continue
        day=dt.date(int(x["year"]),int(x["period"][1:]),1)
        try:
            value=float(x["value"])
        except (ValueError, TypeError, KeyError):
            continue
        if math.isfinite(value) and day<=dt.date.today(): points[day]=value
    if d.get("transform")=="yoy":
        points={day:(value/points[day.replace(year=day.year-1)]-1)*100 for day,value in points.items() if day.replace(year=day.year-1) in points and points[day.replace(year=day.year-1)]>0}
    ordered=sorted(points.items(),reverse=True)
    if not ordered: raise ValueError("No valid BLS observations after skipping missing values")
    def item(pair): return {"date":pair[0].isoformat(),"value":round(pair[1],4)}
    return {**d,"source":"BLS direct","latest":item(ordered[0]),"prior":item(ordered[1]) if len(ordered)>1 else None,"retrievedAt":dt.datetime.now(dt.timezone.utc).isoformat(),"status":"available"}
def direct_rates(d):
    points={}
    if d["id"]=="DFF":
        url="https://markets.newyorkfed.org/api/rates/unsecured/effr/last/10.json"
        with urllib.request.urlopen(url,timeout=20) as r: data=json.load(r)
        for x in data["refRates"]:
            try: points[dt.date.fromisoformat(x["effectiveDate"])]=float(x["percentRate"])
            except (ValueError,TypeError,KeyError): continue
        source="New York Fed direct"
    else:
        url="https://home.treasury.gov/resource-center/data-chart-center/interest-rates/pages/xml?data=daily_treasury_yield_curve&field_tdr_date_value="+str(dt.date.today().year)
        with urllib.request.urlopen(urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0"}),timeout=25) as r: root=ET.fromstring(r.read())
        for node in root.iter():
            if node.tag.split("}")[-1]!="properties": continue
            fields={x.tag.split("}")[-1]:x.text for x in node}
            try: points[dt.date.fromisoformat(fields["NEW_DATE"][:10])]=float(fields[{"DGS10":"BC_10YEAR","DGS2":"BC_2YEAR","DGS3MO":"BC_3MONTH"}[d["id"]]])
            except (ValueError,TypeError,KeyError): continue
        source="US Treasury direct"
    ordered=sorted(((day,val) for day,val in points.items() if day<=dt.date.today() and math.isfinite(val)),reverse=True)
    if not ordered: raise ValueError("No valid direct rate observations")
    def item(pair): return {"date":pair[0].isoformat(),"value":round(pair[1],4)}
    return {**d,"source":source,"sourceUrl":url,"latest":item(ordered[0]),"prior":item(ordered[1]) if len(ordered)>1 else None,"retrievedAt":dt.datetime.now(dt.timezone.utc).isoformat(),"status":"available"}
def direct_gdp(d):
    # BEA's published flat-file archive contains a quarterly CSV with SeriesCode, Period and Value.
    import re
    url="https://www.bea.gov/national/Release/TXT/FlatFiles.ZIP"
    req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0"})
    with urllib.request.urlopen(req,timeout=45) as r: raw=r.read(100_000_001)
    if len(raw)>100_000_000: raise ValueError("BEA archive too large")
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        members=[n for n in z.namelist() if n.lower().endswith("nipadataq.txt")]
        if len(members)!=1: raise ValueError("BEA quarterly table missing")
        if z.getinfo(members[0]).file_size>200_000_000: raise ValueError("BEA table too large")
        points={}
        with z.open(members[0]) as f:
            reader=csv.reader(io.TextIOWrapper(f,encoding="utf-8-sig",errors="replace"))
            head=[re.sub(r"[^a-z0-9]","",x.lower()) for x in next(reader)]
            ci=head.index("seriescode"); pi=head.index("period"); vi=head.index("value")
            for row in reader:
                if len(row)<=max(ci,pi,vi) or row[ci].strip()!="A191RL": continue
                match=re.fullmatch(r"(\d{4})\s*Q?\s*([1-4])",row[pi].strip(),re.I)
                if not match: continue
                try:
                    day=dt.date(int(match[1]),3*(int(match[2])-1)+1,1)
                    value=float(row[vi].replace(",",""))
                    if math.isfinite(value) and day<=dt.date.today(): points[day]=value
                except (ValueError,TypeError): continue
    return pack_direct(d,points,"BEA direct",url)
def direct_oil(d):
    import xlrd
    url=d.get("workbook","https://www.eia.gov/dnav/pet/hist_xls/RWTCd.xls")
    req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0"})
    with urllib.request.urlopen(req,timeout=25) as r: raw=r.read(15_000_001)
    if len(raw)>15_000_000: raise ValueError("EIA workbook too large")
    book=xlrd.open_workbook(file_contents=raw)
    sheet=book.sheet_by_name("Data 1")
    header=" ".join(str(sheet.cell_value(i,j)).lower() for i in range(min(5,sheet.nrows)) for j in range(sheet.ncols))
    if not all(term.lower() in header for term in d.get("header",["WTI"])): raise ValueError("Unexpected EIA series")
    points={}
    for i in range(sheet.nrows):
        try:
            day=xlrd.xldate_as_datetime(sheet.cell_value(i,0),book.datemode).date()
            value=float(sheet.cell_value(i,1))
            if math.isfinite(value) and day<=dt.date.today(): points[day]=value
        except (ValueError,TypeError,OverflowError): continue
    return pack_direct(d,points,"EIA direct",url)
def pack_direct(d,points,source,url):
    ordered=sorted(points.items(),reverse=True)
    if not ordered: raise ValueError("No valid direct observations")
    def item(pair): return {"date":pair[0].isoformat(),"value":round(pair[1],4)}
    return {**d,"source":source,"sourceUrl":url,"latest":item(ordered[0]),"prior":item(ordered[1]) if len(ordered)>1 else None,"retrievedAt":dt.datetime.now(dt.timezone.utc).isoformat(),"status":"available"}
def collect(d):
    try:
        if d["id"] in ("CPIAUCNS","UNRATE"): return bls_fallback(d)
        if d["id"] in ("DFF","DGS10","DGS2","DGS3MO"): return direct_rates(d)
        if d["id"]=="A191RL1Q225SBEA": return direct_gdp(d)
        if d["id"]=="DCOILWTICO" or d.get("workbook"): return direct_oil(d)
    except Exception as e:
        print(d["id"],"Direct",type(e).__name__,str(e),flush=True)
    if d["id"] in ("WCESTUS1","WCRFPUS2"): return {**d,"status":"retrieval_failed"}
    try: return retrieve(d)
    except Exception as e:
        print(d["id"],"FRED",type(e).__name__,str(e),flush=True)
        if d["id"] in ("CPIAUCNS","UNRATE"):
            try: return bls_fallback(d)
            except Exception as fallback: print(d["id"],"BLS",type(fallback).__name__,str(fallback),flush=True)
        return {**d,"status":"retrieval_failed"}
def main():
    old={}
    if OUT.exists():
        try: old={x["id"]:x for x in json.loads(OUT.read_text())["rows"]}
        except (ValueError,KeyError,TypeError): pass
    with ThreadPoolExecutor(max_workers=3) as pool:
        rows=list(pool.map(collect,DEFS))
    rows=[{**r,**old.get(r["id"],{}),"status":"retrieval_failed"} if r["status"]=="retrieval_failed" else r for r in rows]
    print("Successful series:",sum(r["status"]=="available" for r in rows),"/",len(rows),flush=True)
    for r in rows:
        history={x["date"]:x for x in old.get(r["id"],{}).get("history",[]) if isinstance(x,dict) and "date" in x and "value" in x}
        if r["status"]=="available":
            for x in (r.get("prior"),r.get("latest")):
                if x: history[x["date"]]=x
        r["history"]=sorted(history.values(),key=lambda x:x["date"])[-400:]
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps({"generatedAt":dt.datetime.now(dt.timezone.utc).isoformat(),"rows":rows},indent=2)+"\n")
if __name__=="__main__": main()
