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
- **Logs only store counts**,