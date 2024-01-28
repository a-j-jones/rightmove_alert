CREATE TABLE IF NOT EXISTS email_details
(
    email_address varchar(100) NOT NULL PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS property_floorplan
(
    property_id   integer NOT NULL PRIMARY KEY,
    floorplan_url varchar(1000),
    area_sqft     double precision,
    area_sqm      double precision
);

CREATE TABLE IF NOT EXISTS property_summary
(
    property_id integer NOT NULL PRIMARY KEY,
    summary     varchar(10000),
    garden      varchar(50)
);

CREATE TABLE IF NOT EXISTS property_location_excluded
(
    property_id integer NOT NULL PRIMARY KEY,
    excluded    boolean
);

CREATE TABLE IF NOT EXISTS property_data
(
    property_id           integer          NOT NULL,
    property_validfrom    timestamp        NOT NULL,
    property_validto      timestamp        NOT NULL,
    bedrooms              integer,
    bathrooms             integer,
    area                  double precision,
    summary               varchar          NOT NULL,
    address               varchar          NOT NULL,
    property_subtype      varchar,
    property_description  varchar          NOT NULL,
    premium_listing       boolean          NOT NULL,
    price_amount          double precision NOT NULL,
    price_frequency       varchar          NOT NULL,
    price_qualifier       varchar,
    lettings_agent        varchar          NOT NULL,
    lettings_agent_branch varchar          NOT NULL,
    development           boolean          NOT NULL,
    commercial            boolean          NOT NULL,
    enhanced_listing      boolean          NOT NULL,
    students              boolean          NOT NULL,
    auction               boolean          NOT NULL,
    first_visible         timestamp,
    last_update           timestamp,
    last_displayed_update timestamp,
    PRIMARY KEY (property_id, property_validfrom)
);

CREATE TABLE IF NOT EXISTS property_images
(
    property_id   integer NOT NULL,
    image_url     varchar NOT NULL,
    image_caption varchar,
    PRIMARY KEY (property_id, image_url)
);

CREATE TABLE IF NOT EXISTS property_location
(
    property_id        serial
        PRIMARY KEY,
    property_asatdt    timestamp,
    property_channel   varchar          NOT NULL,
    property_longitude double precision NOT NULL,
    property_latitude  double precision NOT NULL
);

CREATE TABLE IF NOT EXISTS review_dates
(
    reviewed_date timestamp NOT NULL
        PRIMARY KEY,
    email_id      integer,
    str_date      varchar
);

CREATE TABLE IF NOT EXISTS reviewed_properties
(
    property_id   serial
        PRIMARY KEY,
    reviewed_date timestamp NOT NULL,
    emailed       boolean   NOT NULL
);

CREATE TABLE IF NOT EXISTS travel_time_precise
(
    property_id serial
        PRIMARY KEY,
    travel_time integer
);

DROP VIEW IF EXISTS properties_review;
DROP VIEW IF EXISTS alert_properties;
DROP VIEW IF EXISTS properties_enhanced;
DROP VIEW IF EXISTS properties_current;
DROP VIEW IF EXISTS start_date;

CREATE VIEW start_date AS
SELECT
    MAX(property_validfrom) AS model_date
FROM
    property_data;

CREATE VIEW properties_current AS
SELECT
    CURRENT_TIMESTAMP AS time,
    pd.*,
    pl.property_channel,
    pl.property_longitude AS longitude,
    pl.property_latitude AS latitude,
    TO_CHAR(GREATEST(COALESCE(first_visible, '1970-01-01'::timestamp),
                     COALESCE(last_displayed_update, '1970-01-01'::timestamp)),
            'YYYY-MM-DD') AS last_rightmove_update,
    ROUND(EXTRACT(EPOCH FROM sd.model_date) - EXTRACT(EPOCH FROM pd.first_visible) / 86400) AS days_old
FROM
    property_data AS pd
        LEFT JOIN property_location AS pl USING (property_id)
        FULL JOIN start_date AS sd ON 1 = 1
WHERE
    CURRENT_TIMESTAMP BETWEEN pd.property_validfrom AND pd.property_validto;


CREATE VIEW properties_enhanced AS
SELECT
    ap.property_id,
    ap.bedrooms,
    ap.bathrooms,
    COALESCE(ap.area, pf.area_sqft) AS area,
    ps.garden,
    ap.summary,
    ap.address,
    ap.property_subtype,
    ap.property_description,
    ap.price_amount,
    ap.lettings_agent,
    ap.lettings_agent_branch,
    ap.last_rightmove_update AS last_update,
    ap.longitude,
    ap.latitude,
    r.emailed,
    r.reviewed_date,
    CASE
        WHEN r.reviewed_date = (SELECT MAX(reviewed_date) FROM reviewed_properties) THEN 1
        ELSE 0 END AS latest_reviewed,
    CASE WHEN ap.property_id = r.property_id THEN 1 ELSE 0 END AS property_reviewed,
    CASE WHEN ap.property_id = tp.property_id THEN 1 ELSE 0 END AS travel_reviewed,
    ple.excluded AS location_excluded,
    tp.travel_time,
    rp.email_id AS review_id,
    (SELECT STRING_AGG(DISTINCT image_url, ',') FROM property_images pi WHERE pi.property_id = ap.property_id) AS images
FROM
    properties_current ap
        LEFT JOIN travel_time_precise tp USING (property_id)
        LEFT JOIN property_location_excluded ple USING (property_id)
        LEFT JOIN reviewed_properties r USING (property_id)
        LEFT JOIN review_dates rp USING (reviewed_date)
        LEFT JOIN property_floorplan pf USING (property_id)
        LEFT JOIN property_summary ps USING (property_id)
WHERE
      NOT ap.development
  AND NOT ap.commercial
  AND NOT ap.auction
  AND ap.last_rightmove_update > TO_CHAR(CURRENT_DATE - INTERVAL '30 days', 'YYYY-MM-DD')
;


CREATE VIEW alert_properties AS
SELECT
    *
FROM
    properties_enhanced
WHERE
      price_amount BETWEEN 550000 AND 850000
  AND LOWER(summary) LIKE '%garden%'
  AND bedrooms >= 2
  AND (area > 700 OR area IS NULL)
  AND (NOT location_excluded OR location_excluded IS NULL)
  AND (travel_time <= 40 OR travel_time IS NULL)
  AND (
          LOWER(summary) LIKE '%garden%'
              OR LOWER(summary) LIKE '%patio%'
              OR LOWER(summary) LIKE '%terrace%'
              OR LOWER(summary) LIKE '%yard%'
          )
  AND (garden IN ('private', 'unknown') OR garden IS NULL)
;

CREATE VIEW properties_review AS
SELECT
    *
FROM
    alert_properties
ORDER BY
    review_id DESC
;
