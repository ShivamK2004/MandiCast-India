# Security notes

MandiCast is designed as a local-first portfolio application. It is not a hardened multi-tenant service.

- Uploaded datasets may contain commercially sensitive or personal information. Run the service locally or in a trusted private environment.
- Do not commit uploaded files, local databases, generated model artifacts, or `.env` secrets. The `.gitignore` excludes the standard runtime locations.
- The API limits file upload size and stores uploaded files beneath generated UUID directories.
- Before public deployment, add authentication and authorization, per-user dataset ownership, malware scanning, rate limiting, secure secret management, audit logging, encryption at rest, and retention/deletion policies.
- Restrict CORS to the actual frontend origin in any deployed environment.
- Rotate the PostgreSQL password and use a managed secret rather than the local example value.

Report security issues privately to the project maintainer rather than publishing exploit details.
