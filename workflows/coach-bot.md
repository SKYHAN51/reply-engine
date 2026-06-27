# Coach Bot Workflow

## Amaç
Salih için kişisel AI koç Telegram botu. Telegram üzerinden Türkçe sohbet, günlük mesajlar, program yönetimi ve haftalık seans sunar.

## Gerekli Girdiler
- Telegram'dan mesaj (Workflow 1) veya zamanlı tetikleme (Workflow 2-4)

## Araçlar
- `n8n` (skyhan.app) — tüm workflow orkestrasyon
- `OpenAI GPT-4o` — sohbet ve program oluşturma
- `OpenAI GPT-4o Mini` — günlük mesajlar ve check-in (maliyet optimizasyonu)
- `Supabase (PostgreSQL)` — kalıcı hafıza, kullanıcı profili, program takibi
- `Telegram Bot API` — mesajlaşma kanalı

## Workflow'lar

### 1. Coach - Sohbet (7/24 aktif)
**Tetikleyici:** Telegram'dan mesaj geldiğinde
**Akış:**
1. Güvenlik filtresi (sadece Salih'in chat_id'si)
2. Supabase'den kullanıcı profili çek
3. Aktif program kontrol et
4. AI Agent (GPT-4o) sistem promptuyla yanıt üret
5. Konuşmayı Supabase'e kaydet
6. Telegram'a cevap gönder
7. [PROGRAM_OLUSTUR] komutu varsa → Webhook ile Workflow 3'ü tetikle

### 2a. Coach - Sabah Mesajı (08:00, Europe/Amsterdam)
**Tetikleyici:** Her sabah 08:00 otomatik
**Akış:**
1. Aktif program ve profil çek
2. Bugünün görevini hesapla (program varsa)
3. GPT-4o Mini ile kişisel sabah mesajı oluştur
4. Telegram'a gönder, Supabase'e kaydet

### 2b. Coach - Akşam Check-in (21:00, Europe/Amsterdam)
**Tetikleyici:** Her akşam 21:00 otomatik
**Akış:**
1. Bugün tamamlanmamış program görevi var mı kontrol et
2. Varsa: o göreve dair nazik soru üret
3. Yoksa: genel akşam refleksiyon sorusu üret
4. Telegram'a gönder

### 3. Coach - Program Oluştur (Webhook)
**Tetikleyici:** Workflow 1'den webhook çağrısı ([PROGRAM_OLUSTUR] komutu)
**Akış:**
1. GPT-4o ile konu/gün/dakika parametrelerine göre program tasarla
2. Supabase programs tablosuna kaydet
3. Her günü program_logs tablosuna kaydet
4. Kullanıcıya program özetini Telegram'dan gönder

### 4. Coach - Haftalık Seans (Pazartesi 09:00)
**Tetikleyici:** Her pazartesi 09:00
**Akış:**
1. Son 7 günün konuşmaları ve program loglarını çek
2. GPT-4o ile haftalık analiz ve derin soru üret
3. Telegram'a gönder, Supabase'e kaydet (is_important: true)

## Hata Durumu
- OpenAI veya Supabase erişilemezse → Telegram'a "Bir hata oluştu, birazdan tekrar dene 🙏" gider
- n8n Error Workflow aktif — sessiz kalınmaz

## Güvenlik
- Tüm workflow'larda Telegram user_id filtresi aktif
- Sadece Salih'in ID'si (ALLOWED_TELEGRAM_USER_ID) kabul edilir
- API key'ler n8n credentials store'da — workflow içinde görünmez
- Supabase RLS aktif — sadece service key erişim sağlar

## Maliyet Optimizasyonu
- Günlük mesajlar: GPT-4o Mini (ucuz)
- Sohbet, program, haftalık seans: GPT-4o (tam model)
- Hafıza: özet gönderilir, tüm geçmiş değil

## Sistem Promptu
`tools/coach_system_prompt.txt`

## Veritabanı Şeması
`tools/supabase_schema.sql`

## Bağımlılıklar
- Supabase project URL ve service key → `.env`
- Telegram bot token → `.env` ve n8n credentials
- OpenAI API key → n8n credentials
- ALLOWED_TELEGRAM_USER_ID → `.env`

## Sorun Giderme
- Workflow çalışmıyorsa: n8n → Executions → hata detayına bak
- Hafıza siliniyorsa: Simple Memory değil Postgres Chat Memory kullanıldığından emin ol
- Bot cevap vermiyorsa: Telegram webhook'un n8n'e bağlı olduğunu kontrol et
