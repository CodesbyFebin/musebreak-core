#!/usr/bin/env python3
"""Build selected public documentation only. No backend execution or network access."""
import argparse
from datetime import date
from html import escape, unescape
from pathlib import Path
import json
import re
import shutil
from urllib.parse import quote, urlsplit
import xml.etree.ElementTree as ET
import markdown

ROOT = Path(__file__).resolve().parents[1]
BASE = 'https://codesbyfebin.github.io/musebreak-core/'
REPO = 'https://github.com/CodesbyFebin/musebreak-core'
SOURCE_REF = 'docs/public-discovery'
# Explicit allowlist: never recursively publish repository contents or evidence data.
PAGES = [
 ('README.md','index.html','MeTaBoss — Meta AI Business Operations Sovereign System','Experimental self-hosted AI gateway and Business OS: exact-payload invoice approval, signed receipts, independent local-state verification, and community.'),
 ('docs/wiki/Home.md','wiki.html','Documentation wiki','Choose a MeTaBoss guide by task: synthetic quick start, architecture, security, evidence, community and publication.'),
 ('docs/wiki/Quickstart.md','quickstart.html','Run the synthetic invoice demo','Reproduce an INR 471.98 synthetic invoice, exact-hash approval, atomic issuance, and a separate-process receipt verification.'),
 ('docs/wiki/Architecture.md','architecture.html','Architecture and trust boundaries','Understand the separation between proposal, gateway authority, local business effects and independent read-only observation.'),
 ('docs/wiki/Security.md','security.html','Security boundaries and privacy','Trusted components, public demo-key limitations, durable data, excluded legacy routes and remaining operational risks.'),
 ('docs/wiki/FAQ.md','faq.html','Questions and answers','Is the repository public? What does verification prove? Model identity, robotics status, and limits of AI discovery.'),
 ('docs/wiki/Community.md','community.html','Community welcome','Help reproduce results, improve accessible review interfaces, clarify documentation and add meaningful safety tests.'),
 ('docs/wiki/Publishing.md','publishing.html','Publish and measure public documentation','Configure GitHub Pages, validate crawlable documentation, understand robots scope, and measure real discovery without ranking promises.'),
 ('docs/verification/INVOICE-WORKFLOW.md','invoice-workflow.html','Invoice workflow contract','Exact business API behavior: operator authorization, canonical hashes, integer totals, transactional stock changes and verification assumptions.'),
 ('docs/verification/QUALIFICATION.md','qualification.html','Recorded invoice qualification','Recorded environment, 89 backend and CLI tests, 21 new invoice tests, synthetic demonstration and explicit coverage limits.'),
 ('docs/verification/UPSTREAM-COMPARISON.md','comparison.html','Pinned implementation comparison','Source review of Witness, Munix, Meta GitHub agent cookbook and the original bounded invoice implementation.'),
 ('CONTRIBUTING.md','contributing.html','Contributing to MeTaBoss','Focused pull requests, synthetic reproduction reports, licensing, conduct, and appropriate validation.'),
 ('SECURITY.md','reporting.html','Security reporting policy','How to report a suspected issue cautiously without exposing credentials, customer data or sensitive exploit details.'),
 ('AGENTS.md','agent-instructions.html','Coding agent contribution instructions','Repository instructions for safe scoped changes, independent verifier boundaries and honest feature claims.'),
]
MAPPING = {src:dest for src,dest,_,_ in PAGES}

def full_text():
    sources=['README.md',*[p[0] for p in PAGES if p[0].startswith('docs/wiki/')], 'docs/verification/INVOICE-WORKFLOW.md']
    return '# MeTaBoss public documentation bundle\n\nPlain-text retrieval aid. Source status and trust limits apply; no execution authority is granted.\n\n'+'\n\n'.join(f'---\nSource: {src}\n\n{(ROOT/src).read_text().rstrip()}' for src in sources)+'\n'

