
# Approach and Limitations

## Objective

The objective of this project is to execute browser tests written in natural language without requiring a separate automation script for each website.

The system receives a starting URL and a plain-English test case, observes the current webpage, and uses a language model to determine appropriate browser actions.

Playwright executes those actions, returns execution feedback, and allows the model to continue until the test is completed or an execution limit is reached.

The implementation prioritizes website independence, controlled execution, explicit verification, and traceable test results.

## Technical Approach

### 1. Dynamic Page Observation

The browser agent observes the currently loaded webpage using a JavaScript-based DOM snapshot.

The observation includes:

- Current page URL and title
- Visible headings
- A limited excerpt of webpage text
- Visible interactive elements
- Element roles and accessible names
- Input types and relevant attributes

Interactive elements receive temporary references such as `e1`, `e2`, and `e3`.

These references are regenerated during page observations instead of relying on fixed HTML IDs, classes, or website-specific selectors.

The agent can also use semantic role/name locators where appropriate.

This approach allows the same automation engine to operate on multiple websites without embedding individual websites' DOM structures into the source code.

### 2. Language Model Integration

The application supports two inference backends:

**Gemini API**

Provides hosted language-model inference through Google's API.

**Ollama**

Provides local language-model inference through a locally running Ollama server.

Both providers are accessed through `model_client.py`.

The model receives:

- The original natural-language test instruction
- The latest page observation
- Recent execution history and feedback

It returns a structured JSON action representing the next operation to perform.

The runner executes only supported actions rather than arbitrary code returned by the model.

### 3. Browser Execution

Browser automation is implemented using Playwright.

Supported operations include:

- Navigation to approved websites
- Clicking elements
- Filling text inputs
- Selecting native dropdown options
- Checking controls
- Pressing permitted keyboard keys
- Brief waits
- Explicit assertions

The agent observes the page again after each operation.

This feedback-driven approach allows subsequent actions to depend on the current webpage state.

### 4. Assertion-Based Verification

A central design requirement is distinguishing successful browser actions from successful test verification.

For example, filling an input field does not by itself prove that the expected value is present.

The runner therefore supports explicit assertions.

| Assertion | Verification |
|---|---|
| `assert_visible` | Element or text is visible |
| `assert_not_visible` | Element or text is hidden or absent |
| `assert_url` | Current URL contains expected text |
| `assert_title` | Page title contains expected text |
| `assert_value` | Input value exactly matches expected text |
| `assert_selected_option` | Selected native dropdown label exactly matches expected text |

Visibility checks are not treated as equivalent to value verification.

For example, verifying that an input is visible does not establish that its value equals `Aaron`.

Likewise, verifying that the text `Two` appears inside a dropdown does not necessarily establish that `Two` is selected.

The dedicated assertion actions address these differences.

### 5. PASS/FAIL Decision Logic

The runner applies assertion-based safeguards to the final outcome.

An overall PASS requires:

1. At least one successful explicit assertion.
2. A model-generated completion decision requesting PASS.
3. No recorded failed assertion actions.

If an assertion fails, the failure is recorded and cannot be overridden by a subsequent successful assertion.

If the agent reaches its maximum step count without verified completion, it returns FAIL.

This prevents several common false-positive scenarios.

However, the system still relies on the language model to determine which assertions are relevant to the original goal.

Consequently, a successful assertion does not independently prove that every requirement in a complex natural-language test has been checked.

## Error Handling

### Browser Action Failures

Playwright exceptions are captured and recorded in the execution history.

Examples include:

- Missing elements
- Element interaction timeouts
- Invalid dropdown options
- Failed assertions
- Unsupported actions

The agent records the failure information for reporting and subsequent decision-making.

### Assertion Failures

Failed assertion actions are tracked independently from successful assertions.

This ensures that an unsuccessful verification cannot be silently overridden by later successful checks.

### API Rate Limits

Hosted model providers may enforce request and token quotas.

When the Gemini API returns HTTP 429, the runner terminates execution with an explanation indicating that the API rate limit or quota was exceeded.

This avoids repeatedly consuming agent steps on requests that are unlikely to succeed.

An API quota error is an execution limitation and does not establish that the target website failed its functional requirements.

## Reporting

Each execution produces a structured JSON report containing:

- Original test instruction
- Overall PASS/FAIL status
- Completion or failure reason
- Number of successful assertions
- Step-by-step action history
- Final webpage URL

When execution fails, the runner also attempts to capture a screenshot.

Reports are stored in the configured report directory.

Entered values are masked in action history, and configured secrets are redacted from recorded feedback where supported.

Screenshots and webpage observations may still contain sensitive information and must be handled appropriately.

## Security Considerations

### Domain Allowlisting

The runner permits navigation to the starting website's hostname.

