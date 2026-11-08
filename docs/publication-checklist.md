# Public Repository Publication Checklist

Use this checklist before publishing new content, code, screenshots, commits or sample data.

## Ownership and rights

- [ ] Is this my original work, or do I have permission to redistribute it?
- [ ] No proprietary slides, teacher solutions, internal LMS exports or restricted exercise text.
- [ ] Third-party code, images and datasets are attributed and licensed appropriately.

## Privacy and security

- [ ] No API keys, credentials, tokens, private keys, connection strings or recovery material.
- [ ] No real personal, student, instructor, customer, employer or company-case data without a clear right to publish.
- [ ] No private email, Teams/Moodle links with access tokens, internal addresses or account identifiers.
- [ ] Example configuration uses placeholders and synthetic data.
- [ ] Local .env files, development settings, certificates, database files and generated outputs remain untracked.
- [ ] Check staged changes and commit history; .gitignore alone does not remove already tracked secrets.

## Technical accuracy

- [ ] README distinguishes working code from plans.
- [ ] Instructions to run and test the example have been tried where possible.
- [ ] Screenshots and diagrams accurately reflect the current implementation.
- [ ] Performance, security and cloud-cost claims have evidence or are labeled as estimates.
- [ ] No unverified claim of certification, course completion, production readiness or deployment.

## Before a public release or showcase link

- [ ] Review the final Git diff and repository visibility.
- [ ] Verify sensitive information is absent from code, configuration, logs and screenshots.
- [ ] Confirm course or company case-study publication restrictions.
- [ ] Provide a concise explanation of the problem, architecture, tests and limitations.

If a secret was committed, treat it as exposed: revoke or rotate it, then clean up the repository history as appropriate. Ignoring the file afterward is not sufficient.
