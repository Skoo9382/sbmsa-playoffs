"""Safely sync SBMSA playoff fixtures; never infer winners from ambiguous page text."""
import json, pathlib, re, urllib.request, datetime
from bs4 import BeautifulSoup
ROOT=pathlib.Path(__file__).resolve().parents[1]
URL="https://sbmsa.net/schedule/710227/6u-boys-silver-playoffs"
DEST=ROOT/"data"/"playoffs.json"
req=urllib.request.Request(URL,headers={"User-Agent":"Mozilla/5.0 (compatible; community-playoff-viewer/1.0)"})
with urllib.request.urlopen(req,timeout=35) as response:
    html=response.read().decode("utf-8","replace")
if len(html)<1000 or "Silver Playoffs" not in html:
    raise RuntimeError("Unexpected source; no updates published")
soup=BeautifulSoup(html,"html.parser")
known={1:("Rams","BHE Lions"),2:("Regis Knights","Seattle Sounders FC"),3:("Tigers","Space City Strikers"),4:("Green Machine","Holland Hooligans"),5:("USA Screaming Eagles","G1 Winner"),6:("Kinkaid Falcons","G2 Winner"),7:("Brazil","G3 Winner"),8:("Argentina FC","G4 Winner"),9:("G5 Winner","G6 Winner"),10:("G7 Winner","G8 Winner"),11:("G9 Winner","G10 Winner")}
existing=json.loads(DEST.read_text()) if DEST.exists() else {"games":{}}
updates={}
# Require an identifiable row and both expected participants; never accept dates or field numbers as scores.
for tr in soup.select("tr"):
    cells=[" ".join(x.stripped_strings) for x in tr.find_all(["td","th"],recursive=False)]
    if len(cells)<5: continue
    hits=[(i,int(m.group(1))) for i,c in enumerate(cells) if (m:=re.fullmatch(r"G(1[01]|[1-9])",c,re.I))]
    if len(hits)!=1: continue
    pos,num=hits[0]
    a,b=known[num]
    row=" | ".join(cells)
    if a.lower() not in row.lower() or b.lower() not in row.lower(): continue
    # Only read scores if the table explicitly labels score columns. No guessing.
    headers=[x.get_text(" ",strip=True).lower() for x in tr.find_parent("table").select("thead th")]
    scores=None
    if len(headers)==len(cells):
        home_idx=next((i for i,x in enumerate(headers) if x in ("home score","home goals")),None)
        away_idx=next((i for i,x in enumerate(headers) if x in ("away score","away goals")),None)
        if home_idx is not None and away_idx is not None:
            sh,sa=cells[home_idx],cells[away_idx]
            if re.fullmatch(r"\d{1,2}",sh) and re.fullmatch(r"\d{1,2}",sa):
                scores=[int(sh),int(sa)]
    # Capture explicit date/time and field only from table cells, no fabricated replacements.
    date=next((c for c in cells if re.search(r"\b(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s+\d{1,2}/\d{1,2}\b",c)),None)
    time=next((c for c in cells if re.fullmatch(r"\d{1,2}:\d{2}\s*[AP]M",c,re.I)),None)
    field=next((c for c in cells if "Field" in c),None)
    item={}
    if date:item["date"]=date
    if time:item["time"]=time
    if field:item["field"]=field
    if scores is not None:
        item["score"]=scores
        if scores[0]!=scores[1]: item["winner"]=a if scores[0]>scores[1] else b
    if item: updates[str(num)]=item
if len(updates)<8:
    raise RuntimeError(f"Only {len(updates)} matching fixtures parsed; preserving previous published data")
# Avoid overwriting existing confirmed results with blanks.
for key,patch in updates.items():
    old=existing["games"].get(key,{})
    existing["games"][key]={**old,**patch}
existing["checked_at"]=datetime.datetime.now(datetime.timezone.utc).isoformat()
existing["source"]=URL
DEST.parent.mkdir(parents=True,exist_ok=True)
DEST.write_text(json.dumps(existing,indent=2,ensure_ascii=False)+"\n")
print(f"Synced {len(updates)} verified fixtures, {sum('score' in x for x in updates.values())} scored")
