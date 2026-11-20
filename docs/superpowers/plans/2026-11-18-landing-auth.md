# Landing integration and account access

User-approved scope: import the supplied Desktop landing page into this course project, connect it to the existing workspace, and add real sign-in backed by a database.

- Copy source and assets into `landing/`; preserve the Desktop source. Exclude dependencies, generated output, actual environment files and Git metadata.
- Serve the landing at `/`, dedicated account pages at `/login` and `/signup`, and the existing workspace at `/app/`. Give workspace assets a `/app/` base to avoid collisions with landing assets. Landing hash navigation stays independent.
- Use the existing local SQLite database. Add users with salted scrypt password hashes, expiring login sessions with hashed random tokens, and session ownership. Use HttpOnly SameSite cookies. Add origin checks and bounded sign-in attempts.
- First account created on this local installation atomically adopts existing unowned debates. Subsequent accounts see only their own data. Protect every discussion, correction, export and voice endpoint, including cached discussions and WebSocket access.
- Replace the landing's sign-in preview with real forms using its existing light lavender visual language. Include register, login, logout, remember-me, validation and useful error states. Keep credentials out of browser storage and source files.
- Verify registration, password checks, cookie persistence/revocation, cross-user denial, migration, existing workflows, both production builds and HTTP routing. The user will inspect visuals; do not spend time on visual QA.
- Leave the live app at first-account setup so the user chooses their own credentials. Do not create a test account in the real database.
