# Environment Configuration Guide

This document explains how to configure INXR2 using environment variables.

## Overview

INXR2 uses `.env` files to manage configuration across different environments. This approach:
- Keeps sensitive credentials out of version control
- Allows different configurations per environment
- Follows the [12-factor app](https://12factor.net/) methodology

## Environment Files

### `.env.dev` (Development)
- **Location**: Project root
- **Purpose**: Development defaults with safe, non-sensitive values
- **Version Control**: ✅ Committed to repository
- **Used By**: `docker-compose.dev.yml`

Contains safe development defaults:
```bash
POSTGRES_PASSWORD=inxr2_dev_password  # Safe for development
DEBUG=true
ENVIRONMENT=development
```

### `.env.prod` (Production)
- **Location**: Project root
- **Purpose**: Production secrets and configuration
- **Version Control**: ❌ NEVER commit (in `.gitignore`)
- **Used By**: `docker-compose.yml`
- **Setup**: Create from `.env.prod.example`

Contains sensitive production values:
```bash
POSTGRES_PASSWORD=strong_random_password  # MUST be secure!
SECRET_KEY=random_secret_key
DEBUG=false
ENVIRONMENT=production
```

### `.env.prod.example` (Production Template)
- **Location**: Project root
- **Purpose**: Template for production configuration
- **Version Control**: ✅ Committed to repository
- **Setup**: Copy to `.env.prod` and customize

### `.env.example` (Complete Reference)
- **Location**: Project root
- **Purpose**: Documents ALL available environment variables
- **Version Control**: ✅ Committed to repository
- **Setup**: Reference documentation

## Quick Start

### Development Setup

**No configuration needed!** The project includes `.env.dev` with safe defaults.

```bash
# Just start the containers
docker-compose -f docker-compose.dev.yml up -d
```

### Production Setup

**CRITICAL: Configure environment before deployment!**

```bash
# 1. Create production environment file
cp .env.prod.example .env.prod

# 2. Generate secure passwords
openssl rand -base64 32  # For POSTGRES_PASSWORD
python -c "import secrets; print(secrets.token_urlsafe(32))"  # For SECRET_KEY

# 3. Edit .env.prod with secure values
nano .env.prod

# 4. Build and deploy
docker-compose build
docker-compose up -d
```

## Environment Variables Reference

### Database Configuration

| Variable | Description | Development | Production | Required |
|----------|-------------|-------------|------------|----------|
| `POSTGRES_DB` | Database name | `inxr2_dev` | `inxr2` | ✅ |
| `POSTGRES_USER` | Database user | `inxr2_user` | `inxr2_user` | ✅ |
| `POSTGRES_PASSWORD` | Database password | `inxr2_dev_password` | **CHANGE THIS!** | ✅ |
| `POSTGRES_HOST` | Database host | `postgres` | `postgres` | ✅ |
| `POSTGRES_PORT` | Database port | `5432` | `5432` | ✅ |
| `DATABASE_URL` | Full connection string | Auto-constructed | Auto-constructed | ✅ |
| `PGDATA` | PostgreSQL data directory | `/var/lib/postgresql/data/pgdata` | Same | ✅ |

**Security Note:** Use a strong, randomly-generated password in production:
```bash
openssl rand -base64 32
```

### Application Configuration

| Variable | Description | Development | Production | Required |
|----------|-------------|-------------|------------|----------|
| `ENVIRONMENT` | Environment name | `development` | `production` | ✅ |
| `DEBUG` | Enable debug mode | `true` | `false` | ✅ |
| `LOG_LEVEL` | Logging verbosity | `DEBUG` | `INFO` | ✅ |
| `APP_PORT` | Application port | `8000` | `8000` | ✅ |

**Log Levels:** `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`

### Security (Production Only)

| Variable | Description | Production Value | Required |
|----------|-------------|------------------|----------|
| `SECRET_KEY` | Secret key for sessions, JWT, etc. | **GENERATE RANDOM** | ⚠️ Production |
| `ALLOWED_HOSTS` | Comma-separated allowed domains | `yourdomain.com,www.yourdomain.com` | ⚠️ Production |
| `CORS_ORIGINS` | Comma-separated CORS origins | `https://yourdomain.com` | ⚠️ Production |

**Generate SECRET_KEY:**
```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### Performance (Optional)

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `DB_POOL_SIZE` | Database connection pool size | `10` | ❌ |
| `DB_MAX_OVERFLOW` | Max overflow connections | `20` | ❌ |
| `API_RATE_LIMIT` | Requests per minute | `100` | ❌ |

### Development Settings

| Variable | Description | Development | Required |
|----------|-------------|-------------|----------|
| `WATCHFILES_FORCE_POLLING` | Force file watching via polling | `true` | ✅ Dev only |

Required for Docker on Mac/Windows due to filesystem events.

### Optional Configuration

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `MAX_FILE_SIZE_KB` | Max file size for indexing (KB) | `1024` | ❌ |

## File Priority and Overrides

Docker Compose loads environment variables in this order (later takes precedence):

1. Environment variables from the shell
2. `.env` file in project root (if exists)
3. `env_file` directive in docker-compose.yml (`.env.dev` or `.env.prod`)
4. `environment` section in docker-compose.yml
5. Default values in format `${VAR:-default}`

**Example:**
```yaml
environment:
  POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-changeme}
