ALTER TABLE public.inventory_latest
    ADD COLUMN IF NOT EXISTS world_id TEXT;

UPDATE public.inventory_latest
SET world_id = 'atm9'
WHERE world_id IS NULL;

ALTER TABLE public.inventory_latest
    ALTER COLUMN world_id SET DEFAULT 'atm9';

-- 先にindex（重複チェックにもなる）
DO
$$
DECLARE
    v_conname text;
BEGIN
    -- Check for an existing primary key on (kind, raw_name) and drop it if present
    SELECT c.conname
    INTO v_conname
    FROM pg_constraint c
    JOIN pg_class t ON c.conrelid = t.oid
    JOIN pg_namespace n ON n.oid = t.relnamespace
    JOIN LATERAL (
        SELECT array_agg(a.attnum ORDER BY a.attnum) AS attnums
        FROM pg_attribute a
        WHERE a.attrelid = t.oid
          AND a.attname IN ('kind', 'raw_name')
          AND a.attnum > 0
          AND NOT a.attisdropped
    ) cols ON TRUE
    WHERE n.nspname = 'public'
      AND t.relname = 'inventory_latest'
      AND c.contype = 'p'
      AND c.conkey = cols.attnums
    LIMIT 1;

    IF v_conname IS NOT NULL THEN
        EXECUTE format('ALTER TABLE public.inventory_latest DROP CONSTRAINT %I', v_conname);
    END IF;

    CREATE UNIQUE INDEX IF NOT EXISTS inventory_latest_world_kind_raw_name_uq
        ON public.inventory_latest (world_id, kind, raw_name);
END;
$$;
-- NULL残ってないか確認（任意だけどおすすめ）
SELECT COUNT(*) AS null_world_id
FROM public.inventory_latest
WHERE world_id IS NULL;

-- 最後に NOT NULL
ALTER TABLE public.inventory_latest
    ALTER COLUMN world_id SET NOT NULL;

CREATE TABLE IF NOT EXISTS public.inventory_prev (
    world_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    raw_name TEXT NOT NULL,
    amount_prev BIGINT NOT NULL,
    ts_prev DOUBLE PRECISION NOT NULL,
    PRIMARY KEY (world_id, kind, raw_name)
);

DROP INDEX IF EXISTS inventory_latest_kind_raw_name_uq;
