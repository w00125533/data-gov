create table asset_event (
    event_id varchar(64) primary key,
    asset_id varchar(64) not null references data_asset(asset_id) on delete cascade,
    event_type varchar(64) not null,
    event_payload text,
    severity varchar(32),
    created_at timestamp not null
);

create index idx_asset_event_asset_id on asset_event(asset_id);
create index idx_asset_event_type on asset_event(event_type);
create index idx_asset_event_created_at on asset_event(created_at);

create table subscription_notification (
    notification_id varchar(64) primary key,
    event_id varchar(64) not null references asset_event(event_id) on delete cascade,
    subscription_id varchar(64) not null references subscription(subscription_id) on delete cascade,
    consumer_id varchar(64) not null references consumer(consumer_id) on delete cascade,
    status varchar(32) not null,
    kafka_topic varchar(256) not null,
    error_message text,
    created_at timestamp not null,
    sent_at timestamp
);

create index idx_subscription_notification_event_id on subscription_notification(event_id);
create index idx_subscription_notification_subscription_id on subscription_notification(subscription_id);
create index idx_subscription_notification_consumer_id on subscription_notification(consumer_id);
create index idx_subscription_notification_status on subscription_notification(status);
