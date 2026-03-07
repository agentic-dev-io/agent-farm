-- base.sql - Core utilities and helpers
-- Must be loaded first as other macros depend on these

-- Retrieve a named secret value (stub — replace with vault integration)
CREATE OR REPLACE MACRO get_secret(name) AS 'mock_secret_value';

-- URL-encode a string (percent-encodes space, &, =, ?, #, %)
CREATE OR REPLACE MACRO url_encode(str) AS (
    replace(replace(replace(replace(replace(replace(
        str,
        '%', '%25'),
        ' ', '%20'),
        '&', '%26'),
        '=', '%3D'),
        '?', '%3F'),
        '#', '%23')
);

-- Current UTC timestamp formatted as ISO-8601 string
CREATE OR REPLACE MACRO now_iso() AS (
    strftime(now(), '%Y-%m-%dT%H:%M:%SZ')
);

-- Current UTC timestamp as Unix epoch seconds
CREATE OR REPLACE MACRO now_unix() AS (
    epoch(now())
);
