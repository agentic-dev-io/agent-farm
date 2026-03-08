# base.sql

Core utilities; loaded first (other macros depend on these).

| Macro | Description |
|-------|-------------|
| `get_secret(name)` | Secret value (stub; replace with vault integration) |
| `url_encode(str)` | URL-encode string (space, `&`, `=`, `?`, `#`, `%`) |
| `now_iso()` | Current UTC timestamp as ISO-8601 string |
| `now_unix()` | Current UTC timestamp as Unix epoch (float) |
