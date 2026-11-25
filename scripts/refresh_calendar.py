import datetime as dt, json, pathlib, urllib.request, urllib.error
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
def fred_calendar(now):
    import os
    from urllib.parse import urlencode
    key=os.environ.get("FRED_API_KEY","").strip()
    if not key: raise ValueError("FRED API key unavailable")
    today=now.astimezone(ZoneInfo("America/New_York")).date()
    query=urlencode({"api_key":key,"file_type":"json","realtime_start":today.isoformat(),"realtime_end":(today+dt.timedelta(days=60)).isoformat(),"include_release_dates_with_no_data":"true","sort_order":"asc","limit":1000})
    try:
        with urllib.request.urlopen("https://api.stlouisfed.org/fred/releases/dates?"+query,timeout=25) as r: raw=r.read(2000001)
        if len(raw)>2000000: raise ValueError("FRED calendar too large")
        payload=json.loads(raw)
        events={}
        allowed={10,50,53,54,46,21,18,9,101,11,13}
        for row in payload["release_dates"]:
            rid=int(row["release_id"])
            if rid not in allowed: continue
            day=dt.date.fromisoformat(row["date"])
            if today<=day<=today+dt.timedelta(days=60):
                title=str(row["release_name"]).strip()
                if title: events[(day,rid)]={"title":title[:240],"date":day.isoformat(),"releaseId":rid}
        if not events: raise ValueError("No selected future release dates returned")
        return sorted(events.values(),key=lambda x:(x["date"],x["title"]))
    except Exception as e:
        print("FRED calendar",type(e).__name__,getattr(e,"code",None),flush=True)
        raise ValueError("FRED calendar retrieval failed") from None
def main():
    now=dt.datetime.now(dt.timezone.utc)
    data={"generatedAt":now.isoformat(),"status":"retrieval_failed","source":URL,"events":[]}
    try:
        with urllib.request.urlopen(urllib.request.Request(URL,headers={"User-Agent":"Mozilla/5.0 Global Threshold calendar reader"}),timeout=30) as r: raw=r.read(5000001)
        if len(raw)>5000000: raise ValueError("Calendar too large")
        data["events"]=parse(raw,now)
        data["status"]="available"
    except Exception as e:
        data["error"]={"type":type(e).__name__,"httpStatus":getattr(e,"code",None) if isinstance(e,urllib.error.HTTPError) else None}
        print(type(e).__name__,str(e))
    if data["status"]!="available":
        try:
            data["events"]=fred_calendar(now)
            data["source"]="https://fred.stlouisfed.org/releases/calendar"
            data["status"]="available"
            data["precision"]="date"
            data["primaryError"]=data.pop("error",None)
        except Exception as e: print(type(e).__name__,str(e),flush=True)
    else: data["precision"]="time"
    p=pathlib.Path("data/calendar.json")
    p.parent.mkdir(exist_ok=True)
    p.write_text(json.dumps(data,indent=2)+"\n")
    print(data["status"],len(data["events"]))
    return int(data["status"]!="available")
if __name__=="__main__": raise SystemExit(main())