```
- Uses `POSTGRES_PASSWORD` from `.env.dev` or `.env.prod`
- Falls back to `changeme` if not set

## Security Best Practices

### ✅ DO

1. **Generate strong passwords:**
   ```bash
   openssl rand -base64 32
   ```

2. **Generate unique SECRET_KEY:**
   ```bash
   python -c "import secrets; print(secrets.token_urlsafe(32))"
   ```

3. **Use different credentials per environment:**
   - Development: Safe defaults
   - Staging: Unique credentials
   - Production: Strong, unique credentials

4. **Set appropriate ALLOWED_HOSTS in production:**
   ```bash
   ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com
   ```

5. **Configure CORS_ORIGINS for your frontend:**
   ```bash
   CORS_ORIGINS=https://yourdomain.com,https://www.yourdomain.com
   ```

6. **Keep `.env.prod` secure:**
   - Never commit to version control (already in `.gitignore`)
   - Restrict file permissions: `chmod 600 .env.prod`
   - Store securely (password manager, secrets vault)

### ❌ DON'T

1. ❌ Commit `.env.prod` to version control
2. ❌ Use default passwords in production
3. ❌ Enable DEBUG mode in production
4. ❌ Share `.env.prod` via insecure channels
5. ❌ Reuse passwords across environments
6. ❌ Store secrets in CI/CD logs

## Troubleshooting

### Container Can't Connect to Database

**Symptom:** `connection refused` or `role does not exist`

**Check:**
```bash
# Verify environment variables are loaded
docker-compose -f docker-compose.dev.yml config

# Check database credentials
docker exec inxr2-postgres-dev env | grep POSTGRES
```

**Solution:**
- Ensure `.env.dev` exists
- Verify `DATABASE_URL` matches PostgreSQL credentials
- Check `POSTGRES_HOST` is `postgres` (not `localhost`)

### Variables Not Loading

**Symptom:** Application uses defaults instead of `.env` values

**Check:**
```bash
# View resolved configuration
docker-compose config

# Check environment inside container
docker exec inxr2-dev env | grep POSTGRES
```

**Solution:**
- Ensure `env_file` directive is present in docker-compose.yml
- Restart containers after editing `.env` files:
  ```bash
  docker-compose down
  docker-compose up -d
  ```

### Production Password Issues

**Symptom:** `FATAL: password authentication failed`

**Solution:**
1. Stop containers: `docker-compose down`
2. Remove database volume: `docker volume rm inxr2_postgres_data`
3. Update `.env.prod` with new password
4. Rebuild: `docker-compose up -d`

## Environment File Examples

### Complete `.env.dev` Example

```bash
# Database
POSTGRES_DB=inxr2_dev
POSTGRES_USER=inxr2_user
POSTGRES_PASSWORD=inxr2_dev_password
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
DATABASE_URL=postgresql://inxr2_user:inxr2_dev_password@postgres:5432/inxr2_dev
PGDATA=/var/lib/postgresql/data/pgdata

# Application
ENVIRONMENT=development
DEBUG=true
LOG_LEVEL=DEBUG
APP_PORT=8000

# Development
WATCHFILES_FORCE_POLLING=true
```

### Complete `.env.prod` Example

```bash
# Database - CHANGE THESE!
POSTGRES_DB=inxr2
POSTGRES_USER=inxr2_user
POSTGRES_PASSWORD=xK8mP2vN9qR5wL3jH7bF4tY6uD1eS0zA  # Strong password!
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
DATABASE_URL=postgresql://inxr2_user:xK8mP2vN9qR5wL3jH7bF4tY6uD1eS0zA@postgres:5432/inxr2
PGDATA=/var/lib/postgresql/data/pgdata

# Application
ENVIRONMENT=production
DEBUG=false
LOG_LEVEL=INFO
APP_PORT=8000

# Security - CHANGE THESE!
SECRET_KEY=dGVzdF9zZWNyZXRfa2V5X2NoYW5nZV9tZQ  # Generate random!
ALLOWED_HOSTS=inxr2.example.com,www.inxr2.example.com
CORS_ORIGINS=https://inxr2.example.com,https://www.inxr2.example.com

# Performance (optional)
DB_POOL_SIZE=10
DB_MAX_OVERFLOW=20
API_RATE_LIMIT=100

# Indexing (optional)
MAX_FILE_SIZE_KB=1024
```

## Integration with CI/CD

### GitHub Actions Example

```yaml
# .github/workflows/deploy.yml
name: Deploy to Production

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Create .env.prod from secrets
        run: |
          cat << EOF > .env.prod
          POSTGRES_PASSWORD=${{ secrets.POSTGRES_PASSWORD }}
          SECRET_KEY=${{ secrets.SECRET_KEY }}
          ALLOWED_HOSTS=${{ secrets.ALLOWED_HOSTS }}
          CORS_ORIGINS=${{ secrets.CORS_ORIGINS }}
          # ... other variables
          EOF

      - name: Deploy
        run: docker-compose up -d
```

Store secrets in GitHub Settings → Secrets.

## Additional Resources

- [12-Factor App - Config](https://12factor.net/config)
- [Docker Compose Environment Variables](https://docs.docker.com/compose/environment-variables/)
- [PostgreSQL Environment Variables](https://www.postgresql.org/docs/current/libpq-envars.html)

## Getting Help

- **Development issues:** See `DEVELOPMENT.md`
- **Deployment issues:** See `README.md` → Deployment section
- **Security questions:** Review this document's Security Best Practices section
