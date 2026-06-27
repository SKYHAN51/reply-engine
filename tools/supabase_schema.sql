-- ============================================================
-- COACH BOT — Supabase Veritabanı Şeması
-- Supabase SQL Editor'a yapıştır ve "Run" düğmesine bas
-- ============================================================

-- Kullanıcı profili
CREATE TABLE user_profile (
  id BIGSERIAL PRIMARY KEY,
  telegram_user_id TEXT UNIQUE NOT NULL,
  name TEXT,
  goals JSONB DEFAULT '[]',
  coach_notes TEXT DEFAULT '',
  sensitivities TEXT DEFAULT '',
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Konuşma geçmişi
CREATE TABLE conversations (
  id BIGSERIAL PRIMARY KEY,
  telegram_user_id TEXT NOT NULL,
  timestamp TIMESTAMPTZ DEFAULT NOW(),
  user_message TEXT NOT NULL,
  coach_response TEXT NOT NULL,
  is_important BOOLEAN DEFAULT FALSE,
  tags TEXT[] DEFAULT '{}'
);

-- Programlar
CREATE TABLE programs (
  id BIGSERIAL PRIMARY KEY,
  telegram_user_id TEXT NOT NULL,
  program_name TEXT NOT NULL,
  topic TEXT NOT NULL,
  duration_days INTEGER NOT NULL,
  start_date DATE NOT NULL,
  daily_tasks JSONB NOT NULL DEFAULT '[]',
  status TEXT DEFAULT 'active' CHECK (status IN ('active', 'paused', 'completed')),
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Program günlüğü
CREATE TABLE program_logs (
  id BIGSERIAL PRIMARY KEY,
  program_id BIGINT REFERENCES programs(id) ON DELETE CASCADE,
  telegram_user_id TEXT NOT NULL,
  day_number INTEGER NOT NULL,
  task TEXT NOT NULL,
  completed BOOLEAN DEFAULT FALSE,
  user_notes TEXT DEFAULT '',
  scheduled_date DATE NOT NULL,
  rescheduled_to DATE,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- n8n Postgres Chat Memory node için hafıza tablosu
CREATE TABLE IF NOT EXISTS n8n_chat_histories (
  id SERIAL PRIMARY KEY,
  session_id TEXT NOT NULL,
  message JSONB NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Performans için indeksler
CREATE INDEX idx_conversations_user ON conversations(telegram_user_id, timestamp DESC);
CREATE INDEX idx_programs_user_status ON programs(telegram_user_id, status);
CREATE INDEX idx_program_logs_date ON program_logs(telegram_user_id, scheduled_date);
CREATE INDEX idx_chat_histories_session ON n8n_chat_histories(session_id);

-- ============================================================
-- ADIM 2: RLS (Row Level Security) — aynı SQL Editor'da çalıştır
-- ============================================================

ALTER TABLE user_profile ENABLE ROW LEVEL SECURITY;
ALTER TABLE conversations ENABLE ROW LEVEL SECURITY;
ALTER TABLE programs ENABLE ROW LEVEL SECURITY;
ALTER TABLE program_logs ENABLE ROW LEVEL SECURITY;

CREATE POLICY "service_key_all" ON user_profile FOR ALL USING (true);
CREATE POLICY "service_key_all" ON conversations FOR ALL USING (true);
CREATE POLICY "service_key_all" ON programs FOR ALL USING (true);
CREATE POLICY "service_key_all" ON program_logs FOR ALL USING (true);

-- ============================================================
-- ADIM 3: İlk kullanıcı profilini ekle
-- SENIN_TELEGRAM_ID yerine gerçek ID'ni yaz (@userinfobot'tan öğren)
-- ============================================================

INSERT INTO user_profile (telegram_user_id, name, goals, coach_notes)
VALUES (
  '5074570038',
  'Salih',
  '["Manevi gelişim", "İç huzur", "Daha iyi ilişkiler", "Psikolojik farkındalık"]',
  'Hollanda''da yaşıyor (Gelderland). Türkçe konuşuyor, Türk kültüründen. Dini boyut en önemli — İslam yaşamının merkezinde. Psikoloji, felsefe, maneviyat, ilişkiler ilgi alanları. n8n ve AI ile çalışıyor. Pratik ve derinlikli olmayı aynı anda istiyor.'
);

-- ============================================================
-- ÖZGÜVEN SİSTEMİ — 2026-06-17 eklendi
-- ============================================================

-- user_profile'a aşama takibi için yeni kolonlar
ALTER TABLE user_profile
ADD COLUMN IF NOT EXISTS ozguven_stage INT DEFAULT 1,
ADD COLUMN IF NOT EXISTS ozguven_stage_started_at DATE DEFAULT CURRENT_DATE;

-- Konuşmalardan otomatik toplanan güçlü anlar
CREATE TABLE IF NOT EXISTS evidence_bank (
  id BIGSERIAL PRIMARY KEY,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  quote TEXT NOT NULL,
  category TEXT NOT NULL CHECK (category IN ('strength', 'insight', 'achievement', 'belief_shift')),
  stage INT NOT NULL DEFAULT 1,
  conversation_id BIGINT REFERENCES conversations(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_evidence_bank_created ON evidence_bank(created_at DESC);

ALTER TABLE evidence_bank ENABLE ROW LEVEL SECURITY;
CREATE POLICY "service_key_all" ON evidence_bank FOR ALL USING (true);

-- Haftalık gerçek dünya challenge'ları ve takibi
CREATE TABLE IF NOT EXISTS challenge_logs (
  id BIGSERIAL PRIMARY KEY,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  week_start DATE NOT NULL,
  challenge_text TEXT NOT NULL,
  stage INT NOT NULL DEFAULT 1,
  response_monday TEXT,
  response_friday TEXT,
  completed BOOLEAN DEFAULT false
);

CREATE INDEX IF NOT EXISTS idx_challenge_logs_week ON challenge_logs(week_start DESC);

ALTER TABLE challenge_logs ENABLE ROW LEVEL SECURITY;
CREATE POLICY "service_key_all" ON challenge_logs FOR ALL USING (true);
