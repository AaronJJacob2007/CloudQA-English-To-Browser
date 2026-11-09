
# English-to-Browser Test Runner

**CloudQA Task 2 | Natural-Language Browser Testing with Playwright and Gemini/Ollama**

A Python-based browser testing tool that translates plain-English test cases into browser actions and explicit assertions using Playwright and a large language model.

Instead of relying on website-specific automation scripts, the runner observes the current webpage, identifies available controls, and selects appropriate browser actions based on the user's instructions.

The starting URL and test case are configurable, allowing the same agent to work across different websites within its supported capabilities.

## Features

- **Natural-language testing:** Execute browser tests using plain-English instructions.
- **Dynamic page inspection:** Discover visible elements, accessible labels, roles, headings, and page content.
- **Website-independent execution:** Use dynamically generated element references and semantic locators rather than hardcoded website selectors.
- **Multiple LLM providers:** Supports Gemini API and locally hosted Ollama models.
- **Browser automation:** Navigate, click, fill inputs, select dropdown options, check controls, and press supported keys.
- **Explicit assertions:** Verify element visibility, URLs, page titles, exact input values, and selected dropdown options.
- **Structured reporting:** Generate JSON reports containing execution steps, assertion results, and final test status.
- **Failure screenshots:** Capture screenshots when tests fail.
- **Execution safeguards:** Domain allowlisting, restricted actions, secret substitution, and protection against destructive operations.

## Architecture

```text
            Plain-English Test Case
                      |
                      v
               Starting URL
                      |
                      v
             Playwright Browser
                      |
                      v
             Current DOM Snapshot
          (Elements, Labels, Text)
                      |
                      v
             LLM Action Selection
             (Gemini / Ollama)
                      |
                      v
            Action Validation
                      |
                      v
            Playwright Execution
                      |
                      v
          Feedback + New Observation
                      |
                      v
              Repeat Until Done
                      |
                      v
           PASS / FAIL + JSON Report
```

The runner observes the active page before selecting each action. Interactive elements are assigned temporary references such as `e1` and `e2`, which are regenerated during subsequent observations.

The agent can also locate controls through accessible roles and names.

A test can return PASS only after a successful explicit assertion. Recorded assertion failures prevent an overall PASS, even if later assertions succeed.

## Technology Stack

| Component | Technology |
|---|---|
| Programming language | Python 3.12 |
| Browser automation | Playwright |
| Hosted AI provider | Google Gemini API |
| Local AI provider | Ollama |
| Test framework | pytest |
| Browser | Chromium |
| Reporting | JSON and screenshots |

## Project Structure

```text
CloudQA-English-To-Browser/
|
|-- main.py
|-- model_client.py
|-- runner.py
|-- requirements.txt
|-- README.md
|-- APPROACH_AND_LIMITATIONS.md
|-- .gitignore
|
|-- examples/
|   |-- test_cases.md
|
|-- tests/
|   |-- test_runner.py
```

### File Responsibilities

- `main.py` — Command-line interface, configuration, and browser initialization.
- `model_client.py` — Communication with Gemini API or Ollama.
- `runner.py` — DOM observation, browser actions, assertions, execution control, and reporting.
- `tests/test_runner.py` — Automated regression tests.
- `examples/test_cases.md` — Sample natural-language test cases.
- `APPROACH_AND_LIMITATIONS.md` — Technical approach, verification strategy, and known limitations.

## Installation

### Prerequisites

- Python 3.11 or newer
- Windows, Linux, or macOS
- Internet connection for hosted AI models
- Gemini API key or a local Ollama installation

The following setup commands use Windows PowerShell.

### 1. Clone the repository

```powershell
git clone https://github.com/AaronJJacob2007/CloudQA-English-To-Browser.git
cd CloudQA-English-To-Browser
```

### 2. Create a virtual environment

```powershell
py -3.12 -m venv .venv
```

### 3. Install dependencies

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### 4. Install Playwright Chromium

```powershell
.\.venv\Scripts\python.exe -m playwright install chromium
```

## Model Configuration

The application supports two model providers.

### Option A — Gemini API

