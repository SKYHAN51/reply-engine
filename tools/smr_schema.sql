-- ============================================================
-- SMR (Stoppen-Met-Roken) Demo — Supabase Schema
-- Plak dit in Supabase SQL Editor en klik "Run"
-- ============================================================

-- Tabel 1: Patiënten
CREATE TABLE smr_patients (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  naam TEXT NOT NULL,
  email TEXT NOT NULL UNIQUE,
  apotheek TEXT,
  start_datum DATE NOT NULL,
  sigaretten_per_dag INT NOT NULL DEFAULT 20,
  jaren_gerookt INT NOT NULL DEFAULT 10,
  medicatie TEXT,
  treatment_cycle INT DEFAULT 1 CHECK (treatment_cycle IN (1, 2, 3)),
  status TEXT DEFAULT 'actief' CHECK (status IN ('actief', 'gestopt', 'voltooid')),
  dropout_risk_score NUMERIC(5,2) DEFAULT 0,
  dropout_risk_level TEXT DEFAULT 'laag' CHECK (dropout_risk_level IN ('laag', 'matig', 'hoog')),
  non_response_count INT DEFAULT 0,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Tabel 2: Geplande follow-ups
CREATE TABLE smr_followups (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  patient_id UUID REFERENCES smr_patients(id) ON DELETE CASCADE,
  scheduled_date DATE NOT NULL,
  type TEXT NOT NULL CHECK (type IN ('week1', 'week2', 'maand1', 'maand2', 'maand3')),
  sent BOOLEAN DEFAULT FALSE,
  sent_at TIMESTAMPTZ,
  CONSTRAINT chk_sent_consistency CHECK (
    (sent = FALSE AND sent_at IS NULL) OR
    (sent = TRUE AND sent_at IS NOT NULL)
  ),
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Tabel 3: Audit trail + patient mood events + alerts
CREATE TABLE smr_events (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  patient_id UUID REFERENCES smr_patients(id) ON DELETE SET NULL,
  event_type TEXT NOT NULL,
  notes TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Tabel 4: GDPR verwijderlog
CREATE TABLE smr_deletion_log (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email_hash TEXT NOT NULL,
  deleted_at TIMESTAMPTZ DEFAULT NOW(),
  reason TEXT,
  deleted_by TEXT DEFAULT 'apotheker'
);

-- Indices voor performance
CREATE INDEX idx_smr_followups_date ON smr_followups(scheduled_date, sent);
CREATE INDEX idx_smr_patients_risk ON smr_patients(dropout_risk_level, status);
CREATE INDEX idx_smr_events_patient ON smr_events(patient_id, created_at DESC);
CREATE INDEX idx_smr_followups_patient ON smr_followups(patient_id);

-- ============================================================
-- RLS (Row Level Security)
-- ============================================================
ALTER TABLE smr_patients ENABLE ROW LEVEL SECURITY;
ALTER TABLE smr_followups ENABLE ROW LEVEL SECURITY;
ALTER TABLE smr_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE smr_deletion_log ENABLE ROW LEVEL SECURITY;

-- Service key (voor Make.com en Retool): volledige toegang
CREATE POLICY "service_key_all" ON smr_patients FOR ALL USING (true);
CREATE POLICY "service_key_all" ON smr_followups FOR ALL USING (true);
CREATE POLICY "service_key_all" ON smr_events FOR ALL USING (true);
CREATE POLICY "service_key_all" ON smr_deletion_log FOR ALL USING (true);

-- Anon key (voor patiënt mini-app): alleen lezen + events aanmaken
CREATE POLICY "anon_read" ON smr_patients FOR SELECT TO anon USING (true);
CREATE POLICY "anon_insert_events" ON smr_events FOR INSERT TO anon WITH CHECK (true);

-- ============================================================
-- Testdata voor demo (3 patiënten met verschillende risico's)
-- ============================================================
INSERT INTO smr_patients
  (naam, email, apotheek, start_datum, sigaretten_per_dag, jaren_gerookt, medicatie, treatment_cycle, dropout_risk_score, dropout_risk_level, non_response_count)
VALUES
  ('Jan de Vries',  'jan@demo.nl',   'Apotheek Gilze',   CURRENT_DATE - 21, 30, 20, 'Varenicline', 1, 73.0, 'hoog',  2),
  ('Maria Smit',    'maria@demo.nl', 'Apotheek Tilburg', CURRENT_DATE - 14, 15,  8, 'NRT Patch',   1, 45.5, 'matig', 1),
  ('Ahmed Yilmaz',  'ahmed@demo.nl', 'Apotheek Breda',   CURRENT_DATE - 7,  10,  5, 'NRT Kauwgom', 1, 12.0, 'laag',  0);
