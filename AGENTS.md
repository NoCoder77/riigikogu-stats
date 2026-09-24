# riigikogu_stats

Private repo (may go public later). Riigikogu open-data ETL + local stats API/UI.

## Verify

```powershell
python -m pip install -e ".[dev]"
python -m pytest -q
```

Optional UI: `cd ui && npm install && npm run build`.

Windows one-folder exe: `.\build\build_windows.ps1`.

## Do not commit

`.env`, `*.db`, `ui/node_modules/`, `ui/dist/`, `dist/`.
