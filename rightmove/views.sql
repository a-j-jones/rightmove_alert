drop view if exists alert_properties;
drop view if exists properties_current;
drop view if exists start_date;

CREATE VIEW alert_properties as
select
    ap.property_id,
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
    last_rightmove_update as last_update,
    longitude,
    latitude,
    r.emailed,
    r.reviewed_date,
    case when r.reviewed_date = (select max(reviewed_date) from reviewedproperties) then 1 else 0 end as latest_reviewed,
    case when ap.property_id = r.property_id then 1 else 0 end as property_reviewed,
    case when ap.property_id = tp.property_id then 1 else 0 end as travel_reviewed,
    travel_time,
    rp.email_id as review_id,
     (SELECT group_concat(DISTINCT image_url) FROM propertyimages pi WHERE pi.property_id = ap.property_id) as images

from properties_current ap
left join traveltimeprecise tp on ap.property_id = tp.property_id
left join reviewedproperties r on ap.property_id = r.property_id
left join reviewdates rp on r.reviewed_date = rp.reviewed_date
where
    price_amount between 550000 and 850000
    and bedrooms >= 2
    and area > 700
    and not development
    and not commercial
    and not auction
    and lower(summary) like "%garden%"
    and last_rightmove_update > strftime('%Y-%m-%d', datetime(CURRENT_TIMESTAMP, '-60 days'));

CREATE VIEW properties_current as
select
    DATETIME(datetime(), 'localtime') as time,
    pd.*,
    pl.property_channel,
    pl.property_longitude as longitude,
    pl.property_latitude as latitude,
    STRFTIME('%Y-%m-%d', max(coalesce(first_visible, "1970/01/01"), coalesce(last_displayed_update,  "1970/01/01"))) as last_rightmove_update,
    round(julianday(sd.model_date) - julianday(pd.first_visible), 0) as days_old
from propertydata as pd
left join propertylocation as pl on pd.property_id = pl.property_id
left join start_date as sd
where DATETIME(datetime(), 'localtime') between pd.property_validfrom and pd.property_validto;

CREATE VIEW start_date as
    select max(property_validfrom) as model_date
from propertydata;

