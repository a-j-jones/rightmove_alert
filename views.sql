create table if not exists email_details
(
    email_address varchar(100) not null primary key
);

create table if not exists property_floorplan
(
    property_id   integer not null primary key,
    floorplan_url varchar(1000),
    area_sqft     double precision,
    area_sqm      double precision
);

create table if not exists property_location_excluded
(
    property_id integer not null primary key,
    excluded    boolean
);

create table if not exists property_data
(
    property_id           integer          not null,
    property_validfrom    timestamp        not null,
    property_validto      timestamp        not null,
    bedrooms              integer,
    bathrooms             integer,
    area                  double precision,
    summary               varchar          not null,
    address               varchar          not null,
    property_subtype      varchar,
    property_description  varchar          not null,
    premium_listing       boolean          not null,
    price_amount          double precision not null,
    price_frequency       varchar          not null,
    price_qualifier       varchar,
    lettings_agent        varchar          not null,
    lettings_agent_branch varchar          not null,
    development           boolean          not null,
    commercial            boolean          not null,
    enhanced_listing      boolean          not null,
    students              boolean          not null,
    auction               boolean          not null,
    first_visible         timestamp,
    last_update           timestamp,
    last_displayed_update timestamp,
    primary key (property_id, property_validfrom)
);

create table if not exists property_images
(
    property_id   integer not null,
    image_url     varchar not null,
    image_caption varchar,
    primary key (property_id, image_url)
);

create table if not exists property_location
(
    property_id        serial
        primary key,
    property_asatdt    timestamp,
    property_channel   varchar          not null,
    property_longitude double precision not null,
    property_latitude  double precision not null
);

create table if not exists review_dates
(
    reviewed_date timestamp not null
        primary key,
    email_id      integer,
    str_date      varchar
);

create table if not exists reviewed_properties
(
    property_id   serial
        primary key,
    reviewed_date timestamp not null,
    emailed       boolean   not null
);

create table if not exists travel_time_precise
(
    property_id serial
        primary key,
    travel_time integer
);

drop view if exists properties_review;
drop view if exists alert_properties;
drop view if exists properties_current;
drop view if exists start_date;

CREATE VIEW start_date as
select max(property_validfrom) as model_date
from property_data;

CREATE VIEW properties_current AS
SELECT CURRENT_TIMESTAMP                                                                       AS time,
       pd.*,
       pl.property_channel,
       pl.property_longitude                                                                   AS longitude,
       pl.property_latitude                                                                    AS latitude,
       TO_CHAR(GREATEST(COALESCE(first_visible, '1970-01-01'::timestamp),
                        COALESCE(last_displayed_update, '1970-01-01'::timestamp)),
               'YYYY-MM-DD')                                                                   AS last_rightmove_update,
       ROUND(EXTRACT(EPOCH FROM sd.model_date) - EXTRACT(EPOCH FROM pd.first_visible) / 86400) AS days_old
FROM property_data AS pd
         LEFT JOIN property_location AS pl using (property_id)
         FULL JOIN start_date AS sd ON 1 = 1
WHERE CURRENT_TIMESTAMP BETWEEN pd.property_validfrom AND pd.property_validto;

CREATE VIEW alert_properties AS
SELECT ap.property_id,
       bedrooms,
       bathrooms,
       coalesce(ap.area, pf.area_sqft)                             as area,
       summary,
       address,
       property_subtype,
       property_description,
       price_amount,
       lettings_agent,
       lettings_agent_branch,
       last_rightmove_update                                       AS last_update,
       longitude,
       latitude,
       r.emailed,
       r.reviewed_date,
       CASE
           WHEN r.reviewed_date = (SELECT MAX(reviewed_date) FROM reviewed_properties) THEN 1
           ELSE 0 END                                              AS latest_reviewed,
       CASE WHEN ap.property_id = r.property_id THEN 1 ELSE 0 END  AS property_reviewed,
       CASE WHEN ap.property_id = tp.property_id THEN 1 ELSE 0 END AS travel_reviewed,
       travel_time,
       rp.email_id                                                 AS review_id,
       (SELECT STRING_AGG(DISTINCT image_url, ',')
        FROM property_images pi
        WHERE pi.property_id = ap.property_id)                     AS images
FROM properties_current ap
         LEFT JOIN travel_time_precise tp using (property_id)
         LEFT JOIN property_location_excluded ple using (property_id)
         LEFT JOIN reviewed_properties r using (property_id)
         LEFT JOIN review_dates rp using (reviewed_date)
         LEFT JOIN property_floorplan pf using (property_id)
WHERE price_amount BETWEEN 550000 AND 850000
  AND bedrooms >= 2
  AND (coalesce(ap.area, pf.area_sqft) > 700 or coalesce(ap.area, pf.area_sqft) is null)
  AND NOT development
  AND NOT commercial
  AND NOT auction
  AND LOWER(summary) LIKE '%garden%'
  AND last_rightmove_update > TO_CHAR(CURRENT_DATE - INTERVAL '30 days', 'YYYY-MM-DD')
  AND (not ple.excluded or ple.excluded is null)
  AND (travel_time <= 40 or tp.property_id is null)
;

CREATE VIEW properties_review AS
SELECT *
FROM alert_properties
ORDER BY review_id DESC
;
