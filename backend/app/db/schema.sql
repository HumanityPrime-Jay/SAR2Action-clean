-- SAR2Action user data (Cloud SQL, PostgreSQL 16).
-- Satellite evidence and the law corpus stay as read-only files; only what a signed-in user
-- creates is stored here. Every user-owned row is deleted with its user (ON DELETE CASCADE).

CREATE TABLE IF NOT EXISTS users (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  google_sub    text NOT NULL UNIQUE,              -- Google account ID (the ID token's `sub`)
  email         text NOT NULL,
  name          text,
  role          text NOT NULL DEFAULT 'farmer' CHECK (role IN ('farmer', 'authority')),  -- authority is granted, never self-chosen
  created_at    timestamptz NOT NULL DEFAULT now(),
  last_login_at timestamptz NOT NULL DEFAULT now()
);

-- A farmer's own field for one disaster: the crop they grow, and the field on the map if they picked one.
-- One per disaster. Township and area come from the field itself, so they are not stored.
CREATE TABLE IF NOT EXISTS farmer_fields (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id     uuid NOT NULL REFERENCES users (id) ON DELETE CASCADE,
  event_id    text NOT NULL,                       -- e.g. champi-2026-yunlin
  field_id    text,                                -- e.g. YL-CAND-01; null until a field is picked
  crop        text NOT NULL,                       -- CropKey: rice, garlic, peanut, ... or other
  crop_other  text,                                -- free text when crop = 'other'
  cadastral   text,                                -- land parcel number (段名 + 地號), optional
  created_at  timestamptz NOT NULL DEFAULT now(),
  updated_at  timestamptz NOT NULL DEFAULT now(),
  UNIQUE (user_id, event_id),
  CHECK (crop <> 'other' OR crop_other IS NOT NULL)
);

-- What the relief assistant answered, with the law version it relied on.
CREATE TABLE IF NOT EXISTS assistant_log (
  id           bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  user_id      uuid NOT NULL REFERENCES users (id) ON DELETE CASCADE,
  field_id     text NOT NULL,
  view         text NOT NULL CHECK (view IN ('farmer', 'authority')),
  lang         text NOT NULL DEFAULT 'zh' CHECK (lang IN ('zh', 'en')),
  question     text NOT NULL,
  reply        jsonb NOT NULL,                     -- the AUTHORITY-mode reply as returned
  law_version  text,                               -- applicable_law_version.version
  created_at   timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS assistant_log_user_time ON assistant_log (user_id, created_at DESC);

-- Relief estimates from the official schedule (附表二); an estimate, never an approved amount.
CREATE TABLE IF NOT EXISTS relief_estimates (
  id                bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  user_id           uuid NOT NULL REFERENCES users (id) ON DELETE CASCADE,
  field_id          text NOT NULL,
  crop_item_id      text NOT NULL,                 -- e.g. veg_6
  area_ha           numeric(10, 4) NOT NULL CHECK (area_ha > 0),
  loss_threshold    text NOT NULL,                 -- e.g. meets_20_percent
  result_status     text NOT NULL,
  amount_twd        integer CHECK (amount_twd >= 0),  -- null when the estimate is blocked
  schedule_version  text NOT NULL,                 -- e.g. MOA-RELIEF-SCHEDULE-1150629-V1
  created_at        timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS relief_estimates_user_time ON relief_estimates (user_id, created_at DESC);

-- Sign-in sessions. The browser holds a random token in an HttpOnly cookie; only its SHA-256 is stored.
CREATE TABLE IF NOT EXISTS sessions (
  token_hash  bytea PRIMARY KEY,
  user_id     uuid NOT NULL REFERENCES users (id) ON DELETE CASCADE,
  created_at  timestamptz NOT NULL DEFAULT now(),
  expires_at  timestamptz NOT NULL
);
CREATE INDEX IF NOT EXISTS sessions_user ON sessions (user_id);
