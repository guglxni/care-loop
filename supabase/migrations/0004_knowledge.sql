-- One knowledge-document path per chart.
-- source_url is the app path /api/v1/patients/<id>/knowledge.
-- The document itself is generated from the chart on each request.
-- bolna_knowledgebase_id stays null until another step registers the path.
-- Row level security matches 0003: no policy, so anon and authenticated are
-- denied. service_role is granted DML when that role exists.

CREATE TABLE IF NOT EXISTS patient_knowledge_links (
  patient_id uuid PRIMARY KEY REFERENCES patients (id),
  source_url text NOT NULL,
  bolna_knowledgebase_id text,
  last_built_at timestamptz NOT NULL
);

DO $$
DECLARE
  table_name text;
  knowledge_tables text[] := ARRAY['patient_knowledge_links'];
BEGIN
  FOREACH table_name IN ARRAY knowledge_tables
  LOOP
    EXECUTE format(
      'ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY',
      table_name
    );
    EXECUTE format('REVOKE ALL ON TABLE public.%I FROM PUBLIC', table_name);

    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
      EXECUTE format('REVOKE ALL ON TABLE public.%I FROM anon', table_name);
    END IF;

    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
      EXECUTE format(
        'REVOKE ALL ON TABLE public.%I FROM authenticated',
        table_name
      );
    END IF;

    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'service_role') THEN
      EXECUTE format(
        'GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.%I TO service_role',
        table_name
      );
    END IF;
  END LOOP;
END $$;
