create table data_asset (
    asset_id varchar(64) primary key,
    asset_code varchar(128) not null unique,
    asset_name varchar(256),
    asset_type varchar(32) not null,
    engine varchar(32) not null,
    domain varchar(128),
    owner varchar(128),
    description text,
    lifecycle_status varchar(32) not null,
    schema_version integer not null default 1,
    queryable boolean not null default false,
    federated_queryable boolean not null default false,
    created_at timestamp not null,
    updated_at timestamp not null
);

create index idx_data_asset_type_engine on data_asset(asset_type, engine);
create index idx_data_asset_domain on data_asset(domain);
create index idx_data_asset_lifecycle_status on data_asset(lifecycle_status);

create table asset_field (
    field_id varchar(64) primary key,
    asset_id varchar(64) not null references data_asset(asset_id) on delete cascade,
    field_name varchar(128) not null,
    field_type varchar(128) not null,
    ordinal_position integer,
    nullable boolean not null default true,
    partition_key boolean not null default false,
    primary_key boolean not null default false,
    event_time boolean not null default false,
    description text,
    expression text,
    version integer not null default 1,
    created_at timestamp not null,
    updated_at timestamp not null,
    constraint uk_asset_field_name unique(asset_id, field_name)
);

create index idx_asset_field_asset_id on asset_field(asset_id);
create index idx_asset_field_name on asset_field(field_name);

create table asset_physical_binding (
    binding_id varchar(64) primary key,
    asset_id varchar(64) not null references data_asset(asset_id) on delete cascade,
    engine varchar(32) not null,
    catalog_name varchar(128),
    database_name varchar(128),
    schema_name varchar(128),
    table_name varchar(128),
    topic_name varchar(128),
    format varchar(64),
    location_uri text,
    connection_ref varchar(256),
    query_adapter varchar(64),
    properties text,
    active boolean not null default true,
    created_at timestamp not null,
    updated_at timestamp not null
);

create index idx_asset_binding_asset_id on asset_physical_binding(asset_id);
create index idx_asset_binding_table on asset_physical_binding(catalog_name, database_name, table_name);
create index idx_asset_binding_topic on asset_physical_binding(topic_name);
