import datetime as dt, json, pathlib, re, time, urllib.request
OUT=pathlib.Path("data/sec-cyber.json")
STATES=set("AL AK AZ AR CA CO CT DE DC FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY".split())
def get(url):
    # Respect SEC fair-access limits. Identify the public project.
    time.sleep(.25)
    req=urllib.request.Request(url,headers={"User-Agent":"Global Threshold public research https://github.com/gcfd8hy5mb-ai/global-threshold","Accept":"application/json"})
    with urllib.request.urlopen(req,timeout=20) as r:
        raw=r.read(12000001)
    if len(raw)>12000000: raise ValueError("SEC response too large")
    return json.loads(raw)
def main():
    today=dt.date.today()
    start=today-dt.timedelta(days=30)
    items=[]
    status="retrieval_failed"
    skipped=0
    examined=0
    try:
        from urllib.parse import urlencode
        url="https://efts.sec.gov/LATEST/search-index?"+urlencode({"q":'"Item 1.05"',"dateRange":"custom","startdt":start.isoformat(),"enddt":today.isoformat(),"forms":"8-K,8-K/A"})
        hits=get(url)["hits"]["hits"]
        seen=set()
        cache={}
        for hit in hits[:40]:
            src=hit.get("_source",{})
            accession=src.get("adsh","")
            if not re.fullmatch(r"\d{10}-\d{2}-\d{6}",accession) or accession in seen: continue
            seen.add(accession)
            ciks=src.get("ciks",[])
            if len(ciks)!=1 or not str(ciks[0]).isdigit(): continue
            cik=str(ciks[0]).zfill(10)
            try:
                if cik not in cache: cache[cik]=get("https://data.sec.gov/submissions/CIK"+cik+".json")
                company=cache[cik]
                recent=company["filings"]["recent"]
                i=recent["accessionNumber"].index(accession)
                form=recent["form"][i]
                filed=recent["filingDate"][i]
                codes=re.split(r"[,;\s]+",recent["items"][i] or "")
                examined+=1
                if form not in ("8-K","8-K/A") or "1.05" not in codes: continue
                if company.get("stateOfIncorporation") not in STATES: continue
                if not start<=dt.date.fromisoformat(filed)<=today: continue
                items.append({"name":company["name"],"date":filed,"form":form,"accession":accession,"url":"https://www.sec.gov/Archives/edgar/data/"+str(int(cik))+"/"+accession.replace("-","")+"/"+accession+"-index.htm"})
            except Exception as e:
                skipped+=1
                print("Candidate verification failed",type(e).__name__,flush=True)
        status="partial" if skipped or len(hits)>=40 else "available"
    except Exception as e: print(type(e).__name__,str(e),flush=True)
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps({"generatedAt":dt.datetime.now(dt.timezone.utc).isoformat(),"status":status,"examined":examined,"skipped":skipped,"items":sorted(items,key=lambda x:x["date"],reverse=True)},indent=2)+"\n")
    return int(status=="retrieval_failed")
if __name__=="__main__": raise SystemExit(main())
