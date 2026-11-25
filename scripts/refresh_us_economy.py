from concurrent.futures import ThreadPoolExecutor
import xml.etree.ElementTree as ET
import zipfile
import csv, json, io, datetime as dt, urllib.request, math, pathlib, time
DEFS = json.loads("[{\"id\":\"CPIAUCNS\",\"label\":\"Inflation (CPI YoY)\",\"frequency\":\"Monthly\",\"unit\":\"%\",\"maxAge\":75,\"source\":\"BLS via FRED\",\"transform\":\"yoy\"},{\"id\":\"UNRATE\",\"label\":\"Unemployment rate\",\"frequency\":\"Monthly\",\"unit\":\"%\",\"maxAge\":75,\"source\":\"BLS via FRED\"},{\"id\":\"A191RL1Q225SBEA\",\"label\":\"Real GDP growth (annualized)\",\"frequency\":\"Quarterly\",\"unit\":\"%\",\"maxAge\":180,\"source\":\"BEA via FRED\"},{\"id\":\"DFF\",\"label\":\"Effective federal funds rate\",\"frequency\":\"Daily\",\"unit\":\"%\",\"maxAge\":10,\"source\":\"Federal Reserve via FRED\"},{\"id\":\"DGS10\",\"label\":\"10-year Treasury yield\",\"frequency\":\"Daily\",\"unit\":\"%\",\"maxAge\":10,\"source\":\"Federal Reserve via FRED\"},{\"id\":\"DCOILWTICO\",\"label\":\"WTI crude oil\",\"frequency\":\"Daily\",\"unit\":\"$/bbl\",\"maxAge\":14,\"source\":\"EIA via FRED\"}]")
DEFS += json.loads("[{\"id\":\"DHHNGSP\",\"label\":\"Henry Hub natural gas\",\"frequency\":\"Daily\",\"unit\":\"$/MMBtu\",\"maxAge\":14,\"source\":\"EIA via FRED\",\"workbook\":\"https://www.eia.gov/dnav/ng/hist_xls/RNGWHHDd.xls\",\"header\":[\"Henry Hub\"]},{\"id\":\"WCESTUS1\",\"label\":\"US commercial crude stocks (excl. SPR)\",\"frequency\":\"Weekly\",\"unit\":\"thousand bbl\",\"maxAge\":21,\"source\":\"EIA direct\",\"workbook\":\"https://www.eia.gov/dnav/pet/hist_xls/WCESTUS1w.xls\",\"header\":[\"crude oil\",\"excluding SPR\"]},{\"id\":\"WCRFPUS2\",\"label\":\"US crude production estimate\",\"frequency\":\"Weekly\",\"unit\":\"thousand bbl/day\",\"maxAge\":21,\"source\":\"EIA direct\",\"workbook\":\"https://www.eia.gov/dnav/pet/hist_xls/WCRFPUS2w.xls\",\"header\":[\"production\",\"crude oil\"]}]")
DEFS += [{"id":"DGS2","label":"2-year Treasury yield","frequency":"Daily","unit":"%","maxAge":10,"source":"US Treasury direct"},{"id":"DGS3MO","label":"3-month Treasury yield","frequency":"Daily","unit":"%","maxAge":10,"source":"US Treasury direct"}]
DEFS += [{"id":"NFCI","label":"National Financial Conditions Index","frequency":"Weekly","unit":"index","maxAge":21,"source":"Chicago Fed via FRED"}]
DEFS += [{"id":"GSCPI","label":"Global Supply Chain Pressure Index","frequency":"Monthly","unit":"index","maxAge":75,"source":"New York Fed direct"}]
OUT = pathlib.Path("data/us-economy.json")
def retained_points(ordered):
    cutoff=dt.date.today()-dt.timedelta(days=3660)
    return [{"date":day.isoformat(),"value":round(value,4)} for day,value in reversed(ordered) if day>=cutoff][-4000:]
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
    return {**d,"history":retained_points(ordered),"latest":item(ordered[0]),"prior":item(ordered[1]) if len(ordered)>1 else None,"retrievedAt":dt.datetime.now(dt.timezone.utc).isoformat(),"status":"available"}
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
    return {**d,"source":"BLS direct","history":retained_points(ordered),"latest":item(ordered[0]),"prior":item(ordered[1]) if len(ordered)>1 else None,"retrievedAt":dt.datetime.now(dt.timezone.utc).isoformat(),"status":"available"}
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
    return {**d,"source":source,"sourceUrl":url,"history":retained_points(ordered),"latest":item(ordered[0]),"prior":item(ordered[1]) if len(ordered)>1 else None,"retrievedAt":dt.datetime.now(dt.timezone.utc).isoformat(),"status":"available"}
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
    return {**d,"source":source,"sourceUrl":url,"history":retained_points(ordered),"latest":item(ordered[0]),"prior":item(ordered[1]) if len(ordered)>1 else None,"retrievedAt":dt.datetime.now(dt.timezone.utc).isoformat(),"status":"available"}