Generate an API key through [Google AI Studio](https://aistudio.google.com/apikey).

Set the API key in the current PowerShell session:

```powershell
$env:GEMINI_API_KEY="YOUR_API_KEY"
```

Run a test:

```powershell
.\.venv\Scripts\python.exe main.py `
  --url "https://phptravels.com/demo" `
  --test "Verify that the page offers demo access" `
  --provider gemini `
  --model gemini-3.6-flash `
  --max-steps 5
```

The model identifier can be changed using `--model`, depending on available models and project permissions.

Gemini API requests are subject to the project's rate limits and quotas. An HTTP 429 response is reported as an API rate-limit or quota error.

### Option B — Ollama

Install [Ollama](https://ollama.com/) and download a model:

```powershell
ollama pull qwen3:8b
```

Ensure the Ollama server is running.

Execute the same test using the local model:

```powershell
.\.venv\Scripts\python.exe main.py `
  --url "https://phptravels.com/demo" `
  --test "Verify that the page offers demo access" `
  --provider ollama `
  --model qwen3:8b `
  --max-steps 5
```

Ollama allows local inference without a hosted API key. Execution speed depends on available CPU, GPU, and memory resources.

## Usage Examples

### Example 1 — Verify a webpage feature

```powershell
.\.venv\Scripts\python.exe main.py `
  --url "https://phptravels.com/demo" `
  --test "Verify that the page offers demo access" `
  --provider gemini `
  --model gemini-3.6-flash `
  --max-steps 5
```

The agent observes the webpage and attempts to verify the requested feature.

### Example 2 — Fill and verify an input field

```powershell
.\.venv\Scripts\python.exe main.py `
  --url "https://www.selenium.dev/selenium/web/web-form.html" `
  --test "Enter Aaron into the Text input field and verify its value equals Aaron" `
  --provider gemini `
  --model gemini-3.6-flash `
  --max-steps 5
```

Expected actions:

1. Identify the text input.
2. Fill it with `Aaron`.
3. Use `assert_value` to verify the exact input value.
4. Report the result.

### Example 3 — Verify a dropdown selection

```powershell
.\.venv\Scripts\python.exe main.py `
  --url "https://www.selenium.dev/selenium/web/web-form.html" `
  --test "Select Two from the standard dropdown and verify the currently selected option is exactly Two" `
  --provider gemini `
  --model gemini-3.6-flash `
  --max-steps 5
```

The agent uses `assert_selected_option` to verify the selected native dropdown option.

### Example 4 — Multi-step browser test

```powershell
.\.venv\Scripts\python.exe main.py `
  --url "https://www.selenium.dev/selenium/web/web-form.html" `
  --test "Enter Aaron into the Text input field and select Two from the standard dropdown. Verify BOTH that the input value is exactly Aaron AND that Two is the selected dropdown option." `
  --provider gemini `
  --model gemini-3.6-flash `
  --max-steps 8
```

This test was successfully executed with two independent assertions:

- `assert_value` verified that the input value was `Aaron`.
- `assert_selected_option` verified that `Two` was selected.

### Example 5 — Negative verification

```powershell
.\.venv\Scripts\python.exe main.py `
  --url "https://www.selenium.dev/selenium/web/web-form.html" `
  --test "Verify that the page contains the exact visible text CLOUDQA_MISSING_987654" `
  --provider gemini `
  --model gemini-3.6-flash `
  --max-steps 5
```

Because the requested text does not exist, a correctly executed test should report FAIL.

## Command-Line Arguments

| Argument | Description |
|---|---|
| `--url` | Starting webpage URL |
| `--test` | Natural-language test instruction |
| `--provider` | `gemini` or `ollama` |
| `--model` | Model identifier |
| `--headless` | Run the browser without a visible window |
| `--max-steps` | Maximum agent execution steps |
| `--report-dir` | Directory for generated reports |
| `--allow-domain` | Explicitly allow an additional hostname |
| `--ollama-url` | Address of the Ollama server |
| `--allow-destructive` | Permit otherwise restricted actions in authorized testing environments |

## Supported Actions

| Action | Function |
|---|---|
| `navigate` | Navigate to an approved URL |
| `click` | Click an interactive element |
| `fill` | Enter text into a field |
| `select` | Select a native dropdown option |
| `check` | Check a supported control |
| `press` | Press an allowed keyboard key |
| `wait` | Wait briefly |
| `assert_visible` | Verify an element or text is visible |
| `assert_not_visible` | Verify an element or text is not visible |
| `assert_url` | Verify a URL contains expected text |
| `assert_title` | Verify a page title contains expected text |
| `assert_value` | Verify an exact input value |
| `assert_selected_option` | Verify the selected native dropdown option |
| `finish` | Complete execution with PASS or FAIL |

## Test Reports

Every execution generates:

```text
reports/
|-- result.json
```

Failed executions also attempt to generate:

```text
reports/
|-- result.json
|-- failure.png
```

A successful report contains fields such as:

```json
{
  "goal": "Verify that the page offers demo access",
  "status": "PASS",
  "reason": "The requested demo-access control was visible.",
  "assertions_passed": 1,
  "final_url": "https://phptravels.com/demo"
}
```

The complete report additionally includes a `steps` array with executed actions, feedback, and individual outcomes.

Filled values are masked in the recorded action history.

## Automated Testing

Run the regression suite:

```powershell
.\.venv\Scripts\python.exe -m pytest tests -v
```

### Validation Results

**10 automated regression tests passed on Windows using Python 3.12.**

The tests cover:

- Model response parsing
- Secret substitution
- Domain allowlisting
- Browser execution with a scripted model
- Rejection of PASS without successful assertions
- Exact text-input verification
- Native dropdown verification
- Rejection of incorrect input values
- Rejection of incorrect dropdown selections
- Prevention of PASS after an earlier failed assertion

The tests use local browser fixtures and scripted model responses. They do not require live Gemini API calls.

### Live Browser Validation

Additional tests were executed using Gemini and Playwright against two public websites.

| Test Case | Observed Outcome |
|---|---|
| PHPTRAVELS demo-access verification | PASS |
| Deliberately nonexistent webpage text | FAIL |
| Enter and verify a text-input value | PASS |
| Select and verify a dropdown option | PASS |
| Multi-step input and dropdown verification | PASS |
| Multi-step test containing an impossible requirement | FAIL |

These results demonstrate the implementation's core capabilities but do not guarantee successful execution of arbitrary unseen test cases.

## Credentials and Security

Test credentials can be supplied through environment variables.

```powershell
$env:TEST_EMAIL="demo@example.com"
$env:TEST_PASSWORD="YOUR_TEST_PASSWORD"
```

Supported placeholders can be referenced in test instructions:

```text
Log in using {{TEST_EMAIL}} and {{TEST_PASSWORD}}, then verify the dashboard is visible.
```

The browser resolves supported placeholders during execution without including the underlying credential values directly in model instructions.

The runner also provides:

- Domain allowlisting for navigation.
- Restricted action execution.
- Blocking of certain potentially destructive operations by default.
- Masking of entered values in reports.
- Redaction of configured secrets from recorded text.

These safeguards are not a complete security boundary. Webpage observations are provided to the selected model, and screenshots may contain sensitive content.

Use dedicated test accounts and authorized test environments. Do not commit API keys, passwords, environment files, or generated reports.

## Limitations

- Model-generated actions may occasionally select incorrect elements or assertions.
- A successful assertion does not independently guarantee complete coverage of every requirement in a complex test case.
- Cross-origin iframes, closed shadow roots, canvas-based applications, file uploads, and complex custom widgets are not fully supported.
- CAPTCHA, MFA, and bot protection may prevent automated login.
- Dynamic interfaces may require additional observations or retries.
- Hosted models are subject to API availability and quota limits.
- Local models depend on available computing resources.
- Hidden and unseen evaluation cases have not been validated.

For implementation details and engineering tradeoffs, see [Approach and Limitations](APPROACH_AND_LIMITATIONS.md).

## Conclusion

English-to-Browser Test Runner demonstrates how a language model can guide browser automation without requiring a separate hardcoded script for each target website.

By combining dynamic page observation, constrained Playwright actions, explicit verification, and structured reporting, the project provides a flexible foundation for natural-language browser testing.
