-- MandiCast India SQL practice queries (MySQL 8.0+).
--
-- These templates assume that you separately import a verified AGMARKNET-style
-- CSV into a table named mandi_prices. They do not run against the MandiCast
-- metadata database by default: that database stores dataset/job metadata,
-- while original source files are stored on disk.
--
-- Suggested table columns:
-- arrival_date DATE, state VARCHAR(100), district VARCHAR(100),
-- market VARCHAR(160), commodity VARCHAR(120), variety VARCHAR(120),
-- min_price DECIMAL(14,4), max_price DECIMAL(14,4),
-- modal_price DECIMAL(14,4), arrivals DECIMAL(16,4), unit VARCHAR(60)

-- 1. Latest modal price per commodity and market.
WITH ranked AS (
    SELECT
        commodity, state, district, market, arrival_date, modal_price,
        ROW_NUMBER() OVER (
            PARTITION BY commodity, state, district, market
            ORDER BY arrival_date DESC
        ) AS row_rank
    FROM mandi_prices
    WHERE arrival_date IS NOT NULL AND modal_price IS NOT NULL
)
SELECT commodity, state, district, market,
       arrival_date AS latest_observation_date,
       modal_price AS latest_modal_price
FROM ranked
WHERE row_rank = 1;

-- 2. Monthly average modal price by commodity and state.
SELECT
    STR_TO_DATE(DATE_FORMAT(arrival_date, '%Y-%m-01'), '%Y-%m-%d') AS month,
    state,
    commodity,
    AVG(modal_price) AS average_modal_price,
    COUNT(*) AS observations
FROM mandi_prices
WHERE modal_price IS NOT NULL
GROUP BY month, state, commodity
ORDER BY month, state, commodity;

-- 3. Month-over-month change by commodity and market.
WITH monthly AS (
    SELECT
        STR_TO_DATE(DATE_FORMAT(arrival_date, '%Y-%m-01'), '%Y-%m-%d') AS month,
        commodity, state, market,
        AVG(modal_price) AS average_modal_price
    FROM mandi_prices
    WHERE modal_price IS NOT NULL
    GROUP BY month, commodity, state, market
), lagged AS (
    SELECT *, LAG(average_modal_price) OVER (
        PARTITION BY commodity, state, market ORDER BY month
    ) AS previous_month_price
    FROM monthly
)
SELECT *,
       100.0 * (average_modal_price - previous_month_price)
       / NULLIF(previous_month_price, 0) AS month_over_month_pct
FROM lagged
ORDER BY month, commodity, state, market;

-- 4. Market price dispersion for each commodity.
SELECT
    commodity, state, market,
    COUNT(*) AS observations,
    AVG(modal_price) AS mean_modal_price,
    STDDEV_POP(modal_price) AS price_stddev,
    MIN(modal_price) AS min_observed_price,
    MAX(modal_price) AS max_observed_price
FROM mandi_prices
WHERE modal_price IS NOT NULL
GROUP BY commodity, state, market
HAVING COUNT(*) >= 10
ORDER BY commodity, price_stddev DESC;

-- 5. Potential data-quality checks: nulls, invalid ranges and duplicates.
SELECT
    COUNT(*) AS total_rows,
    SUM(CASE WHEN arrival_date IS NULL THEN 1 ELSE 0 END) AS missing_dates,
    SUM(CASE WHEN modal_price IS NULL THEN 1 ELSE 0 END) AS missing_modal_prices,
    SUM(CASE WHEN min_price > max_price THEN 1 ELSE 0 END) AS inverted_price_ranges,
    SUM(CASE WHEN modal_price < 0 THEN 1 ELSE 0 END) AS negative_modal_prices
FROM mandi_prices;

-- 6. Arrivals-weighted modal-price estimate. Use only if arrivals are valid
-- and comparable within the same commodity/unit/market/time grouping.
SELECT
    STR_TO_DATE(DATE_FORMAT(arrival_date, '%Y-%m-01'), '%Y-%m-%d') AS month,
    state, market, commodity,
    SUM(modal_price * arrivals) / NULLIF(SUM(arrivals), 0)
        AS arrivals_weighted_modal_price,
    SUM(arrivals) AS total_arrivals
FROM mandi_prices
WHERE modal_price IS NOT NULL
  AND arrivals IS NOT NULL
  AND arrivals > 0
GROUP BY month, state, market, commodity
ORDER BY month, state, market, commodity;
