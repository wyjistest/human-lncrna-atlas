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

# Or use per-service .env files (never commit real values!)
cp frontend/backend/.env.example frontend/backend/.env
cp frontend/web/.env.example frontend/web/.env
# Edit the copied files with your values
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

### Security Hardening (Phase 9.8)

The following security measures were implemented based on Codex security audit:

#### Timing Attack Protection
Admin API key comparison uses `secrets.compare_digest()` for constant-time comparison:
```python
# Prevents timing attacks on API key validation
import secrets
if secrets.compare_digest(provided_key.encode(), expected_key.encode()):
    # Key is valid
```

#### Sensitive Data Protection
All sensitive configuration uses `pydantic.SecretStr` to prevent accidental exposure:
- `DATABASE_PASSWORD`
- `REDIS_PASSWORD`
- `ADMIN_API_KEY`

SecretStr prevents sensitive data from appearing in:
- Log output
- Exception messages
- `repr()` calls
- JSON serialization

#### Cache Namespace Injection Prevention
Cache clear operations validate namespaces against a whitelist:
```python
ALLOWED_CACHE_NAMESPACES = {
    "regulations", "genes", "stats", "export", "conservation",
    "chipseq", "network", "diseases", "features", "igv",
    "analysis", "visualization",
}
NAMESPACE_PATTERN = re.compile(r'^[a-z0-9_-]{1,32}$')
```

#### Input Validation Limits
API endpoints enforce strict input limits to prevent DoS attacks:
- `MAX_COMMA_SEPARATED_ITEMS = 20` - Maximum items in comma-separated lists
- `MAX_ITEM_LENGTH = 50` - Maximum length per item
- `MAX_FIELD_LENGTH = 500` - Maximum total field length
- Chromosome format validation via regex pattern

#### Metrics Endpoint Protection
The `/metrics` endpoint is hidden from OpenAPI schema (`include_in_schema=False`) to reduce attack surface. Additional network-level ACL protection is recommended in production.

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

*Last updated: 2025-12-18*
