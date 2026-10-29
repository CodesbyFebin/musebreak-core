#!/usr/bin/env python3
"""Build and check public documentation links, metadata, scope and text consistency."""
from html.parser import HTMLParser
from pathlib import Path
import json
import re
import tempfile
from urllib.parse import unquote,urlsplit
import xml.etree.ElementTree as ET
from build_docs import BASE,ROOT,PAGES,build,full_text

class Page(HTMLParser):
    def __init__(self,text):
        super().__init__();self.links=[];self.ids=set();self.meta={};self.canon=[];self.headings=0;self.jsonld=[];self.in_json=False;self.title=False;self.title_text='';self.feed(text)
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if 'id' in a:self.ids.add(a['id'])
        if tag=='h1':self.headings+=1
        if tag=='a' and 'href' in a:self.links.append(a['href'])
        if tag=='link' and a.get('rel')=='canonical':self.canon.append(a['href'])
        if tag=='link' and a.get('rel')=='stylesheet':self.links.append(a['href'])
        if tag=='meta':self.meta[a.get('name',a.get('property',''))]=a.get('content','')
        if tag=='script':self.in_json=a.get('type')=='application/ld+json'
        if tag=='title':self.title=True
    def handle_endtag(self,tag):
        if tag=='script':self.in_json=False
        if tag=='title':self.title=False
    def handle_data(self,data):
        if self.in_json:self.jsonld.append(json.loads(data))
        if self.title:self.title_text+=data

def main():
    count=len(re.findall(r"\b[\w'-]+\b",(ROOT/'README.md').read_text()))
    assert count>=5000, f'Expected requested 5000+ word guide; got {count}'
    assert (ROOT/'llms-full.txt').read_text()==full_text(),'Run build_docs.py --refresh-text after changing source'
    identity=json.loads((ROOT/'project.json').read_text());assert identity['name']=='MeTaBoss'
    with tempfile.TemporaryDirectory(prefix='metaboss-doc-check-') as d:
        out=build(Path(d)/'site');pages={name:Page((out/name).read_text()) for _,name,_,_ in PAGES}
        titles=set();descriptions=set();links=0
        for name,p in pages.items():
            assert p.headings==1,(name,'expected one main heading')
            assert p.title_text not in titles,(name,'duplicate title');titles.add(p.title_text)
            desc=p.meta['description'];assert desc and desc not in descriptions,(name,'duplicate description');descriptions.add(desc)
            assert p.canon==[BASE+('' if name=='index.html' else name)],(name,p.canon)
            assert p.meta['robots']=='index,follow'
            assert p.jsonld[0]['name']=='MeTaBoss' and p.jsonld[0]['@type']=='SoftwareSourceCode'
            assert not any(k in p.jsonld[0] for k in ['aggregateRating','review','offers'])
            for link in p.links:
                u=urlsplit(link)
                if u.scheme or u.netloc:continue
                target=unquote(u.path) or name
                assert (out/target).is_file(),(name,'missing link',link)
                if u.fragment:
                    assert target in pages and unquote(u.fragment) in pages[target].ids,(name,'missing anchor',link)
                links+=1
        locs=[e.text for e in ET.parse(out/'sitemap.xml').findall('{*}url/{*}loc')]
        assert set(locs)=={p.canon[0] for p in pages.values()}
        assert len(locs)==len(pages)
        allowed={dest for _,dest,_,_ in PAGES}|{'style.css','robots.txt','llms.txt','llms-full.txt','agents.txt','project.json','sitemap.xml','.nojekyll','404.html'}
        assert {p.name for p in out.iterdir()}==allowed,'Unexpected published artifact'
        assert 'HOST ROOT' in (out/'robots.txt').read_text()
        for name in ['agents.txt','llms.txt','llms-full.txt']:
            assert 'MeTaBoss' in (out/name).read_text()
        print(json.dumps({'ok':True,'readme_words':count,'html_pages':len(pages),'checked_local_links':links,'unique_titles':len(titles),'unique_descriptions':len(descriptions),'sitemap_urls':len(locs),'private_artifacts_published':False},indent=2))

if __name__=='__main__':main()
