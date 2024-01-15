drop view if exists alert_properties;
drop view if exists properties_current;
drop view if exists start_date;


CREATE VIEW start_date as
select max(property_validfrom) as model_date
from propertydata;

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
FROM propertydata AS pd
         LEFT JOIN propertylocation AS pl ON pd.property_id = pl.property_id
         FULL JOIN start_date AS sd ON 1 = 1
WHERE CURRENT_TIMESTAMP BETWEEN pd.property_validfrom AND pd.property_validto;

CREATE VIEW alert_properties AS
SELECT ap.property_id,
       bedrooms,
       bathrooms,
       area,
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
           WHEN r.reviewed_date = (SELECT MAX(reviewed_date) FROM reviewedproperties) THEN 1
           ELSE 0 END                                              AS latest_reviewed,
       CASE WHEN ap.property_id = r.property_id THEN 1 ELSE 0 END  AS property_reviewed,
       CASE WHEN ap.property_id = tp.property_id THEN 1 ELSE 0 END AS travel_reviewed,
       travel_time,
       rp.email_id                                                 AS review_id,
       (SELECT STRING_AGG(DISTINCT image_url, ',')
        FROM propertyimages pi
        WHERE pi.property_id = ap.property_id)                     AS images
FROM properties_current ap
         LEFT JOIN traveltimeprecise tp ON ap.property_id = tp.property_id
         LEFT JOIN reviewedproperties r ON ap.property_id = r.property_id
         LEFT JOIN reviewdates rp ON r.reviewed_date = rp.reviewed_date
WHERE price_amount BETWEEN 550000 AND 850000
  AND bedrooms >= 2
  AND area > 700
  AND NOT development
  AND NOT commercial
  AND NOT auction
  AND LOWER(summary) LIKE '%garden%'
  AND last_rightmove_update > TO_CHAR(CURRENT_DATE - INTERVAL '60 days', 'YYYY-MM-DD');