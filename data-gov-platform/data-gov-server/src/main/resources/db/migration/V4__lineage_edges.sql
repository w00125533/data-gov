create table lineage_edge (
    edge_id varchar(64) primary key,
    source_asset_id varchar(64) not null references data_asset(asset_id) on delete cascade,
    target_asset_id varchar(64) not null references data_asset(asset_id) on delete cascade,
    relation_type varchar(32) not null,
    producer varchar(128),
    process_name varchar(256),
    job_name varchar(256),
    description text,
    properties text,
    active boolean not null default true,
    created_at timestamp not null,
    updated_at timestamp not null
);

create index idx_lineage_edge_source on lineage_edge(source_asset_id);
create index idx_lineage_edge_target on lineage_edge(target_asset_id);
create index idx_lineage_edge_active on lineage_edge(active);
create index idx_lineage_edge_relation_type on lineage_edge(relation_type);

create table lineage_field_edge (
    field_edge_id varchar(64) primary key,
    lineage_edge_id varchar(64) not null references lineage_edge(edge_id) on delete cascade,
    source_field_id varchar(64) references asset_field(field_id) on delete set null,
    target_field_id varchar(64) references asset_field(field_id) on delete set null,
    transform_expression text,
    description text,
    properties text,
    active boolean not null default true,
    created_at timestamp not null,
    updated_at timestamp not null
);

create index idx_lineage_field_edge_lineage on lineage_field_edge(lineage_edge_id);
create index idx_lineage_field_edge_source_field on lineage_field_edge(source_field_id);
create index idx_lineage_field_edge_target_field on lineage_field_edge(target_field_id);