def gscpi_csv(d):
    url="https://www.newyorkfed.org/medialibrary/research/interactives/data/gscpi/gscpi_interactive_data.csv"
    with urllib.request.urlopen(urllib.request.Request(url,headers={"User-Agent":"Global Threshold economic research"}),timeout=35) as r:
        raw=r.read(5000001)
    if len(raw)>5000000: raise ValueError("Index CSV too large")
    reader=csv.reader(io.StringIO(raw.decode("utf-8-sig")))
    head=next(reader)
    if len(head)<2 or head[0].strip().lower()!="date": raise ValueError("Unexpected GSCPI header")
    vintage=head[-1].strip()
    release=dt.datetime.strptime(vintage,"%b-%y").date()
    if release.replace(day=1)>dt.date.today(): raise ValueError("Future vintage")
    points={}
    for row in reader:
        if len(row)!=len(head): continue
        try:
            day=dt.datetime.strptime(row[0].strip(),"%d-%b-%Y").date()
            value=float(row[-1])
            if math.isfinite(value) and day<=dt.date.today(): points[day]=value
        except (ValueError,TypeError): continue
    return {**pack_direct(d,points,"New York Fed direct",url),"releaseVintage":vintage}
def gscpi_workbook(d):
    import openpyxl
    url="https://www.newyorkfed.org/medialibrary/research/interactives/gscpi/downloads/gscpi_data.xlsx"
    with urllib.request.urlopen(urllib.request.Request(url,headers={"User-Agent":"Global Threshold economic research"}),timeout=35) as r:
        raw=r.read(10000001)
    if len(raw)>10000000: raise ValueError("GSCPI workbook too large")
    return pack_direct(d,parse_gscpi_workbook(raw),"New York Fed direct workbook",url)
def parse_gscpi_workbook(raw):
    import openpyxl,xlrd
    sheets=[]
    if raw.startswith(bytes.fromhex("d0cf11e0a1b11ae1")):
        book=xlrd.open_workbook(file_contents=raw)
        for sheet in book.sheets():
            rows=[]
            for i in range(sheet.nrows):
                rows.append([xlrd.xldate_as_datetime(c.value,book.datemode) if c.ctype==xlrd.XL_CELL_DATE else c.value for c in sheet.row(i)])
            sheets.append((sheet.name,rows))
    elif raw.startswith(b"PK"):
        book=openpyxl.load_workbook(io.BytesIO(raw),read_only=True,data_only=True)
        try: sheets=[(s.title,list(s.iter_rows(values_only=True))) for s in book.worksheets]
        finally: book.close()
    else: raise ValueError("Unrecognized GSCPI workbook format")
    for name,rows in sheets:
        points={}; columns=None
        for row in rows:
            if columns is None:
                labels=[str(v or "").strip().lower() for v in row]
                dates=[i for i,v in enumerate(labels) if v in ("date","month","observation date")]
                vals=[i for i,v in enumerate(labels) if v in ("gscpi","global supply chain pressure index")]
                if len(dates)==1 and len(vals)==1: columns=(dates[0],vals[0])
                continue
            di,vi=columns
            if len(row)<=max(di,vi): continue
            day=None; value=row[di]
            if isinstance(value,dt.datetime): day=value.date()
            elif isinstance(value,dt.date): day=value
            else:
                for fmt in ("%Y-%m-%d","%b-%y","%b %Y","%d-%b-%Y","%m/%d/%Y","%Y-%m","%m/%Y"):
                    try: day=dt.datetime.strptime(str(value).strip(),fmt).date();break
                    except ValueError: pass
            try:
                val=float(row[vi])
                if day and 1997<=day.year<=dt.date.today().year and day<=dt.date.today() and math.isfinite(val): points[day.replace(day=1)]=val
            except (ValueError,TypeError): continue
        if len(points)>=12: return points
    raise ValueError("GSCPI workbook has no recognized Date/GSCPI series")
def direct_gscpi(d):
    try: return gscpi_workbook(d)
    except Exception as e: print("GSCPI workbook",type(e).__name__,str(e),flush=True)
    return gscpi_csv(d)