def rewrite_links(html, source):
    def replace(m):
        attr,raw=m.group(1),unescape(m.group(2))
        parsed=urlsplit(raw)
        if parsed.scheme or parsed.netloc or raw.startswith('#') or raw.startswith('/'):
            return m.group(0)
        path=(ROOT/source).parent.joinpath(parsed.path).resolve()
        try: rel=path.relative_to(ROOT).as_posix()
        except ValueError: raise ValueError(f'Link escapes repository in {source}: {raw}')
        if not path.exists(): raise ValueError(f'Missing source link in {source}: {raw}')
        if rel in MAPPING: target=MAPPING[rel]
        elif rel in {'llms.txt','llms-full.txt','agents.txt','robots.txt','project.json'}:target=rel
        else:target=f'{REPO}/blob/{SOURCE_REF}/{quote(rel)}'
        if parsed.query:target+='?'+parsed.query
        if parsed.fragment:target+='#'+parsed.fragment
        return f'{attr}="{escape(target,quote=True)}"'
    return re.sub(r'(href|src)="([^"]+)"',replace,html)

STYLE='''*{box-sizing:border-box}html{color-scheme:dark;scroll-behavior:smooth}body{margin:0;background:#0c1017;color:#e1e6ef;font:17px/1.75 system-ui,sans-serif}a{color:#9cbcff;text-underline-offset:3px}a:hover{color:#d3e2ff}a:focus-visible{outline:3px solid #f6c25a;outline-offset:4px}.skip{position:absolute;left:-9999px}.skip:focus{left:1rem;top:1rem;background:#17243b;padding:1rem;z-index:2}header{border-bottom:1px solid #303b4a;padding:22px max(24px,calc((100vw - 1240px)/2));background:#111824}header strong{font-size:24px;color:white}header p{margin:0;color:#b5bfce;font-size:14px}.layout{display:grid;grid-template-columns:220px minmax(0,900px);max-width:1240px;margin:auto;gap:40px;padding:32px 24px}nav{font-size:14px}nav ul{list-style:none;padding:0;position:sticky;top:20px}nav li{margin:0 0 9px}nav [aria-current]{color:#a8efd3;font-weight:700}main{min-width:0}h1{font-size:clamp(30px,4vw,45px);line-height:1.2;color:#fff}h2{margin-top:2.6rem;line-height:1.3;color:#fff}h3{margin-top:2rem;color:#fff}code{font-family:ui-monospace,monospace;font-size:.85em;background:#182231;padding:.12em .3em;border-radius:3px}pre{overflow:auto;background:#131d2b;padding:20px;border:1px solid #354258;border-radius:8px}pre code{padding:0;background:none}.table-scroll{overflow-x:auto}table{border-collapse:collapse;font-size:14px;min-width:600px}th,td{padding:12px;border:1px solid #354258;text-align:left;vertical-align:top}th{background:#182231}blockquote,.notice{margin:1rem 0;padding:14px 20px;border-left:4px solid #84d6b3;background:#142422}.notice{font-size:14px}footer{border-top:1px solid #303b4a;padding:30px 24px;max-width:1240px;margin:30px auto;color:#b5bfce;font-size:14px}img{max-width:100%}@media(max-width:800px){.layout{grid-template-columns:1fr;gap:12px;padding:16px}nav ul{position:static;display:flex;flex-wrap:wrap;gap:10px 18px}nav li{margin:0}header{padding:18px}body{font-size:16px}h1{font-size:31px}}@media(prefers-reduced-motion:reduce){html{scroll-behavior:auto}}'''

