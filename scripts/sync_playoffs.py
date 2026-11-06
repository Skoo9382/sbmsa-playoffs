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
# The official playoff grid uses a six-column table. Team cells contain
# separate left/right <p> elements for name and score, not score headers.
grid=soup.select_one('table[id$="PlayoffGrid_ctl00"]')
if grid is None:
    raise RuntimeError("Official playoff schedule grid not found")
for tr in grid.select("tr"):
    cells=tr.find_all("td",recursive=False)
    if len(cells)!=6: continue
    labels=[c.get_text(" ",strip=True) for c in cells]
    match=re.fullmatch(r"G(1[01]|[1-9])",labels[2],re.I)
    if not match: continue
    num=int(match.group(1))
    if num in updates: raise RuntimeError(f"Duplicate official game G{num}")
    if not re.fullmatch(r"(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s+\d{1,2}/\d{1,2}",labels[0]): continue
    if not re.fullmatch(r"\d{1,2}:\d{2}\s*[AP]M",labels[1],re.I): continue
    if "Field" not in labels[5]: continue
    def team_and_score(cell):
        pieces=[p.get_text(" ",strip=True) for p in cell.find_all("p",recursive=False)]
        if pieces:
            name=pieces[0]
            score=int(pieces[1]) if len(pieces)>1 and re.fullmatch(r"\d{1,2}",pieces[1]) else None
            return name,score
        return cell.get_text(" ",strip=True),None
    home,hs=team_and_score(cells[3])
    away,aw=team_and_score(cells[4])
    expected=known[num]
    # Later rounds can show resolved winners instead of placeholders.
    def expected_name(label):
        m=re.fullmatch(r"G(\d+) Winner",label)
        return updates.get(m.group(1),{}).get("winner") or existing["games"].get(m.group(1),{}).get("winner") or label if m else label
    if home!=expected_name(expected[0]) or away!=expected_name(expected[1]):
        raise RuntimeError(f"Unexpected participants in G{num}: {home} vs {away}")
    item={"date":labels[0],"time":labels[1],"field":labels[5]}
    if hs is not None and aw is not None:
        item["score"]=[hs,aw]
        if hs!=aw:
            item["winner"]=home if hs>aw else away
        # A shootout can produce a final non-tied result, but the official
        # site must be checked if tied scores are displayed.
    updates[str(num)]=item
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
