-- =============================================================================
-- 20260506_002_audit_chain.sql
-- Hash chain inmutable sobre `audit_events` (architecture §8.10).
--
-- Estrategia:
--   prev_hash    = hash del evento anterior (para la misma entity_type+entity_id)
--   current_hash = sha256( prev_hash || event_at || actor_id || entity_type ||
--                          entity_id || action || payload_diff::text )
--
-- El trigger BEFORE INSERT calcula ambos campos — el caller (app o psql) NO
-- los provee. Cualquier intento de UPDATE/DELETE en `audit_events` se bloquea
-- por el trigger `audit_events_immutable_trigger`.
-- =============================================================================

CREATE OR REPLACE FUNCTION audit_events_hash_chain_trigger()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
DECLARE
    v_prev_hash VARCHAR(64);
    v_payload_text TEXT;
BEGIN
    -- 1. Buscar el último hash para esta entidad (cadena por entidad).
    SELECT current_hash INTO v_prev_hash
    FROM audit_events
    WHERE entity_type = NEW.entity_type
      AND entity_id   = NEW.entity_id
      AND event_at    < NEW.event_at
    ORDER BY event_at DESC, id DESC
    LIMIT 1;

    NEW.prev_hash := v_prev_hash;

    -- 2. Computar current_hash = sha256(prev || event_at || actor || ... || payload).
    v_payload_text :=
        COALESCE(NEW.prev_hash, '')
        || COALESCE(NEW.event_at::text, '')
        || COALESCE(NEW.actor_id::text, '')
        || NEW.entity_type
        || NEW.entity_id
        || NEW.action
        || COALESCE(NEW.payload_diff::text, '{}');

    NEW.current_hash := encode(digest(v_payload_text, 'sha256'), 'hex');

    RETURN NEW;
END
$$;

COMMENT ON FUNCTION audit_events_hash_chain_trigger() IS
    'Hash chain SHA-256 sobre audit_events. Caller NO debe setear prev_hash/current_hash.';

-- 3. Trigger BEFORE INSERT en audit_events.
DROP TRIGGER IF EXISTS trg_audit_events_hash_chain ON audit_events;
CREATE TRIGGER trg_audit_events_hash_chain
    BEFORE INSERT ON audit_events
    FOR EACH ROW
    EXECUTE FUNCTION audit_events_hash_chain_trigger();

-- 4. Inmutabilidad: bloquea UPDATE / DELETE.
CREATE OR REPLACE FUNCTION audit_events_immutable_trigger()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'audit_events is append-only — UPDATE/DELETE forbidden (ADR-049)';
END
$$;

DROP TRIGGER IF EXISTS trg_audit_events_no_update ON audit_events;
CREATE TRIGGER trg_audit_events_no_update
    BEFORE UPDATE OR DELETE ON audit_events
    FOR EACH ROW
    EXECUTE FUNCTION audit_events_immutable_trigger();

-- 5. Helper de verificación (TI/Auditoría) — recomputa la cadena para una entidad
-- y devuelve la primera fila donde diverge. NULL = cadena íntegra.
CREATE OR REPLACE FUNCTION audit_events_verify_chain(
    p_entity_type TEXT,
    p_entity_id   TEXT
) RETURNS TABLE (
    broken_id BIGINT,
    broken_at TIMESTAMPTZ,
    expected_hash VARCHAR(64),
    found_hash VARCHAR(64)
) LANGUAGE plpgsql STABLE AS $$
DECLARE
    r RECORD;
    v_prev VARCHAR(64) := NULL;
    v_expected VARCHAR(64);
BEGIN
    FOR r IN
        SELECT id, event_at, actor_id, entity_type, entity_id, action,
               payload_diff, prev_hash, current_hash
        FROM audit_events
        WHERE entity_type = p_entity_type AND entity_id = p_entity_id
        ORDER BY event_at ASC, id ASC
    LOOP
        v_expected := encode(digest(
            COALESCE(v_prev, '')
            || COALESCE(r.event_at::text, '')
            || COALESCE(r.actor_id::text, '')
            || r.entity_type
            || r.entity_id
            || r.action
            || COALESCE(r.payload_diff::text, '{}'),
            'sha256'), 'hex');

        IF r.current_hash IS DISTINCT FROM v_expected
           OR r.prev_hash IS DISTINCT FROM v_prev THEN
            broken_id := r.id;
            broken_at := r.event_at;
            expected_hash := v_expected;
            found_hash := r.current_hash;
            RETURN NEXT;
            RETURN;
        END IF;

        v_prev := r.current_hash;
    END LOOP;
    RETURN;
END
$$;

COMMENT ON FUNCTION audit_events_verify_chain(TEXT, TEXT) IS
    'Verifica integridad de la hash chain para una entidad. Devuelve fila rota o nada.';
