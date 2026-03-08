-- base.sql - Core utilities and helpers
-- Must be loaded first as other macros depend on these

-- Resolve a named secret from env (e.g. brave_api_key -> BRAVE_API_KEY)
CREATE OR REPLACE MACRO get_secret(name) AS (
    CASE lower(name)
        WHEN 'brave_api_key' THEN getenv('BRAVE_API_KEY')
        WHEN 'elevenlabs_key' THEN getenv('ELEVENLABS_API_KEY')
        ELSE getenv(upper(replace(name, '-', '_')))
    END
);

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
