import datetime as dt, email.utils, json, pathlib, urllib.request, urllib.parse, xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
SOURCES=[
 ("geopolitics","UN News","https://news.un.org/feed/subscribe/en/news/topic/peace-and-security/feed/rss.xml",("news.un.org",)),
 ("government","DOJ National Security Division","https://www.justice.gov/news/rss?field_component=361&field_topic%5B0%5D=25321&field_topic%5B1%5D=44971&field_topic%5B2%5D=44956&field_topic%5B3%5D=7881&field_topic%5B4%5D=44951&field_topic%5B5%5D=45186&require_all=0&search_api_language=en&show_public_archived=0&type%5B0%5D=press_release&type%5B1%5D=speech&type%5B2%5D=youtube_video",("justice.gov","www.justice.gov")),
 ("trade","WTO news","https://www.wto.org/library/rss/latest_news_e.xml",("wto.org","www.wto.org"))]
def collect(spec):
    key,source,url,hosts=spec
    result={"id":key,"source":source,"feed":url,"status":"retrieval_failed","items":[]}
    try:
        with urllib.request.urlopen(urllib.request.Request(url,headers={"User-Agent":"Global Threshold public news reader/1.0"}),timeout=25) as r: raw=r.read(3000001)
        if len(raw)>3000000: raise ValueError("Feed too large")
        root=ET.fromstring(raw)
        channel=root.find("channel")
        if channel is None: raise ValueError("Unexpected RSS format")
        seen=set()
        now=dt.datetime.now(dt.timezone.utc)
        for item in channel.findall("item"):
            title=" ".join((item.findtext("title") or "").split())
            link=(item.findtext("link") or "").strip()
            parsed=urllib.parse.urlparse(link)
            if parsed.scheme not in ("https","http") or parsed.hostname not in hosts or not title: continue
            try: date=email.utils.parsedate_to_datetime(item.findtext("pubDate") or "")
            except (ValueError,TypeError): continue
            if date.tzinfo is None: continue
            date=date.astimezone(dt.timezone.utc)
            if date>now+dt.timedelta(minutes=5) or date<now-dt.timedelta(days=30): continue
            if link in seen: continue
            seen.add(link)
            result["items"].append({"title":title[:300],"url":link,"publishedAt":date.isoformat()})
        result["items"]=sorted(result["items"],key=lambda x:x["publishedAt"],reverse=True)[:12]
        result["status"]="available"
    except Exception as e: print(key,type(e).__name__,str(e),flush=True)
    return result
def main():
    with ThreadPoolExecutor(max_workers=3) as pool: sources=list(pool.map(collect,SOURCES))
    path=pathlib.Path("data/public-news.json")
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps({"generatedAt":dt.datetime.now(dt.timezone.utc).isoformat(),"sources":sources},indent=2)+"\n")
    print([(s["id"],s["status"],len(s["items"])) for s in sources])
    return 0 if any(s["status"]=="available" for s in sources) else 1
if __name__=="__main__": raise SystemExit(main())
