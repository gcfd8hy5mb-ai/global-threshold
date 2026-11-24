import csv, json, io, datetime as dt, urllib.request, math, pathlib, time
DEFS = json.loads("[{\"id\":\"CPIAUCNS\",\"label\":\"Inflation (CPI YoY)\",\"frequency\":\"Monthly\",\"unit\":\"%\",\"maxAge\":75,\"source\":\"BLS via FRED\",\"transform\":\"yoy\"},{\"id\":\"UNRATE\",\"label\":\"Unemployment rate\",\"frequency\":\"Monthly\",\"unit\":\"%\",\"maxAge\":75,\"source\":\"BLS via FRED\"},{\"id\":\"A191RL1Q225SBEA\",\"label\":\"Real GDP growth (annualized)\",\"frequency\":\"Quarterly\",\"unit\":\"%\",\"maxAge\":180,\"source\":\"BEA via FRED\"},{\"id\":\"DFF\",\"label\":\"Effective federal funds rate\",\"frequency\":\"Daily\",\"unit\":\"%\",\"maxAge\":10,\"source\":\"Federal Reserve via FRED\"},{\"id\":\"DGS10\",\"label\":\"10-year Treasury yield\",\"frequency\":\"Daily\",\"unit\":\"%\",\"maxAge\":10,\"source\":\"Federal Reserve via FRED\"},{\"id\":\"DCOILWTICO\",\"label\":\"WTI crude oil\",\"frequency\":\"Daily\",\"unit\":\"$/bbl\",\"maxAge\":14,\"source\":\"EIA via FRED\"}]")
OUT = pathlib.Path("data/us-economy.json")
def retrieve(d):
    start = (dt.date.today()-dt.timedelta(days=800)).isoformat()
    url = "https://fred.stlouisfed.org/graph/fredgraph.csv?id="+d["id"]+"&cosd="+start
    req = urllib.request.Request(url, headers={"User-Agent":"Global Threshold public economic research/1.0"})
    with urllib.request.urlopen(req,timeout=35) as r:
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
def main():
    old={}
    if OUT.exists():
        try: old={x["id"]:x for x in json.loads(OUT.read_text())["rows"]}
        except (ValueError,KeyError,TypeError): pass
    rows=[]
    for d in DEFS:
        try: rows.append(retrieve(d))
        except Exception as e:
            print(d["id"],type(e).__name__,str(e))
            rows.append({**d,**old.get(d["id"],{}),"status":"retrieval_failed"})
        time.sleep(1)
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps({"generatedAt":dt.datetime.now(dt.timezone.utc).isoformat(),"rows":rows},indent=2)+"\n")
if __name__=="__main__": main()