def build(out):
    out=Path(out).resolve()
    if out==ROOT or ROOT in out.parents and out.name!='_site':
        raise ValueError('Use _site in the repository or a separate temporary output directory')
    out.mkdir(parents=True,exist_ok=True)
    (out/'style.css').write_text(STYLE)
    for src,dest,title,description in PAGES:
        text=(ROOT/src).read_text()
        body=markdown.markdown(text,extensions=['fenced_code','tables','toc'])
        body=rewrite_links(body,src)
        body=re.sub(r'<table>(.*?)</table>',r'<div class="table-scroll"><table>\1</table></div>',body,flags=re.S)
        canonical=BASE+('' if dest=='index.html' else dest)
        schema={'@context':'https://schema.org','@type':'SoftwareSourceCode','name':'MeTaBoss','alternateName':'MuseBreak','description':'Experimental self-hosted AI gateway and Business OS with exact-payload invoice approvals and independent local-state verification.','codeRepository':REPO,'license':REPO+'/blob/main/LICENSE','programmingLanguage':['Python','TypeScript','Go'],'author':{'@type':'Person','name':'CodesbyFebin','url':'https://github.com/CodesbyFebin'}}
        nav=''.join(f'<li><a href="{d}"'+(' aria-current="page"' if d==dest else '')+f'>{escape(t if d!="index.html" else "Project guide")}</a></li>' for _,d,t,_ in PAGES)
        sourceurl=f'{REPO}/blob/{SOURCE_REF}/{quote(src)}'
        html=f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(title)} | MeTaBoss</title><meta name="description" content="{escape(description,quote=True)}"><meta name="robots" content="index,follow"><link rel="canonical" href="{canonical}">
<meta property="og:title" content="{escape(title,quote=True)}"><meta property="og:description" content="{escape(description,quote=True)}"><meta property="og:type" content="website"><meta property="og:url" content="{canonical}"><meta property="og:site_name" content="MeTaBoss"><meta name="twitter:card" content="summary"><link rel="stylesheet" href="style.css"><link rel="alternate" type="text/plain" title="LLM retrieval guide" href="llms.txt"><script type="application/ld+json">{json.dumps(schema).replace('<','\\u003c')}</script></head>
<body><a class="skip" href="#main">Skip to content</a><header><a href="index.html"><strong>MeTaBoss</strong></a><p>Meta AI Business Operations Sovereign System · Formerly MuseBreak · Independent project</p></header>
<div class="layout"><nav aria-label="Documentation"><ul>{nav}<li><a href="{REPO}">GitHub repository</a></li><li><a href="llms.txt">Retrieval guide</a></li></ul></nav><main id="main"><aside class="notice" aria-label="Development status">Development prototype. Invoice implementation: <a href="{REPO}/pull/1">PR #1</a>. Documentation describes the pending implementation; inspect current merge status. No live model call, payment settlement, physical hardware proof or real zkVM is established by the synthetic invoice demo.</aside>{body}</main></div>
<footer><p><a href="{sourceurl}">View this page's source</a> · <a href="project.json">Project identity</a> · <a href="agents.txt">Agent entry point</a> · <a href="llms-full.txt">Full plain text</a></p><p>Public documentation only. No customer records, private keys or backend service are hosted here. MIT-licensed source; dependencies and models retain separate terms.</p></footer></body></html>'''
        (out/dest).write_text(html)
    for name in ['agents.txt','llms.txt','robots.txt','project.json']:
        shutil.copyfile(ROOT/name,out/name)
    (out/'llms-full.txt').write_text(full_text())
    (out/'.nojekyll').touch()
    ns='http://www.sitemaps.org/schemas/sitemap/0.9';ET.register_namespace('',ns)
    sitemap=ET.Element(f'{{{ns}}}urlset')
    for _,dest,_,_ in PAGES:
        u=ET.SubElement(sitemap,f'{{{ns}}}url');ET.SubElement(u,f'{{{ns}}}loc').text=BASE+('' if dest=='index.html' else dest)
    ET.ElementTree(sitemap).write(out/'sitemap.xml',encoding='utf-8',xml_declaration=True)
    (out/'404.html').write_text('<!doctype html><html lang="en"><meta charset="utf-8"><meta name="robots" content="noindex"><title>Page not found | MeTaBoss</title><h1>Page not found</h1><p><a href="'+BASE+'">Open the MeTaBoss documentation</a></p></html>')
    return out

if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--out',default=str(ROOT/'_site'));ap.add_argument('--refresh-text',action='store_true');args=ap.parse_args()
    if args.refresh_text:(ROOT/'llms-full.txt').write_text(full_text())
    output=build(args.out);print(f'Built {len(PAGES)} public documentation pages in {output}')
