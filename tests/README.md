# Browser and visual regression tests

The responsive suite uses Playwright and checks the public landing, login, and
signup pages at 320px, 375px, 768px, and 1024px. It fails when the document
width exceeds the viewport. An optional authenticated smoke test checks the
workspace, composer, Coding Command Center, and captures a mobile screenshot.

Install Playwright in the local development environment, start Django, then run:

```powershell
npx playwright test tests/responsive.spec.js
```

Set `SYNTAX_LOCAL_AI_URL` when Django is not on `http://127.0.0.1:8000`.
Set `SYNTAX_LOCAL_AI_STORAGE` to a Playwright storage-state JSON file to enable
the authenticated workspace check. Browser binaries are not downloaded by the
application and must be provisioned locally; offline environments should use a
preinstalled Playwright browser.
