from __future__ import annotations
import argparse
import json
import os
import sys
from urllib.parse import urlsplit
from playwright.sync_api import sync_playwright
from model_client import ModelClient
from runner import BrowserAgent


def main() -> int:
    p=argparse.ArgumentParser(description='English test case -> AI-guided browser test with verifiable assertions')
    p.add_argument('--url',required=True,help='Starting URL, HTTPS recommended')
    p.add_argument('--test',required=True,help='Plain-English test case')
    p.add_argument('--provider',choices=['gemini','ollama'],default='ollama')
    p.add_argument('--model',default=None)
    p.add_argument('--ollama-url',default='http://localhost:11434')
    p.add_argument('--allow-domain',action='append',default=[],help='Approved extra host e.g. phptravels.net')
    p.add_argument('--headless',action='store_true')
    p.add_argument('--max-steps',type=int,default=18)
    p.add_argument('--report-dir',default='reports')
    p.add_argument('--allow-destructive',action='store_true',help='Only for authorized sandbox testing')
    args=p.parse_args()
    parsed=urlsplit(args.url)
    if parsed.scheme not in ('https','http') or not parsed.hostname:
        p.error('Start URL must use http or https')
    hosts={parsed.hostname.lower(),*[h.lower() for h in args.allow_domain]}
    secrets={key:os.environ[key] for key in ('TEST_EMAIL','TEST_USERNAME','TEST_PASSWORD') if os.environ.get(key)}
    model=ModelClient(args.provider,args.model,args.ollama_url)
    with sync_playwright() as pw:
        browser=pw.chromium.launch(headless=args.headless,executable_path=os.getenv("CHROMIUM_EXECUTABLE") or None)
        context=browser.new_context(viewport={'width':1280,'height':850},accept_downloads=False)
        page=context.new_page();page.set_default_timeout(7000)
        try:
            page.goto(args.url,wait_until='domcontentloaded',timeout=35000)
            agent=BrowserAgent(page,model,allowed_hosts=hosts,secrets=secrets,
                               max_steps=args.max_steps,allow_destructive=args.allow_destructive)
            result=agent.run(args.test,report_dir=args.report_dir)
            print(json.dumps({k:v for k,v in result.items() if k!='steps'},indent=2))
            print(f"Report: {args.report_dir}/result.json")
            return 0 if result['status']=='PASS' else 1
        finally:
            context.close();browser.close()

if __name__=='__main__': sys.exit(main())
