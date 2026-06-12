create table drift_record (
    drift_id varchar(64) primary key,
    drift_type varchar(64) not null,
    asset_id varchar(64) references data_asset(asset_id) on delete set null,
    consumer_id varchar(64) references consumer(consumer_id) on delete set null,
    subscription_id varchar(64) references subscription(subscription_id) on delete set null,
    unique_key varchar(256) not null unique,
    evidence text,
    status varchar(32) not null,
    detected_at timestamp not null,
    resolved_at timestamp
);

create index idx_drift_record_type on drift_record(drift_type);
create index idx_drift_record_status on drift_record(status);
create index idx_drift_record_asset_id on drift_record(asset_id);
create index idx_drift_record_consumer_id on drift_record(consumer_id);
create index idx_drift_record_subscription_id on drift_record(subscription_id);
create index idx_drift_record_detected_at on drift_record(detected_at);
