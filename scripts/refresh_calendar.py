import datetime as dt, json, pathlib, urllib.request
from icalendar import Calendar
from zoneinfo import ZoneInfo
URL="https://www.bls.gov/schedule/news_release/bls.ics"
def parse(raw, now):
    calendar=Calendar.from_ical(raw)
    result={}
    for event in calendar.walk("VEVENT"):
        if str(event.get("STATUS","")).upper()=="CANCELLED": continue
        title=str(event.get("SUMMARY","")).strip()
        if not title or "DTSTART" not in event: continue
        start=event.decoded("DTSTART")
        if not isinstance(start,dt.datetime): continue
        if start.tzinfo is None: start=start.replace(tzinfo=ZoneInfo("America/New_York"))
        start=start.astimezone(dt.timezone.utc)
        if not now<=start<=now+dt.timedelta(days=60): continue
        result[(title.casefold(),start.isoformat())]={"title":title[:240],"start":start.isoformat()}
    return sorted(result.values(),key=lambda x:x["start"])[:100]
def main():
    now=dt.datetime.now(dt.timezone.utc)
    data={"generatedAt":now.isoformat(),"status":"retrieval_failed","source":URL,"events":[]}
    try:
        with urllib.request.urlopen(urllib.request.Request(URL,headers={"User-Agent":"Mozilla/5.0 Global Threshold calendar reader"}),timeout=30) as r: raw=r.read(5000001)
        if len(raw)>5000000: raise ValueError("Calendar too large")
        data["events"]=parse(raw,now)
        data["status"]="available"
    except Exception as e: print(type(e).__name__,str(e))
    p=pathlib.Path("data/calendar.json")
    p.parent.mkdir(exist_ok=True)
    p.write_text(json.dumps(data,indent=2)+"\n")
    print(data["status"],len(data["events"]))
    return int(data["status"]!="available")
if __name__=="__main__": raise SystemExit(main())
