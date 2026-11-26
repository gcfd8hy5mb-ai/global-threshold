import gzip, io, urllib.error, re, time, datetime as dt, email.utils, json, pathlib, urllib.request, urllib.parse, xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
SOURCES=[
 ("geo-africa","UN News · Africa","https://news.un.org/feed/subscribe/en/news/region/africa/feed/rss.xml",("news.un.org",)),
 ("geo-asia","UN News · Asia-Pacific","https://news.un.org/feed/subscribe/en/news/region/asia-pacific/feed/rss.xml",("news.un.org",)),
 ("geo-europe","UN News · Europe","https://news.un.org/feed/subscribe/en/news/region/europe/feed/rss.xml",("news.un.org",)),
 ("geo-middle-east","UN News · Middle East","https://news.un.org/feed/subscribe/en/news/region/middle-east/feed/rss.xml",("news.un.org",)),
 ("geo-americas","UN News · Americas","https://news.un.org/feed/subscribe/en/news/region/americas/feed/rss.xml",("news.un.org",)),
 ("geo-humanitarian","UN News · Humanitarian aid","https://news.un.org/feed/subscribe/en/news/topic/humanitarian-aid/feed/rss.xml",("news.un.org",)),
 ("geopolitics","UN News","https://news.un.org/feed/subscribe/en/news/topic/peace-and-security/feed/rss.xml",("news.un.org",)),
 ("government","DOJ National Security Division","https://www.justice.gov/news/rss?field_component=361&field_topic%5B0%5D=25321&field_topic%5B1%5D=44971&field_topic%5B2%5D=44956&field_topic%5B3%5D=7881&field_topic%5B4%5D=44951&field_topic%5B5%5D=45186&require_all=0&search_api_language=en&show_public_archived=0&type%5B0%5D=press_release&type%5B1%5D=speech&type%5B2%5D=youtube_video",("justice.gov","www.justice.gov")),
 ("trade","WTO news","https://www.wto.org/library/rss/latest_news_e.xml",("wto.org","www.wto.org"))]
# Retry the documented feed, never substitute unrelated regional coverage.
def collect(spec):
    attempts=[]
    for attempt in range(2):
        result=collect_endpoint(spec)
        attempts.append({"url":spec[2],"status":result["status"],"error":result.get("error")})
        if result["status"]=="available": break
        if result.get("error",{}).get("httpStatus") in (403,429): break
        if attempt==0: time.sleep(2)
    result["attempts"]=attempts
    return result
def decode_transport(raw, encoding=""):
    # Some CDN responses are gzip-compressed even without a correct header.
    if raw.startswith(b"\x1f\x8b"):
        with gzip.GzipFile(fileobj=io.BytesIO(raw)) as stream:
            raw=stream.read(3000001)
        if len(raw)>3000000: raise ValueError("Decompressed feed too large")
        return raw,"gzip"
    if encoding.lower().strip() not in ("","identity","gzip"):
        raise ValueError("Unsupported content encoding")
    return raw,"identity"
def parse_feed(raw):
    try:
        return ET.fromstring(raw), False
    except ET.ParseError:
        # Narrow repair: illegal XML 1.0 control characters and bare ampersands.
        # Do not interpret HTML error pages as successful feeds.
        text=raw.decode("utf-8-sig")
        if not re.search(r"<rss(?:\s|>)",text[:4096],re.I): raise ValueError("Not an RSS document")
        text=re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]","",text)
        text=re.sub(r"&(?!amp;|lt;|gt;|apos;|quot;|#\d+;|#x[0-9a-fA-F]+;)","&amp;",text)
        return ET.fromstring(text), True
def collect_endpoint(spec):
    key,source,url,hosts=spec
    result={"id":key,"source":source,"feed":url,"status":"retrieval_failed","items":[]}
    try:
        with urllib.request.urlopen(urllib.request.Request(url,headers={"User-Agent":"Global Threshold public news reader/1.0","Accept-Encoding":"identity","Accept":"application/rss+xml, application/xml, text/xml;q=0.9"}),timeout=25) as r:
            raw=r.read(3000001)
            encoding=r.headers.get("Content-Encoding","")
            result["transport"]={"contentType":r.headers.get("Content-Type",""),"contentEncoding":encoding,"bytes":len(raw),"signature":raw[:4].hex()}
        if len(raw)>3000000: raise ValueError("Feed too large")
        raw,transport=decode_transport(raw,encoding)
        result["transport"]["decodedAs"]=transport
        root,repaired=parse_feed(raw)
        result["xmlRepaired"]=repaired
        channel=root.find("channel")
        if root.tag!="rss" or channel is None: raise ValueError("Unexpected RSS format")
        seen=set()
        titles=set()
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
            title_key=(title.casefold(),date.date().isoformat())
            if link in seen or title_key in titles: continue
            seen.add(link)
            titles.add(title_key)
            result["items"].append({"title":title[:300],"url":link,"publishedAt":date.isoformat()})
        result["items"]=sorted(result["items"],key=lambda x:x["publishedAt"],reverse=True)[:12]
        result["status"]="available"
    except Exception as e:
        result["error"]={"type":type(e).__name__,"httpStatus":getattr(e,"code",None) if isinstance(e,urllib.error.HTTPError) else None}
        print(key,type(e).__name__,getattr(e,"code",None),flush=True)
    return result
def main():
    with ThreadPoolExecutor(max_workers=3) as pool: sources=list(pool.map(collect,SOURCES))
    path=pathlib.Path("data/public-news.json")
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps({"generatedAt":dt.datetime.now(dt.timezone.utc).isoformat(),"sources":sources},indent=2)+"\n")
    print([(s["id"],s["status"],len(s["items"])) for s in sources])
    return 0 if any(s["status"]=="available" for s in sources) else 1
if __name__=="__main__": raise SystemExit(main())
