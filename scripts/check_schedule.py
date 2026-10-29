"""Detect changes to the public SBMSA schedule without publishing unverified results."""
import hashlib, json, pathlib, urllib.request, os
from html.parser import HTMLParser
URL='https://sbmsa.net/schedule/710227/6u-boys-silver-playoffs'
ROOT=pathlib.Path(__file__).resolve().parents[1]
req=urllib.request.Request(URL,headers={'User-Agent':'Mozilla/5.0 (SBMSA fan schedule checker)'})
with urllib.request.urlopen(req,timeout=30) as response:
    html=response.read().decode('utf-8','replace')
if len(html)<1000 or 'silver' not in html.lower():
    raise RuntimeError('Unexpected SBMSA response; preserving existing schedule')
class Text(HTMLParser):
    def __init__(self): super().__init__(); self.skip=0; self.parts=[]
    def handle_starttag(self,tag,attrs):
        if tag in ('script','style'): self.skip+=1
    def handle_endtag(self,tag):
        if tag in ('script','style'): self.skip=max(0,self.skip-1)
    def handle_data(self,data):
        if not self.skip: self.parts.append(data)
p=Text();p.feed(html)
digest=hashlib.sha256(' '.join(' '.join(p.parts).split()).encode()).hexdigest()
path=ROOT/'data/source-monitor.json'
old=json.loads(path.read_text()) if path.exists() else {}
changed=bool(old.get('digest') and old['digest']!=digest)
path.parent.mkdir(parents=True,exist_ok=True)
path.write_text(json.dumps({'digest':digest,'source':URL},indent=2)+'\n')
if changed:
    with open(os.environ.get('GITHUB_OUTPUT','/tmp/sbmsa-output'),'a') as out:out.write('changed=true\n')
print('Change detected' if changed else 'No changes or first baseline')
