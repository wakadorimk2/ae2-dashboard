CREATE UNIQUE INDEX IF NOT EXISTS inventory_latest_kind_raw_name_uq
ON public.inventory_latest (kind, raw_name);
