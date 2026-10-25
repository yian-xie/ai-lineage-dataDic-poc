SELECT
    DATA:KiwiAcc::VARCHAR(100) AS ACCOUNTNUMBER
FROM {{ source('fixture_raw', 'ACCOUNTS') }}
