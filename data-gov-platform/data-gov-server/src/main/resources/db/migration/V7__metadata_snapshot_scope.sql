alter table data_asset add column producer_service_name varchar(128);
alter table data_asset add column producer_service_type varchar(32);
alter table data_asset add column producer_environment varchar(64);
alter table data_asset add column producer_owner varchar(128);
alter table data_asset add column declaration_hash varchar(128);
alter table data_asset add column last_declared_instance_id varchar(256);
alter table data_asset add column last_synced_at timestamp;
alter table data_asset add column unregistered_at timestamp;

create index idx_data_asset_producer_scope
    on data_asset(producer_service_name, producer_environment);

create index idx_data_asset_last_synced_at on data_asset(last_synced_at);
