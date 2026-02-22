-- base.sql - Core utilities and helpers
-- Must be loaded first as other macros depend on these

CREATE OR REPLACE MACRO get_secret(name) AS 'mock_secret_value';

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

CREATE OR REPLACE MACRO now_iso() AS (
    strftime(now(), '%Y-%m-%dT%H:%M:%SZ')
);

CREATE OR REPLACE MACRO now_unix() AS (
    epoch(now())
);