def nfci_text(d):
    # Official FRED tabular export, independent of the failed graph CSV endpoint.
    import re
    url="https://fred.stlouisfed.org/data/NFCI.txt"
    with urllib.request.urlopen(urllib.request.Request(url,headers={"User-Agent":"Global Threshold economic research"}),timeout=30) as r:
        raw=r.read(2000001)
    if len(raw)>2000000: raise ValueError("Index text too large")
    body=raw.decode("utf-8-sig")
    if not re.search(r"(?m)^\s*DATE\s+VALUE\s*$",body): raise ValueError("Unexpected NFCI text header")
    points={}
    for line in body.splitlines():
        match=re.fullmatch(r"\s*(\d{4}-\d{2}-\d{2})\s+(-?\d+(?:\.\d+)?)\s*",line)
        if not match: continue
        day=dt.date.fromisoformat(match[1]);value=float(match[2])
        if day<=dt.date.today() and math.isfinite(value): points[day]=value
    return pack_direct(d,points,"Chicago Fed via FRED table",url)
def nfci_publisher(d):
    # Discover the publisher's own CSV link rather than assume a filename.
    from html.parser import HTMLParser
    from urllib.parse import urljoin,urlparse
    class Links(HTMLParser):
        def __init__(self): super().__init__(); self.links=[]
        def handle_starttag(self,tag,attrs):
            if tag=="a": self.links.extend(v for k,v in attrs if k=="href" and v)
    page="https://www.chicagofed.org/research/data/nfci/current-data-aws"
    with urllib.request.urlopen(urllib.request.Request(page,headers={"User-Agent":"Global Threshold economic research"}),timeout=25) as r:
        raw=r.read(4000001)
    if len(raw)>4000000: raise ValueError("Publisher page too large")
    links=Links();links.feed(raw.decode("utf-8",errors="replace"))
    candidates=[]
    for link in links.links:
        url=urljoin(page,link);u=urlparse(url)
        if u.scheme=="https" and u.hostname in ("www.chicagofed.org","chicagofed.org") and ".csv" in u.path.lower() and "nfci" in u.path.lower(): candidates.append(url)
    print("NFCI publisher candidate count",len(candidates),flush=True)
    for url in list(dict.fromkeys(candidates))[:4]:
        try:
            with urllib.request.urlopen(urllib.request.Request(url,headers={"User-Agent":"Global Threshold economic research"}),timeout=25) as r: raw=r.read(5000001)
            if len(raw)>5000000: raise ValueError("NFCI file too large")
            reader=csv.reader(io.StringIO(raw.decode("utf-8-sig")))
            head=next(reader); cols=[x.strip().lower() for x in head]
            if "nfci" not in cols: continue
            ci=cols.index("nfci"); di=next(i for i,c in enumerate(cols) if c in ("date","week","week ending","observation_date"))
            points={}
            for row in reader:
                if len(row)<=max(ci,di): continue
                day=None
                for fmt in ("%Y-%m-%d","%m/%d/%Y","%m/%d/%y"):
                    try: day=dt.datetime.strptime(row[di].strip(),fmt).date();break
                    except ValueError: pass
                try:
                    val=float(row[ci])
                    if day and day<=dt.date.today() and math.isfinite(val): points[day]=val
                except ValueError: continue
            return pack_direct(d,points,"Chicago Fed direct",url)
        except Exception as e: print("NFCI publisher file",type(e).__name__,str(e),flush=True)
    raise ValueError("No usable publisher CSV link")
def nfci_api(d):
    import os
    from urllib.parse import urlencode
    key=os.environ.get("FRED_API_KEY","").strip()
    if not key: raise ValueError("FRED_API_KEY not configured")
    endpoint="https://api.stlouisfed.org/fred/series/observations"
    query=urlencode({"series_id":"NFCI","api_key":key,"file_type":"json","sort_order":"desc","limit":530})
    try:
        with urllib.request.urlopen(urllib.request.Request(endpoint+"?"+query,headers={"User-Agent":"Global Threshold public research"}),timeout=25) as r:
            raw=r.read(1000001)
        if len(raw)>1000000: raise ValueError("FRED response too large")
        payload=json.loads(raw)
        points={}
        for row in payload["observations"]:
            try:
                day=dt.date.fromisoformat(row["date"]);val=float(row["value"])
                if day<=dt.date.today() and math.isfinite(val): points[day]=val
            except (ValueError,TypeError): continue
        if len(points)<2: raise ValueError("Insufficient observations")
        return pack_direct(d,points,"Chicago Fed via official FRED API","https://fred.stlouisfed.org/series/NFCI")
    except Exception as e:
        # Never include request URL or credentials in logs.
        print("NFCI API",type(e).__name__,getattr(e,"code",None),flush=True)
        raise ValueError("FRED API retrieval failed") from None
def direct_nfci(d):
    import os
    if os.environ.get("FRED_API_KEY","").strip():
        try: return nfci_api(d)
        except Exception: print("NFCI API unavailable; trying public endpoints",flush=True)
    try: return nfci_publisher(d)
    except Exception as e: print("NFCI publisher",type(e).__name__,str(e),flush=True)
    return nfci_text(d)
