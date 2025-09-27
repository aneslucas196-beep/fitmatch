# Database Migrations

This directory contains SQL migration scripts for the Coach Fitness application.

## How to apply migrations

### Development Environment

1. Connect to your development database
2. Execute the migration files in order:

```bash
# Apply migration 001
psql -d $DATABASE_URL -f migrations/001_add_profile_completed.sql
```

### Production Environment

**Important:** Always test migrations in a staging environment before applying to production.

1. Take a backup of the production database
2. Apply migrations during a maintenance window
3. Verify the migration was successful

```bash
# Backup first
pg_dump $DATABASE_URL > backup_$(date +%Y%m%d_%H%M%S).sql

# Apply migration
psql -d $DATABASE_URL -f migrations/001_add_profile_completed.sql
```

## Migration Files

- `001_add_profile_completed.sql` - Adds profile_completed boolean field to profiles table for coach onboarding flow

## Notes

- Migrations are designed to be idempotent (safe to run multiple times)
- Each migration includes appropriate error handling with `IF NOT EXISTS` clauses
- Existing data is preserved and backfilled intelligently where appropriate