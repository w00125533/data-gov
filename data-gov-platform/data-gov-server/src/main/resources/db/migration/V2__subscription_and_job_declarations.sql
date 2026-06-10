create table consumer (
    consumer_id varchar(64) primary key,
    consumer_type varchar(32) not null,
    consumer_name varchar(128) not null,
    owner varchar(128),
    environment varchar(64) not null default 'default',
    runtime_version varchar(128),
    instance_id varchar(256),
    declaration_hash varchar(128),
    last_registered_at timestamp,
    last_seen_at timestamp,
    created_at timestamp not null,
    updated_at timestamp not null,
    constraint uk_consumer_name_env unique(consumer_name, environment)
);

create index idx_consumer_type on consumer(consumer_type);
create index idx_consumer_last_registered_at on consumer(last_registered_at);

create table subscription (
    subscription_id varchar(64) primary key,
    asset_id varchar(64) not null references data_asset(asset_id) on delete cascade,
    consumer_id varchar(64) not null references consumer(consumer_id) on delete cascade,
    usage_mode varchar(32) not null,
    purpose text,
    declared_fields text,
    notify_on text,
    source_type varchar(32) not null,
    declaration_hash varchar(128),
    last_registered_at timestamp,
    last_runtime_seen_at timestamp,
    status varchar(32) not null,
    created_at timestamp not null,
    updated_at timestamp not null,
    constraint uk_subscription_asset_consumer_usage unique(asset_id, consumer_id, usage_mode)
);

create index idx_subscription_asset_id on subscription(asset_id);
create index idx_subscription_consumer_id on subscription(consumer_id);
create index idx_subscription_status on subscription(status);

create table consumer_job (
    job_id varchar(64) primary key,
    consumer_id varchar(64) not null references consumer(consumer_id) on delete cascade,
    job_name varchar(128) not null,
    job_type varchar(32) not null,
    owner varchar(128),
    code_ref text,
    runtime_config text,
    input_asset_codes text,
    output_asset_codes text,
    declaration_hash varchar(128),
    status varchar(32) not null,
    last_registered_at timestamp,
    created_at timestamp not null,
    updated_at timestamp not null,
    constraint uk_consumer_job_name_type unique(consumer_id, job_name, job_type)
);

create index idx_consumer_job_consumer_id on consumer_job(consumer_id);
create index idx_consumer_job_name on consumer_job(job_name);
