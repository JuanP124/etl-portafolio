# Sales ETL: data cleaning with Python, PostgreSQL and Streamlit

An ETL pipeline that takes messy sales data (CSV and Excel), cleans it with explicit rules, loads it into PostgreSQL, and shows the result in a dashboard (*Sales Performance Analytics*).

## The problem it solves

Real-world data rarely arrives clean. This project starts from synthetic data with errors injected on purpose (generated with Faker, no real people or businesses): 200 customers, 15 products and 1,500 sales.

Errors that are fixed or discarded:

- Empty, non-numeric or duplicated IDs.
- Names and cities with extra spaces and inconsistent capitalization.
- Emails with an invalid format.
- Dates in several formats (`2025-10-28`, `27/04/2025`, `27-04-2025`), before 2020, or in the future.
- Amounts written in different ways (`COP 22000`, `$25.500`, `125,000`).
- Quantities that are zero or negative.
- Sales that point to customers or products that do not exist.

## How it works

```
extract (CSV/Excel) -> clean -> save results -> load into PostgreSQL -> dashboard
```

Design decisions:

- **One function per cleaning rule**, small and independent, so each one can be tested on its own.
- **Explicit date formats.** Letting pandas guess can read `10/05/2026` as October 5th; here it is always read as day/month/year.
- **Anything that cannot be fixed is discarded and stored separately** in `data/rejected/`, together with the reason for the rejection.
- **Logs only store counts**, never row contents (no emails or names are logged).
- **Least-privilege database access:** one user for the ETL (no deletes) and a different read-only user for the dashboard, which cannot see the customers' emails.
- **Credentials kept out of the code**, in a `.env` file that is never committed.

## Project structure

```
src/         extract.py, clean.py, load.py, main.py, generar_datos.py
dashboard/   app.py (Streamlit)
sql/         01_esquema.sql
tests/       pytest test suite
data/        raw/ (input), processed/ (clean), rejected/ (discarded)
logs/        run logs
```

Note: code comments, function names and log messages are written in Spanish.

## Installation

From the project folder (Windows, PowerShell):

```powershell
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
Copy-Item .env.example .env
```

Open `.env` and replace the placeholder values (`cambia_esto`) with the ones for your local database. Never commit that file.

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

## Usage

```powershell
python -m src.generar_datos      # creates the messy data in data/raw/
python -m src.main               # extracts, cleans, saves and loads into PostgreSQL
streamlit run dashboard/app.py   # opens the dashboard
```

## Tests

```powershell
pip install -r requirements-dev.txt
pytest
```

The 32 tests cover each cleaning rule, the cleaning of each table, the dropping of sales whose customer or product was rejected, and the saving of the output files.

## Tech stack

Python, pandas, SQLAlchemy, PostgreSQL, Streamlit, Plotly and pytest.