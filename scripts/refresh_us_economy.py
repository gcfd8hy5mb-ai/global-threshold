from concurrent.futures import ThreadPoolExecutor
import csv, json, io, datetime as dt, urllib.request, math, pathlib, time
DEFS = json.loads("[{\"id\":\"CPIAUCNS\",\"label\":\"Inflation (CPI YoY)\",\"frequency\":\"Monthly\",\"unit\":\"%\",\"maxAge\":75,\"source\":\"BLS via FRED\",\"transform\":\"yoy\"},{\"id\":\"UNRATE\",\"label\":\"Unemployment rate\",\"frequency\":\"Monthly\",\"unit\":\"%\",\"maxAge\":75,\"source\":\"BLS via FRED\"},{\"id\":\"A191RL1Q225SBEA\",\"label\":\"Real GDP growth (annualized)\",\"frequency\":\"Quarterly\",\"unit\":\"%\",\"maxAge\":180,\"source\":\"BEA via FRED\"},{\"id\":\"DFF\",\"label\":\"Effective federal funds rate\",\"frequency\":\"Daily\",\"unit\":\"%\",\"maxAge\":10,\"source\":\"Federal Reserve via FRED\"},{\"id\":\"DGS10\",\"label\":\"10-year Treasury yield\",\"frequency\":\"Daily\",\"unit\":\"%\",\"maxAge\":10,\"source\":\"Federal Reserve via FRED\"},{\"id\":\"DCOILWTICO\",\"label\":\"WTI crude oil\",\"frequency\":\"Daily\",\"unit\":\"$/bbl\",\"maxAge\":14,\"source\":\"EIA via FRED\"}]")
OUT = pathlib.Path("data/us-economy.json")
def retrieve(d):
    start = (dt.date.today()-dt.timedelta(days=800)).isoformat()
    url = "https://fred.stlouisfed.org/graph/fredgraph.csv?id="+d["id"]+"&cosd="+start
    req = urllib.request.Request(url, headers={"User-Agent":"Global Threshold public economic research/1.0"})
    with urllib.request.urlopen(req,timeout=18) as r:
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
        value=float(x["value"])
        if math.isfinite(value) and day<=dt.date.today(): points[day]=value
    if d.get("transform")=="yoy":
        points={day:(value/points[day.replace(year=day.year-1)]-1)*100 for day,value in points.items() if day.replace(year=day.year-1) in points and points[day.replace(year=day.year-1)]>0}
    ordered=sorted(points.items(),reverse=True)
    if not ordered: raise ValueError("No BLS observations")
    def item(pair): return {"date":pair[0].isoformat(),"value":round(pair[1],4)}
    return {**d,"source":"BLS direct","latest":item(ordered[0]),"prior":item(ordered[1]) if len(ordered)>1 else None,"retrievedAt":dt.datetime.now(dt.timezone.utc).isoformat(),"status":"available"}
def collect(d):
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
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps({"generatedAt":dt.datetime.now(dt.timezone.utc).isoformat(),"rows":rows},indent=2)+"\n")
if __name__=="__main__": main()
