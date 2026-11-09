"""Page-independent browser actions and evidence-driven pass/fail results."""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
from urllib.parse import urlsplit

from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError


# This snapshot deliberately discovers the CURRENT page rather than relying on
# a hardcoded website's DOM. Ephemeral refs are re-created each observation.
SNAPSHOT_JS = r"""
() => {
  const visible = el => !!(el.getClientRects().length && getComputedStyle(el).visibility!=='hidden' && getComputedStyle(el).display!=='none');
  const text = el => (el?.innerText || el?.textContent || '').replace(/\s+/g,' ').trim().slice(0,85);
  const targets = Array.from(document.querySelectorAll(
    'a[href],button,input:not([type="hidden"]),textarea,select,[role="button"],[role="link"],[role="textbox"],[role="combobox"],[role="option"],[role="tab"],[role="checkbox"],[role="radio"]'
  )).filter(e=>visible(e) && !e.disabled).slice(0,120);
  const seen = new Set();
  const elements = targets.map((el,index)=>{
     const ref='e'+(index+1); el.setAttribute('data-test-agent-ref',ref);
     const labels=el.labels ? Array.from(el.labels).map(text).join(' ') : '';
     const labelledby=(el.getAttribute('aria-labelledby')||'').split(/\s+/).filter(Boolean)
       .map(id=>text(document.getElementById(id))).join(' ');
     const name=(el.getAttribute('aria-label')||labels||labelledby||el.getAttribute('placeholder')||text(el)||el.getAttribute('title')||'').slice(0,100);
     const tag=el.tagName.toLowerCase();
     const role=el.getAttribute('role')||({a:'link',button:'button',textarea:'textbox',select:'combobox'}[tag]||
       (tag==='input'?({'checkbox':'checkbox','radio':'radio','submit':'button'}[el.type]||'textbox'):'element'));
     return {ref,tag,role,name,type:el.getAttribute('type')||'',text:text(el),
       placeholder:el.getAttribute('placeholder')||'',href:el.getAttribute('href')||'',
       checked:!!el.checked,selected:el.getAttribute('aria-selected')||''};
  });
  const headings=Array.from(document.querySelectorAll('h1,h2,h3,[role="heading"]')).filter(visible).slice(0,16).map(text);
  const main=document.querySelector('main')||document.body;
  let bodyText=(main?.innerText||'').replace(/\s+/g,' ').trim().slice(0,1900);
  return {title:document.title, url:location.href,headings,elements,body_excerpt:bodyText};
}
"""

DANGEROUS = re.compile(
    r'\b(pay now|place order|confirm purchase|buy now|delete account|delete all|remove account|transfer funds|send money)\b',
    re.I,
)
ALLOWED_ACTIONS = {
    'click', 'fill', 'select', 'check', 'press',
    'navigate', 'assert_visible', 'assert_not_visible',
    'assert_url', 'assert_title', 'assert_value',
    'assert_selected_option', 'wait', 'finish',
}


def allowed_site(url: str, allowed_hosts: set[str]) -> bool:
    parsed = urlsplit(url)
    return parsed.scheme in ('http', 'https') and (parsed.hostname or '').lower() in allowed_hosts


def replace_secret(s: str, secrets: dict[str, str]) -> str:
    def repl(match):
        key = match.group(1)
        if key not in secrets:
            raise ValueError(f'Missing value for secret {key}')
        return secrets[key]

    return re.sub(r'\{\{(TEST_[A-Z_]+)\}\}', repl, s)


def scrub_sensitive(s: str, secrets: dict[str, str]) -> str:
    for value in secrets.values():
        if value and len(value) >= 3:
            s = s.replace(value, '[REDACTED]')
    return s


def locator_for(page: Page, target: dict):
    if not isinstance(target, dict):
        raise ValueError('Action requires a target object')
    if target.get('ref'):
        ref = target['ref']
        if not re.fullmatch(r'e\d{1,3}', ref):
            raise ValueError('Invalid element ref')
        return page.locator(f'[data-test-agent-ref="{ref}"]')
    role = target.get('role')
    name = target.get('name')
    if role and name:
        return page.get_by_role(role, name=name, exact=True)
    if name:
        return page.get_by_label(name, exact=True)
    raise ValueError('Use an observed ref or semantic role/name to target an element')


