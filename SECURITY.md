# Security Policy

## Reporting Vulnerabilities

If you discover a security vulnerability in this project, please report it responsibly:

1. **Do NOT** open a public GitHub issue
2. Contact the maintainers directly via email
3. Include detailed steps to reproduce the issue

## Credential Handling

### Never Commit Secrets

The following should **never** be committed to the repository:

- Database passwords
- API keys (including `ADMIN_API_KEY`)
- Private SSH keys
- Cloud provider credentials
- Any `.env` files with real values

### Use Environment Variables

All sensitive configuration should be provided via environment variables:

```bash
# Backend
export DB_PASSWORD="<secure-password>"
export ADMIN_API_KEY="<random-32-char-key>"
export REDIS_PASSWORD="<redis-password>"

# Or use .env file (never commit!)
cp .env.example .env
# Edit .env with your values
```

### Example Files

- `.env.example` files should only contain placeholders like `<YOUR_VALUE>`
- Documentation should use placeholders, not real credentials
- Use `<YOUR_SECURE_PASSWORD>`, `<YOUR_API_KEY>`, `<YOUR_DOMAIN>` patterns

### Pre-commit Checks

Consider adding secret scanning to prevent accidental commits:

```bash
# Install gitleaks
brew install gitleaks  # macOS
# or
apt install gitleaks   # Ubuntu

# Run before commit
gitleaks detect --source . --verbose
```

## Security Configuration

### Production Deployment

Required security settings for production:

```env
# Admin API - MUST enable strict mode
ADMIN_REQUIRE_API_KEY=true
ADMIN_API_KEY=<strong-random-key>

# Trusted proxies (if behind reverse proxy)
TRUSTED_PROXIES=["<nginx-ip>"]

# Rate limiting
RATE_LIMIT_BYPASS_PRIVATE=false
```

### Database Security

1. Use strong, unique passwords (min 16 characters)
2. Restrict network access to trusted IPs
3. Enable SSL/TLS for connections
4. Regular credential rotation

### API Security

- All admin endpoints require API key authentication
- Rate limiting enabled on all public endpoints
- Input validation via Pydantic schemas
- SQL injection prevention via parameterized queries

## Incident Response

If credentials are accidentally exposed:

1. **Immediately rotate** all exposed credentials
2. **Revoke** any active sessions/tokens
3. **Audit** access logs for unauthorized activity
4. **Update** all systems using the compromised credentials
5. **Document** the incident and remediation steps

## Security Updates

This project uses:
- Dependabot for dependency updates
- `pip-audit` for Python vulnerability scanning
- `npm audit` for JavaScript vulnerability scanning

Run security audits regularly:

```bash
# Backend
pip-audit

# Frontend
npm audit
```

---

*Last updated: 2025-12-17*
