## Riigikogu API discovery notes

Source: https://www.riigikogu.ee/en/open-data/

Key points:
- Base URL: `https://api.riigikogu.ee`
- JSON API with UUIDs for many entities.
- Example endpoints:
  - `GET /api/votings?startDate=YYYY-MM-DD&endDate=YYYY-MM-DD&lang=et`
  - `GET /api/votings/{uuid}?lang=et`
- Data earlier than 2012 may be incomplete.

Swagger UI is linked from the open data page (may time out on fetch tools).