class BrowserAgent:
    def __init__(
        self, page: Page, model, *, allowed_hosts: set[str],
        secrets: dict[str, str] | None = None,
        max_steps: int = 18, allow_destructive: bool = False,
    ):
        self.page = page
        self.model = model
        self.allowed_hosts = {h.lower() for h in allowed_hosts}
        self.secrets = secrets or {}
        self.max_steps = max_steps
        self.allow_destructive = allow_destructive
        self.history = []
        self.assertions = 0
        self.assertion_failures = []  # NEW: a failed assertion must not be overridden

    def observe(self) -> dict:
        data = self.page.evaluate(SNAPSHOT_JS)
        # Avoid sending personal or authentication tokens in URLs.
        p = urlsplit(data['url'])
        data['url'] = p._replace(query='', fragment='').geturl()
        data['body_excerpt'] = scrub_sensitive(data.get('body_excerpt', ''), self.secrets)
        return data

    def act(self, instruction: dict, observation: dict) -> str:
        action = instruction.get('action')
        if action not in ALLOWED_ACTIONS:
            raise ValueError(f'Unsupported action {action!r}')
        if action == 'finish':
            return 'finish'
        if action == 'wait':
            self.page.wait_for_timeout(min(max(float(instruction.get('seconds', 1)), 0), 3) * 1000)
            return 'Wait completed'
        if action == 'navigate':
            url = instruction.get('url', '')
            if not allowed_site(url, self.allowed_hosts):
                raise ValueError('Navigation blocked: host not approved')
            self.page.goto(url, wait_until='domcontentloaded', timeout=25000)
            return 'Navigated to approved host'

        if action in ('assert_url', 'assert_title'):
            got = self.page.url if action == 'assert_url' else self.page.title()
            fragment = instruction.get('contains', '')
            if not fragment or fragment.lower() not in got.lower():
                raise AssertionError(f'{action} failed: expected to contain {fragment!r}')
            self.assertions += 1
            return f'{action} passed: {fragment!r}'

        if action in ('assert_value', 'assert_selected_option'):
            target = instruction.get('target')
            expected = instruction.get('equals')
            if not target:
                raise ValueError('Assertion requires a target')
            if not isinstance(expected, str):
                raise ValueError('Assertion requires expected text')

            loc = locator_for(self.page, target)
            if action == 'assert_value':
                actual = loc.input_value(timeout=6500)
            else:
                actual = loc.evaluate("""element => {
                    if (element.tagName !== 'SELECT') {
                        throw new Error('Expected an HTML select');
                    }
                    const selected = Array.from(element.selectedOptions);
                    return selected.length === 1
                        ? selected[0].textContent.trim()
                        : null;
                }""")

            if actual != expected:
                raise AssertionError(
                    f'{action} failed: expected {expected!r}, got {actual!r}'
                )
            self.assertions += 1
            return f'{action} passed'

        if action in ('assert_visible', 'assert_not_visible'):
            if instruction.get('target') and 'text' in instruction:
                raise ValueError(
                    'Visibility does not verify text or field values. '
                    'Use assert_value or assert_selected_option.'
                )
            if instruction.get('target'):
                loc = locator_for(self.page, instruction['target'])
            else:
                value = instruction.get('text', '')
                if not value:
                    raise ValueError('Assertion needs a target or text')
                loc = self.page.get_by_text(value, exact=False).first
            if action == 'assert_visible':
                loc.wait_for(state='visible', timeout=6500)
            else:
                loc.wait_for(state='hidden', timeout=6500)
            self.assertions += 1
            return f'{action} passed'

        target = instruction.get('target') or {}
        # Check that model-supplied refs appear in the CURRENT observation.
        if target.get('ref') and target['ref'] not in [e['ref'] for e in observation['elements']]:
            raise ValueError('Element ref not present in current observation')
        el = locator_for(self.page, target)
        if action == 'click':
            label = next(
                (e['name'] or e['text'] for e in observation['elements'] if e['ref'] == target.get('ref')),
                target.get('name', ''),
            )
            if DANGEROUS.search(label or '') and not self.allow_destructive:
                raise ValueError(
                    'Potentially destructive action blocked; use --allow-destructive '
                    'for authorized test environments'
                )
            el.click(timeout=7000)
            if not allowed_site(self.page.url, self.allowed_hosts):
                raise ValueError('Navigation reached an unapproved host; stopping')
            return 'Clicked selected control'
        if action == 'fill':
            value = replace_secret(str(instruction.get('value', '')), self.secrets)
            el.fill(value, timeout=7000)
            return 'Filled selected control (value omitted from report)'
        if action == 'select':
            value = instruction.get('value', '')
            el.select_option(label=value, timeout=7000)
            return f'Selected option label {value!r}'
        if action == 'check':
            el.check(timeout=7000)
            return 'Checked selected control'
        if action == 'press':
            key = instruction.get('key', 'Enter')
            if key not in ('Enter', 'Tab', 'Escape', 'ArrowDown', 'ArrowUp', 'Space'):
                raise ValueError('Unsupported key')
            el.press(key, timeout=7000)
            return f'Pressed {key}'
        raise ValueError('Unhandled action')

    def run(self, goal: str, *, report_dir: str = 'reports') -> dict:
        folder = Path(report_dir)
        folder.mkdir(parents=True, exist_ok=True)
        status = 'FAIL'
        reason = 'Step limit exceeded'

        for i in range(1, self.max_steps + 1):
            if not allowed_site(self.page.url, self.allowed_hosts):
                reason = 'Browser navigated to unapproved website'
                break

            observation = self.observe()
            decision = None  # NEW: distinguish model errors from assertion errors
            try:
                decision = self.model.decide(goal, observation, self.history)
                # Secrets should never enter recorded history or model memory.
                cleaned = {
                    k: ('[REDACTED]' if k == 'value' else v)
                    for k, v in decision.items()
                }

                if decision.get('action') == 'finish':
                    proposed = str(decision.get('result', 'fail')).lower()
                    if proposed == 'pass' and self.assertion_failures:
                        # NEW: even one failed assertion prevents a final PASS.
                        status = 'FAIL'
                        reason = (
                            f'{len(self.assertion_failures)} assertion(s) failed. '
                            f'First failure: {self.assertion_failures[0]}'
                        )
                    elif proposed == 'pass' and self.assertions > 0:
                        status = 'PASS'
                        reason = scrub_sensitive(
                            str(decision.get('reason', 'Verified outcome')),
                            self.secrets,
                        )
                    else:
                        status = 'FAIL'
                        reason = scrub_sensitive(
                            str(decision.get('reason', 'No verified assertions')),
                            self.secrets,
                        )
                    self.history.append({'step': i, 'action': cleaned, 'status': status})
                    break

                feedback = self.act(decision, observation)
                self.history.append({
                    'step': i,
                    'action': cleaned,
                    'status': 'OK',
                    'feedback': feedback,
                })

            
            except Exception as error:
                note = scrub_sensitive(str(error)[:220], self.secrets)

                # Record failed assertions
                if (
                    isinstance(decision, dict)
                    and str(decision.get('action', '')).startswith('assert_')
                ):
                    self.assertion_failures.append(note)

                self.history.append({
                    'step': i,
                    'status': 'ERROR',
                    'feedback': note
                })

                # NEW: Stop immediately when Gemini returns HTTP 429
                if getattr(
                    getattr(error, "response", None),
                    "status_code",
                    None
                ) == 429:
                    reason = (
                        "Gemini API rate limit or quota exceeded (HTTP 429). "
                        "Browser test could not be completed."
                    )
                    break

                if i == self.max_steps:
                    reason = note


        else:
            if self.assertion_failures:
                reason = (
                    f'{len(self.assertion_failures)} assertion(s) failed. '
                    f'First failure: {self.assertion_failures[0]}'
                )
            else:
                reason = 'Maximum steps reached without verified completion'

        result = {
            'goal': goal,
            'status': status,
            'reason': reason,
            'assertions_passed': self.assertions,
            'steps': self.history,
            'final_url': urlsplit(self.page.url)._replace(query='', fragment='').geturl(),
        }
        (folder / 'result.json').write_text(
            json.dumps(result, indent=2, ensure_ascii=False), encoding='utf-8'
        )
        if status != 'PASS':
            try:
                self.page.screenshot(path=str(folder / 'failure.png'), full_page=True)
            except Exception:
                pass
        return result
