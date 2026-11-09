# Suggested manual smoke tests

Before running any real-world login test, request legitimate PHPTRAVELS demo credentials at https://phptravels.com/demo.
The PHPTRAVELS page now acts as a demo-access gate. Never publish your username/password in GitHub.

1. No credentials needed (safe starting point):
   `--url https://phptravels.com/demo --test "Verify the PHPTRAVELS live demo page includes a way to get demo access"`
2. Verify a second unrelated website (use a site you control):
   `--url https://your-test-site.example --test "Fill the contact form with sample details and verify confirmation"`
3. Customer login (only if you have working demo credentials and the customer login URL):
   Set `TEST_EMAIL` and `TEST_PASSWORD` in your environment and use:
   `--url https://<your-demo-login-host>/ --test "Log in as the demo customer using {{TEST_EMAIL}} and {{TEST_PASSWORD}}, then verify the customer dashboard is displayed" --allow-domain <the-approved-demo-host>`

Never run destructive tests against production sites without permission.
