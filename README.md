## Database

Run these steps once, as the PostgreSQL admin user (`postgres`). The schema script does not create the users, so they must exist before you run it.

Open a `psql` session:

```powershell
psql -U postgres
```

Inside `psql`, create the two users and the database. `\password` asks for the password interactively, so it never ends up in your shell history:

```sql
CREATE ROLE etl_user LOGIN;
CREATE ROLE dashboard_user LOGIN;
\password etl_user
\password dashboard_user
CREATE DATABASE etl_portafolio_db;
\q
```

Then create the tables and permissions:

```powershell
psql -U postgres -d etl_portafolio_db -f sql/01_esquema.sql
```

Use the two passwords you just chose in your `.env` file (`DB_USER` / `DB_PASSWORD` for the ETL, `DASH_DB_USER` / `DASH_DB_PASSWORD` for the dashboard). The usernames must match the ones above.

Permissions follow least privilege: `etl_user` can read, insert and update but not delete, and `dashboard_user` is read-only and cannot see the `email` column.