Additional hostnames must be explicitly approved using `--allow-domain`.

This limits unintended navigation, although it is not equivalent to complete browser network isolation.

### Restricted Action Set

The language model cannot directly execute arbitrary shell commands or arbitrary JavaScript through the supported action interface.

The runner accepts only predefined browser actions.

### Destructive Operations

Certain payment, purchase, deletion, and transfer-related actions are blocked by default.

The `--allow-destructive` option provides explicit opt-in for authorized testing environments.

This safeguard uses heuristic checks and does not guarantee detection of every destructive operation.

### Credential Handling

Supported test credentials are provided through environment variables.

Placeholder substitution allows the browser to use those credentials without placing their underlying values directly into model instructions.

API keys and credentials must not be committed to source control.

Testing should be limited to websites and accounts for which authorization has been granted.

## Validation

### Automated Regression Tests

The project was tested on Windows with Python 3.12.

**Result: 10 automated tests passed.**

The regression tests cover:

1. Model response parsing.
2. Secret placeholder substitution.
3. Host allowlisting.
4. Browser execution using a scripted model.
5. Rejection of PASS without successful assertions.
6. Exact input-value and dropdown verification.
7. Rejection of incorrect input values.
8. Rejection of incorrect dropdown selections.
9. Rejection of visibility assertions used as value checks.
10. Prevention of PASS following a previously failed assertion.

The automated tests use local HTML fixtures and scripted model responses, allowing deterministic verification without consuming hosted API quota.

### Live Browser Tests

Live execution was also performed using Gemini and Playwright.

The test scenarios included:

- Detecting demo-access functionality on PHPTRAVELS.
- Reporting FAIL for nonexistent webpage text.
- Entering and verifying an exact text-input value.
- Selecting and verifying a native dropdown option.
- Completing a multi-step test with two successful assertions.
- Reporting FAIL when one requirement succeeded but another deliberately impossible requirement was not satisfied.

These tests demonstrated successful execution of the supported workflows on public webpages.

They do not establish reliability across all possible websites or unseen evaluation scenarios.

## Known Limitations

### 1. Model-Dependent Decisions

The language model determines which actions and assertions to perform.

It may misunderstand instructions, identify incorrect controls, or select insufficient verification steps.

The implementation does not independently decompose every natural-language goal into mandatory requirements.

### 2. Incomplete Goal Coverage

Although assertion failures prevent an overall PASS, the system cannot guarantee that every clause of a complex test instruction was verified.

A production implementation would benefit from explicit requirement tracking and independent verification coverage.

### 3. DOM Coverage

The current observation system focuses on visible controls in the top-level DOM.

It does not fully support:

- Cross-origin iframes
- Closed shadow roots
- Canvas-based interfaces
- Complex custom components
- File uploads

### 4. Dynamic Webpages

Webpage elements may change between observations and actions.

Temporary references are refreshed during observation, but disappearing or ambiguous controls can still cause interaction failures.

### 5. Advanced Interactions

Native dropdowns and standard form controls are supported.

More complex interactions, including drag-and-drop, custom dropdown widgets, rich text editors, and hover-dependent interfaces, may require additional capabilities.

### 6. Authentication Restrictions

Login automation requires legitimate credentials and authorization.

CAPTCHA, MFA, bot protection, and missing demo credentials may prevent completion.

The runner does not attempt to bypass these protections.

### 7. Model Availability and Performance

Gemini API execution depends on network connectivity, provider availability, and project quotas.

Local Ollama inference avoids hosted API quotas but can be slower on systems without dedicated GPU acceleration.

### 8. Privacy

Webpage observations are supplied to the selected model provider.

Generated reports and screenshots may expose information visible in the browser.

Confidential or production systems require additional privacy and security review before use.

### 9. Unseen Test Cases

The implementation has been validated against local regression fixtures and selected public webpages.

Its behavior on arbitrary unseen test cases is not guaranteed.

## Potential Improvements

Possible future enhancements include:

- Independent decomposition of natural-language instructions into verifiable requirements.
- Tracking assertion coverage against every required condition.
- Separating application failures from infrastructure and model-provider errors.
- Retry policies with exponential backoff for transient API failures.
- Support for additional browser controls and iframe interactions.
- More detailed execution traces and diagnostic reporting.
- Broader evaluation across websites with different DOM structures.

These improvements are outside the current implementation.

## Summary

The project demonstrates a practical approach to natural-language browser testing using Playwright and a language model.

Its architecture separates page observation, model-directed decisions, browser execution, assertion evaluation, and reporting.

Explicit assertions, constrained actions, and failure tracking improve result reliability while retaining flexibility across different websites.

The implementation remains a prototype with clearly defined limitations, particularly around model decisions, complex webpage interactions, and complete verification of multi-part test instructions.
