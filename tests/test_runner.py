from pathlib import Path
import pytest
from unittest.mock import patch
import os
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from playwright.sync_api import sync_playwright
from runner import BrowserAgent, allowed_site, replace_secret
from model_client import parse_json_answer

class ReplayModel:
    def __init__(self,actions): self.actions=iter(actions)
    def decide(self,goal,observation,history): return next(self.actions)

HTML='''<html><head><title>Demo Test Portal</title></head><body>
<h1>Welcome</h1><label>Email <input type="email" /></label>
<button id="go">Log in</button>
<div id="dashboard" style="display:none">Customer Dashboard</div>
<script>document.querySelector('button').addEventListener('click',()=>{
  if(document.querySelector('input').value.includes('@'))document.querySelector('#dashboard').style.display='block';
});</script></body></html>'''


def test_model_parser():
    assert parse_json_answer('```json\n{"action":"wait","seconds":1}\n```')['action']=='wait'


def test_secret_substitution():
    assert replace_secret('{{TEST_EMAIL}}',{'TEST_EMAIL':'demo@example.org'})=='demo@example.org'


def test_host_allowlist():
    assert allowed_site('https://example.com/dashboard',{'example.com'})
    assert not allowed_site('https://notexample.com',{'example.com'})


def test_generic_agent_pass(tmp_path):
    with sync_playwright() as pw:
        browser=pw.chromium.launch(headless=True,executable_path=os.getenv("CHROMIUM_EXECUTABLE") or None)
        page=browser.new_page();page.set_content(HTML)
        model=ReplayModel([
            {'action':'fill','target':{'role':'textbox','name':'Email'},'value':'{{TEST_EMAIL}}'},
            {'action':'click','target':{'role':'button','name':'Log in'}},
            {'action':'assert_visible','text':'Customer Dashboard'},
            {'action':'finish','result':'pass','reason':'Dashboard is visible'}
        ])
        agent=BrowserAgent(page,model,allowed_hosts={'127.0.0.1'},secrets={'TEST_EMAIL':'demo@example.org'})
        with patch('runner.allowed_site',return_value=True):
            result=agent.run('Login and verify dashboard',report_dir=str(tmp_path))
        assert result['status']=='PASS'
        assert result['assertions_passed']==1
        assert 'demo@example.org' not in (tmp_path/'result.json').read_text()
        browser.close()


def test_finish_without_assertion_is_failure(tmp_path):
    with sync_playwright() as pw:
        browser=pw.chromium.launch(headless=True,executable_path=os.getenv("CHROMIUM_EXECUTABLE") or None);page=browser.new_page();page.set_content(HTML)
        agent=BrowserAgent(page,ReplayModel([{'action':'finish','result':'pass','reason':'looks fine'}]),allowed_hosts={'127.0.0.1'})
        with patch('runner.allowed_site',return_value=True):
            assert agent.run('Verify dashboard',report_dir=str(tmp_path))['status']=='FAIL'
        browser.close()


# Regression tests for exact input and dropdown verification

FORM_HTML = """
<html>
<body>
    <label>Text input
        <input type="text">
    </label>

    <label>Dropdown
        <select>
            <option>One</option>
            <option>Two</option>
        </select>
    </label>
</body>
</html>
"""


def run_form_actions(actions, tmp_path):
    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=True,
            executable_path=os.getenv("CHROMIUM_EXECUTABLE") or None
        )

        try:
            page = browser.new_page()
            page.set_content(FORM_HTML)

            agent = BrowserAgent(
                page,
                ReplayModel(actions),
                allowed_hosts={"127.0.0.1"},
                max_steps=8
            )

            with patch("runner.allowed_site", return_value=True):
                return agent.run(
                    "Test form fields",
                    report_dir=str(tmp_path)
                )
        finally:
            browser.close()


def test_exact_value_and_dropdown_both_pass(tmp_path):
    text = {"role": "textbox", "name": "Text input"}
    dropdown = {"role": "combobox", "name": "Dropdown"}

    result = run_form_actions([
        {"action": "fill", "target": text, "value": "Aaron"},
        {"action": "select", "target": dropdown, "value": "Two"},
        {"action": "assert_value", "target": text, "equals": "Aaron"},
        {"action": "assert_selected_option", "target": dropdown, "equals": "Two"},
        {"action": "finish", "result": "pass", "reason": "Both verified"}
    ], tmp_path)

    assert result["status"] == "PASS"
    assert result["assertions_passed"] == 2


def test_wrong_input_value_cannot_pass(tmp_path):
    text = {"role": "textbox", "name": "Text input"}

    result = run_form_actions([
        {"action": "fill", "target": text, "value": "Aaron"},
        {"action": "assert_value", "target": text, "equals": "Wrong"},
        {"action": "finish", "result": "pass", "reason": "Incorrect claim"}
    ], tmp_path)

    assert result["status"] == "FAIL"
    assert result["assertions_passed"] == 0
    assert any(s["status"] == "ERROR" for s in result["steps"])


def test_wrong_dropdown_selection_cannot_pass(tmp_path):
    dropdown = {"role": "combobox", "name": "Dropdown"}

    result = run_form_actions([
        {"action": "select", "target": dropdown, "value": "Two"},
        {"action": "assert_selected_option", "target": dropdown, "equals": "One"},
        {"action": "finish", "result": "pass", "reason": "Incorrect claim"}
    ], tmp_path)

    assert result["status"] == "FAIL"
    assert result["assertions_passed"] == 0
    assert any(s["status"] == "ERROR" for s in result["steps"])


def test_visibility_is_not_value_verification(tmp_path):
    text = {"role": "textbox", "name": "Text input"}

    result = run_form_actions([
        {"action": "fill", "target": text, "value": "Aaron"},
        {"action": "assert_visible", "target": text, "text": "Aaron"},
        {"action": "finish", "result": "pass", "reason": "Incorrect claim"}
    ], tmp_path)

    assert result["status"] == "FAIL"
    assert result["assertions_passed"] == 0


def test_failed_assertion_cannot_be_overridden(tmp_path):
    text = {"role": "textbox", "name": "Text input"}
    dropdown = {"role": "combobox", "name": "Dropdown"}

    result = run_form_actions([
        {"action": "fill", "target": text, "value": "Aaron"},
        {"action": "select", "target": dropdown, "value": "Two"},

        # Deliberately fails
        {"action": "assert_value", "target": text, "equals": "Wrong"},

        # Deliberately passes
        {"action": "assert_selected_option", "target": dropdown, "equals": "Two"},

        # AI incorrectly claims the overall test passed
        {"action": "finish", "result": "pass", "reason": "All checks passed"}
    ], tmp_path)

    assert result["status"] == "FAIL"
    assert any(
        step["status"] == "ERROR"
        for step in result["steps"]
    )
