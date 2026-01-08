CREATE UNIQUE INDEX IF NOT EXISTS inventory_latest_world_kind_raw_name_uq
ON public.inventory_latest (world_id, kind, raw_name);
