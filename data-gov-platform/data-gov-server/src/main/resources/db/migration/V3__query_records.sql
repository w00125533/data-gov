create table query_record (
    query_id varchar(64) primary key,
    request_type varchar(32) not null,
    asset_id varchar(64) references data_asset(asset_id) on delete set null,
    subscription_id varchar(64) references subscription(subscription_id) on delete set null,
    consumer_id varchar(64) references consumer(consumer_id) on delete set null,
    referenced_asset_codes text,
    selected_fields text,
    filter_json text,
    sql_text text,
    rewritten_sql text,
    status varchar(32) not null,
    error_code varchar(64),
    error_message text,
    row_count integer,
    elapsed_ms bigint,
    created_at timestamp not null
);

create index idx_query_record_created_at on query_record(created_at);
create index idx_query_record_subscription_id on query_record(subscription_id);
create index idx_query_record_consumer_id on query_record(consumer_id);
create index idx_query_record_asset_id on query_record(asset_id);
create index idx_query_record_request_type on query_record(request_type);