def collect(d):
    direct_error=None
    try:
        if d["id"]=="GSCPI": return direct_gscpi(d)
        if d["id"]=="NFCI": return direct_nfci(d)
        if d["id"] in ("CPIAUCNS","UNRATE"): return bls_fallback(d)
        if d["id"] in ("DFF","DGS10","DGS2","DGS3MO"): return direct_rates(d)
        if d["id"]=="A191RL1Q225SBEA": return direct_gdp(d)
        if d["id"]=="DCOILWTICO" or d.get("workbook"): return direct_oil(d)
    except Exception as e:
        print(d["id"],"Direct",type(e).__name__,str(e),flush=True)
        direct_error={"type":type(e).__name__,"httpStatus":getattr(e,"code",None)}
    if d["id"] in ("WCESTUS1","WCRFPUS2","GSCPI"): return {**d,"status":"retrieval_failed","directError":direct_error}
    try: return retrieve(d)
    except Exception as e:
        print(d["id"],"FRED",type(e).__name__,str(e),flush=True)
        if d["id"] in ("CPIAUCNS","UNRATE"):
            try: return bls_fallback(d)
            except Exception as fallback: print(d["id"],"BLS",type(fallback).__name__,str(fallback),flush=True)
        return {**d,"status":"retrieval_failed"}
def enrich_history(row):
    # Keep direct-source latest/prior unchanged; use official FRED only for older history.
    import os
    from urllib.parse import urlencode
    ids={"CPIAUCNS","UNRATE","DFF","DGS10","DGS2","DGS3MO"}
    if row["id"] not in ids or row.get("status")!="available": return row
    key=os.environ.get("FRED_API_KEY","").strip()
    if not key: return row
    try:
        start=(dt.date.today()-dt.timedelta(days=4030 if row["id"]=="CPIAUCNS" else 3660)).isoformat()
        query=urlencode({"series_id":row["id"],"api_key":key,"file_type":"json","observation_start":start,"sort_order":"asc","limit":10000})
        with urllib.request.urlopen("https://api.stlouisfed.org/fred/series/observations?"+query,timeout=25) as r: raw=r.read(3000001)
        if len(raw)>3000000: raise ValueError("FRED history too large")
        points={}
        for item in json.loads(raw)["observations"]:
            try:
                day=dt.date.fromisoformat(item["date"]); value=float(item["value"])
                if day<=dt.date.today() and math.isfinite(value): points[day]=value
            except (ValueError,TypeError,KeyError): continue
        if row["id"]=="CPIAUCNS":
            points={day:(value/points[day.replace(year=day.year-1)]-1)*100 for day,value in points.items() if day.day==1 and day.replace(year=day.year-1) in points and points[day.replace(year=day.year-1)]>0}
        cutoff=dt.date.fromisoformat(row["latest"]["date"])
        existing={x["date"]:x for x in row.get("history",[])}
        older=retained_points(sorted(((d,v) for d,v in points.items() if d<cutoff),reverse=True))
        for x in older:
            existing.setdefault(x["date"],{**x,"source":"FRED historical API"})
        row["history"]=sorted(existing.values(),key=lambda x:x["date"])[-4000:]
        print(row["id"],"history",len(row["history"]),flush=True)
    except Exception as e:
        print(row["id"],"history unavailable",type(e).__name__,getattr(e,"code",None),flush=True)
    return row
def main():
    old={}
    if OUT.exists():
        try: old={x["id"]:x for x in json.loads(OUT.read_text())["rows"]}
        except (ValueError,KeyError,TypeError): pass
    with ThreadPoolExecutor(max_workers=3) as pool:
        rows=list(pool.map(collect,DEFS))
        rows=list(pool.map(enrich_history,rows))
    rows=[{**r,**old.get(r["id"],{}),"status":"retrieval_failed"} if r["status"]=="retrieval_failed" else r for r in rows]
    print("Successful series:",sum(r["status"]=="available" for r in rows),"/",len(rows),flush=True)
    for r in rows:
        history={x["date"]:x for x in old.get(r["id"],{}).get("history",[]) if isinstance(x,dict) and "date" in x and "value" in x}
        if r["status"]=="available":
            for x in [*r.get("history",[]),r.get("prior"),r.get("latest")]:
                if x: history[x["date"]]=x
        r["history"]=sorted(history.values(),key=lambda x:x["date"])[-4000:]
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps({"generatedAt":dt.datetime.now(dt.timezone.utc).isoformat(),"rows":rows},indent=2)+"\n")
if __name__=="__main__": main()
