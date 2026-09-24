# skyhan.app — CEO / Principal Engineer İncelemesi

- **Tarih:** 23 Eylül 2026
- **Kapsam:** `SKYHAN51/skyhan-app` (commit `94746bc`) + sitede vitrine konan demolar (`SKYHAN51/reply-engine`: Reply Engine API, Voice Receptionist)
- **Yöntem:** Kaynak kodun tamamı okundu · `eslint`, `tsc --noEmit`, `next build`, `npm audit`, `npm outdated` · üretim derlemesi yerelde `next start` ile çalıştırıldı · Playwright (Chromium 1194) ile masaüstü 1440×900 ve mobil 390×844 gezinti, 4× CPU kısıtlama, `prefers-reduced-motion`, axe-core 4.x taraması (tam kaydırma sonrası) · API uçları `curl` ile test edildi · demo API test paketi çalıştırıldı (22/22 geçti)
- **Sınırlar:** Canlı `skyhan.app` bu oturumun ağ politikası tarafından engellendi (`skyhan.app:443 → 403`), bu yüzden tüm çalışma zamanı ölçümleri **yerel üretim derlemesine** karşıdır (ağ gecikmesi yok → gerçek dünyada sayılar daha kötü olur). Fontshare (Satoshi) yüklenemedi; ekran görüntülerinde yedek font var. n8n, Telegram, OpenAI, Render, VAPI canlı olarak test edilmedi.
- **Not:** Hukuki başlıklar bilgilendirme amaçlıdır, hukuki tavsiye değildir; bir jurist ile teyit edin.

---

## 1. Yönetici özeti

skyhan.app, gördüğüm en iddialı tek-kişilik portföy sitelerinden biri: özgün bir "yayın kontrol odası" konsepti, disiplinli mühendislik, kanıta dayalı çalışma kültürü (Lighthouse erişilebilirlik 100, CLS 0, güçlü güvenlik başlıkları, belgelenmiş kararlar). **Zanaat sorunu yok.**

Sorun şu: site bir **iş varlığı** olarak, cilanın çözemeyeceği sızıntılara sahip. 6–15 Eylül arasındaki işin büyük kısmı Lighthouse, WebGL ve hareket tasarımına gitmiş; oysa bugün en büyük kaldıraç **güven, dönüşüm ve ölçüm** tarafında:

1. **Sitenin AI chatbot'u, var olmayan üç müşteriyi uydurma sonuçlarla anlatıyor** (SCHARP "no-show %40 → %8", STAHL "conversie +34%", LUMEN). Gerçek amiral projeler (Regie, ZorgNotitie) istemde hiç yok.
2. **Chatbot'la konuşan ziyaretçi iletişim formunda engelleniyor** — üç API rotası tek bir rate-limit sayacını paylaşıyor. Yerelde doğrulandı: 5 chat mesajı → ilk form gönderimi `429`.
3. **Google'a 8 vaka sayfasının hepsinin ana sayfanın kopyası olduğu söyleniyor** (her sayfada `canonical = https://skyhan.app`); LinkedIn'de paylaşılan her vaka linki ana sayfa kartını gösteriyor. Derlenmiş HTML'de doğrulandı.
4. **"Hareketi azalt" ayarlı fare kullanıcıları sitede hiç imleç görmüyor** (`cursor: none !important` + özel imleç reduced-motion'da hiç render edilmiyor). Doğrulandı.
5. **Hukuki boşluklar:** KvK/BTW numarası yok; gizlilik politikası Telegram, OpenAI, Anthropic/n8n, Fontshare ve Vercel'e giden veriyi hiç anmıyor.
6. **Kör uçuş:** Sıfır analitik. Mobilde sayfa **32 ekran** uzunluğunda; her sert yüklemede (vaka sayfalarına doğrudan girişte de) **~4,6–5 sn zorunlu intro** var. Bunların dönüşüme etkisi ölçülemiyor.

İlk dört madde toplam **bir iş günü** civarında düzeltilebilir. Tavsiyem: yeni görsel/hareket işi yapmadan önce 48 saatlik "güven + dönüşüm" sprintini (§9) bitirmek.

---

## 2. Karne

| Alan | Not | Gerekçe |
|---|---|---|
| Görsel özgünlük & zanaat | **9/10** | Tutarlı "Regiekamer" dili, amber/kırmızı disiplini, özenli hareket tasarımı |
| Frontend mühendisliği | **7/10** | Temiz TS, belgelenmiş kararlar; ama hata sınırı yok, şema doğrulaması yok, 10 ölü dosya, test yok |
| Güvenlik | **6,5/10** | CSP/HSTS/COOP/frame-ancestors, origin guard, girdi limitleri iyi; paylaşılan rate-limit hatası, bot koruması yok |
| Mobil performans | **4/10** | Kendi ölçümleriniz: mobil LCP 4–6 sn; ilk JS ~312 KB gzip; 4,6–5 sn intro |
| Erişilebilirlik | **6/10** | Güçlü temel; ama imleç hatası, Kanalen'de 15 kontrast gerilemesi, chat paneli semantiği |
| SEO | **4/10** | Canonical hatası vaka sayfalarını gizliyor; İngilizce başlık; Person şeması zayıf |
| Güven & iddia tutarlılığı | **3/10** | Uydurma chatbot vakaları, kaynaksız "100% tevreden klanten", çelişen durum etiketleri |
| Dönüşüm (lead üretimi) | **3/10** | 32 ekran, fiyat sinyali yok, referans yok, form hatası geri dönüşsüz kayboluyor |
| Hukuk & uyum (NL/AB) | **3/10** | KvK/BTW yok, eksik AVG bilgilendirmesi, üçüncü taraf font, voorwaarden boşlukları |
| Operasyon & ölçüm | **2/10** | Analitik yok, CI yok, manuel deploy + alias, lead'in tek hata noktası Telegram |

---

## 3. Kritik bulgular (P0 — bu hafta)

### K1. Chatbot, var olmayan müşterileri uydurma metriklerle anlatıyor
- **Kanıt:** `src/app/api/chat/route.ts:22-26` sistem istemi:
  - "SCHARP (barbershop): no-show van 40% → 8%"
  - "STAHL (automotive): response time 3 dagen → 4 minuten, conversie +34%"
  - "LUMEN (AI SaaS): demo prep 3 uur → 8 minuten"
  
  Bu üç proje sitenin hiçbir yerinde yok. Görselleri (`public/work/{scharp,stahl,lumen}/*`, ~20 MB) `scripts/generate-assets.mjs` ve `generate-phone-assets.mjs` ile **OpenAI görüntü üretimiyle** oluşturulmuş fotogerçekçi "dashboard" çekimleri. `public/` altında oldukları için herkese açık servis ediliyorlar. Gerçek 8 proje (Regie, ZorgNotitie, Voice Receptionist…) istemde **hiç geçmiyor**.
- **Etki:** "Hangi projeleri yaptınız?" diye soran her potansiyel müşteri uydurma vakalar duyar, sonra sitede bulamaz, referans istediğinde veremezsiniz. Bu; sitenin kendi "Law 1: sahte veri yok" ilkesini (`src/data/slates.ts:1-3`) çiğniyor ve B2B'de yanıltıcı reklam riski taşıyor (art. 6:194 BW). En hızlı güven kaybı senaryosu budur.
- **Çözüm:** Sistem istemini `PROJECTS` ve `PROFILE` verisinden üretin (tek doğruluk kaynağı). SCHARP/STAHL/LUMEN'i istemden, `public/work/`'ten ve üretim script'lerinden kaldırın. Fiyat için net bir kural ekleyin (bkz. Ö2: öneri kartı "Hoeveel kost een project?" diyor ama istemde fiyat bilgisi yok → model ya uydurur ya geçiştirir).
- **Efor:** 1–2 saat.

### K2. Paylaşılan rate-limit sayacı, lead'i dönüşüm anında engelliyor (doğrulandı)
- **Kanıt:** `src/lib/rate-limit.ts:2` tek bir modül-seviyesi `Map`; üç rota da aynı anahtarla çağırıyor: `rateLimit(clientIp(req), …)` — chat 10/dk (`chat/route.ts:43`), contact 5/dk (`contact/route.ts:21`), automation-analyse 3/dk (`automation-analyse/route.ts:16`). Hata veren istekler de sayılıyor.
- **Yerel tekrar üretim (`next start`):**
  - Aynı IP ile 3 chat mesajı → **ilk** ROI analizi: `429 Te veel verzoeken`
  - Aynı IP ile 5 chat mesajı → **ilk** iletişim formu: `429 Te veel verzoeken`
- **Etki:** En ilgili ziyaretçiler (önce AI ile konuşan, sonra yazmaya karar veren) tam dönüşüm anında reddediliyor. Arayüz bunu genel "Er is iets misgegaan" olarak gösteriyor, mesaj 3,5 sn sonra kayboluyor (`Contact.tsx:72-74`), WhatsApp/e-posta alternatifi sunulmuyor. Vercel'de rotalar aynı fonksiyon örneğini paylaştığında (Fluid compute ile olası) aynı etki; her durumda kod yanlış.
- **Çözüm:** Anahtarı ad alanına alın (`` `contact:${ip}` ``); formu en cömert limite koyun; kalıcı limiter (Upstash/Vercel KV veya Vercel Firewall) + formda honeypot/Turnstile. Hata durumunda kalıcı mesaj + "WhatsApp'tan yazın" butonu.
- **Efor:** 30 dk (anahtar) + 2–3 saat (kalıcı limiter + hata UX).

### K3. Canonical ve OpenGraph kök layout'tan miras alınıyor → vaka sayfaları indekslenmiyor, paylaşım önizlemeleri bozuk (doğrulandı)
- **Kanıt:** `src/app/layout.tsx:57-59` `alternates.canonical: "https://skyhan.app"`, `:60-76` sabit `openGraph` (url/başlık/görsel). `src/app/projects/[slug]/page.tsx:10-18` yalnızca `title` ve `description` geçersiz kılıyor. Derlenmiş HTML'de **her sayfa** — 8 vaka, `/rundown`, hatta 404 — şunu yayınlıyor:
  ```html
  <link rel="canonical" href="https://skyhan.app"/>
  <meta property="og:title" content="SKYHAN: Automation Specialist"/>
  <meta property="og:url" content="https://skyhan.app"/>
  ```
- **Etki:** Google'a "bu 8 vaka ana sayfanın kopyası" deniyor → büyük olasılıkla "Alternatif sayfa (uygun canonical ile)" olarak dizin dışı. Sitemap aynı sayfaları öncelik 0.7 ile listeliyor (çelişen sinyal). Voice Receptionist spec'inde birincil lead kanalı olarak geçen **LinkedIn'de her vaka linki ana sayfa kartıyla görünüyor.**
- **Çözüm:** Kökten `alternates.canonical`'ı kaldırıp `page.tsx`'e taşıyın; `generateMetadata` içinde `alternates: { canonical: \`/projects/${slug}\` }` ve `openGraph: { title, description, url, images: [project.image] }` ekleyin (metadataBase zaten tanımlı). `/rundown`, `/privacy`, `/voorwaarden` için de aynısı. Bonus: vaka sayfalarına `CreativeWork`/`Article` JSON-LD.
- **Efor:** 1 saat.

### K4. "Hareketi azalt" kullanan fare kullanıcıları imleç göremiyor (doğrulandı)
- **Kanıt:** `src/app/globals.css:289-291` `@media (pointer: fine) { *, *::before, *::after { cursor: none !important; } }` — hareket tercihinden bağımsız. `src/components/ui/CustomCursor.tsx:131` `if (reduced) return null;`. Playwright + `reducedMotion: "reduce"`: `body`, `a`, `button` hesaplanan imleç `none`, özel imleç yok.
- **Etki:** Vestibüler rahatsızlığı olanlar ve Windows'ta "animasyonları göster" kapalı olanlar dahil, bu kullanıcılar sitede imleci **tamamen kaybediyor**. Ayrıca hidrasyon tamamlanana kadar (yavaş cihazda saniyeler) herkes imleçsiz.
- **Çözüm:** Kuralı `@media (pointer: fine) and (prefers-reduced-motion: no-preference)` ile sınırlayın ve yalnızca `CustomCursor` mount olduktan sonra `<html>`'e eklenen bir sınıfa bağlayın.
- **Efor:** 30 dk.

### K5. Birbiriyle ve marka teziyle çelişen iddialar
Sitenin kimliği "alles echt" ve "automatisch waar mogelijk, gecontroleerd waar nodig". Aşağıdakiler bu kimliği içeriden aşındırıyor:

| İddia | Yer | Sorun |
|---|---|---|
| "100% tevreden klanten" + "Gemeten op productiesystemen" | `Numbers.tsx:14` | Kaynaksız; memnuniyet "üretim sistemlerinde ölçülmez". Kendi kuralınız: kaynaksız sayı yayınlanmaz |
| "0 hallucinaties door RAG" | `projects.ts:172` | Teknik olarak savunulamaz; hakem aynı `gpt-4o-mini` (`reply-engine/demo/api/quality_checker.py`). Teknik alıcı/işe alımcı için kırmızı bayrak |
| "4 AI-agents in < 2 s" | `projects.ts:156`, `slates.ts:95` | Pipeline ≥3 ardışık LLM çağrısı + embedding + 2'ye kadar yeniden deneme (`orchestrator.py`); ayrıca Render'da (ücretsiz katmansa soğuk başlatma 30–60 sn). p50/p95 ölçüp dürüst yayınlayın |
| "PDF… automatisch verwijderd na 1 uur" | `projects.ts:174`, `reply-engine/demo/index.html:813` | `tools/cleanup_uploads.py` var ama **hiçbir şey onu çalıştırmıyor** (Dockerfile/`render.yaml` yalnızca uvicorn). Kodun tutmadığı bir gizlilik sözü |
| "Geen terugkerende kosten" | `projects.ts:161` | Yanlış: her soru OpenAI maliyeti |
| SMR Zorgpad: "Volledig automatisch… apotheker hoeft niets te doen", "risicoscoring op basis van patiëntgedrag" | `projects.ts:108-126`, `slates.ts:34-48` | Marka tezine ve ZorgNotitie'nin "geen risicoscores" duruşuna ters. Sağlık alıcısı için kırmızı bayrak. **Gerçek hastalarla canlıysa:** sağlık verisi (AVG art. 9) + ABD'deki OpenAI → DPIA ve verwerkersovereenkomst gerekir |
| Durum etiketleri | De Wand: tüm projeler "ARCHIEF"; Kanalen: Regie "● LIVE"; `projects.ts`: "Live Demo" | Aynı proje iki bölüm arayla hem "arşiv" hem "canlı" |
| "85+ workflows in productie" (4 kez tekrar) | Services, About, Statement, Numbers | Kimin için? Sitede otomasyon müşterisi görünmüyor. Kanıtlayın (anonim liste) ya da kaldırın |
| "Demo gebouwd voor een loodgietersbedrijf" | `projects.ts:62` | "Snelservice Installatie" kurgusal (`vapi_handler.py:23`) → "een fictief loodgietersbedrijf" deyin |
| Terminal `projects`/`neofetch` | `terminal-commands.ts:89-94, 187-196` | "ULTRA ASSISTANT", "KRAN TTS", "CPU: Claude Sonnet 4.6", "Kernel: Next.js 16.2.1" — gerçek projelerle/sürümle uyuşmuyor |

- **Kök neden:** "Ne yaptım" bilgisinin **en az 6 bağımsız kopyası** var: `projects.ts`, `slates.ts`, `profile.ts`, chat istemi, `terminal-commands.ts`, JSON-LD. Birbirinden sapıyorlar.
- **Çözüm:** Tek bir "iddia kaydı" (claims register) ve tüm yüzeyleri (chat, terminal, rundown, JSON-LD, De Wand, Kanalen) oradan türetin. Kaynağı olmayan her iddia gider.
- **Efor:** Yarım gün.

### K6. Hukuki / uyum boşlukları (NL/AB)
- **KvK ve btw-id yok** (tüm `src/` içinde 0 eşleşme). Bilgi toplumu hizmeti sağlayıcılarının kimlik, adres, e-posta, KvK ve btw numarasını sunması gerekir (art. 3:15d BW). Footer'a ekleyin.
- **Gizlilik politikası eksik (AVG art. 13)** — `src/app/privacy/page.tsx`:
  - İletişim formu verisi **Telegram**'a gidiyor (AB dışı) — anılmıyor.
  - Chat mesajları **OpenAI**'a (ABD) gidiyor — anılmıyor.
  - ROI hesaplayıcı süreç açıklamasını **n8n + Claude/Anthropic**'e gönderiyor — anılmıyor.
  - **Fontshare** her sayfa görüntülemesinde ziyaretçi IP'sini alıyor — anılmıyor (Alman LG München'in 2022 Google Fonts kararıyla aynı mantık; Satoshi'yi self-host etmek hem bunu hem performansı çözer).
  - **Vercel** (barındırma logları) — anılmıyor.
  - Hukuki dayanak (grondslag), üçüncü ülke aktarımı güvenceleri, itiraz/kısıtlama/taşınabilirlik hakları ve **Autoriteit Persoonsgegevens**'e şikâyet hakkı yok.
- **Algemene voorwaarden** (`voorwaarden/page.tsx`):
  - Sorumluluk sınırı "te allen tijde" — kasıt/bilinçli pervasızlık istisnası olmadan bu hâliyle uygulanamaz (art. 6:248 lid 2 BW içtihadı). "behoudens opzet of bewuste roekeloosheid" ekleyin.
  - Müşterilerin müşteri/hasta verisini işleyen otomasyonlar kuruyorsunuz ama **verwerkersovereenkomst (AVG art. 28)** hiç geçmiyor.
  - Barındırma/API giderleri ve bakım (beheer) şartları yok — hem risk hem kaçan tekrarlayan gelir (bkz. §8).
  - Öneri: bir jurist kontrolü veya denetlenmiş bir şablon (örn. NLdigital Voorwaarden + Model Verwerkersovereenkomst).
- **Efor:** Footer 15 dk; gizlilik metni 2–3 saat; voorwaarden jurist ile.

---

## 4. Önemli bulgular (P1 — bu ay)

### Ö1. Konumlandırma: dört kitleye birden konuşmak
"Voor wie" bölümü üç kitle sayıyor — Oprichter (startups/scale-ups), Ondernemer (MKB/ZZP), Beslisser (managers/DMU) — artı Rundown/CV ile işe alımcılar. Portföyün gerçekten kanıtladığı ise: yerel KOBİ siteleri (RMK Autoservice, Karizma), yerel hizmet otomasyonu (Voice Receptionist), insan-onaylı AI (Regie, ZorgNotitie). "Herkes için" = kimse için. Karar vericilere "Geen technische uitleg" deyip 15 bölümün ikisini (Master Control + Stack) teknoloji yığınına ayırmak da bu gerilimin belirtisi. Öneri için §8.

### Ö2. Dönüşüm mimarisi
- **Uzunluk:** Mobilde **27.045 px = 32 ekran**, 15 bölüm, 3 sabitlenmiş (pinned) scroll bölümü. İletişim formu ~30. ekranda.
- **Zorunlu intro:** Her sert yüklemede hero ancak **~5,1 sn** (masaüstü) / **~7,4 sn** (4× CPU) sonra görünüyor. Vaka sayfasına doğrudan girişte de aynı tam ekran intro var (`/projects/zorgnotitie`: `boot-done` 4,56 sn). "Overslaan" yazan görünür bir düğme yok (tıklama/Esc ile atlanabildiği bilgisi hiçbir yerde yazmıyor). LCP metriği (~0,5 sn) bunu gizliyor çünkü intro yazısı LCP sayılıyor.
- **Mobilde kalıcı CTA yok;** chat FAB'ı Kanalen metninin ve Directe Lijn'deki "Lijn 04" butonunun üstüne biniyor (ekran görüntüleriyle doğrulandı).
- **Çelişen yanıt süresi sözleri:** "Reactie binnen 2 uur" (`Contact.tsx:211`, `profile.ts:31`) vs "binnen één werkdag" (`Contact.tsx:230`) vs gizlilikte "5 werkdagen". Tek kişilik bir işletme için "2 saat" riskli bir söz.
- **Form:** Bedrijfsnaam zorunlu (ZZP/bireyler için sürtünme); hata metinleri 9 px (`Contact.tsx:35, 389`); başarı mesajı "**Wij** nemen… contact op" (`:328`) — "Één developer, geen tussenpersonen" markasıyla çelişiyor.
- **Fiyat sinyali sıfır.** Chat öneri kartı "Hoeveel kost een project?" diye soruyor (`ChatWidget.tsx:9`) ama istemde fiyat yok. ROI hesaplayıcı geri ödeme süresini gizli "standaard implementatiekosten"e göre hesaplıyor (`AutomationDemo.tsx:144`) — bu varsayımı açık bir fiyat çapasına çevirin.
- **ROI hesaplayıcı lead'i sızdırıyor:** Sonuçtan sonra "Bespreek mijn situatie →" sadece `#contact`'a atlıyor; ziyaretçi her şeyi yeniden yazmak zorunda. Süreç açıklamasını ve ROI sonucunu forma önceden doldurun.
- **Sosyal kanıt yok:** Rundown dürüstçe "echte naam olmadan quote yok" diyor (`RundownSheet.tsx:107-120`) — doğru ilke; şimdi yapılacak iş RMK ve Karizma'dan isimli 1–2 cümlelik referans almak.
- **Kişisel Gmail** iş iletişim adresi; `info@skyhan.app` hiç kurulmamış (HANDOFF). Alan adlı e-posta ucuz ve büyük güven kazancı.
- **"CV (PDF)"** bir müşteri iletişim "hattı" olarak sunuluyor — iş arayan sinyali; müşteri akışından çıkarıp Rundown'a taşıyın.

### Ö3. Sıfır analitik
Gizlilik sayfası "geen analysediensten" diyor ve bu doğru — ama bu, introyu, bölüm terk oranını, formu, chatbot'u ölçemediğiniz anlamına geliyor. Önceki oturumlarda haftalarca Lighthouse optimize edildi; gerçek ziyaretçi davranışı hakkında tek bir veri noktası yok. Çerezsiz analitik (Vercel Web Analytics, Plausible veya n8n sunucunuzda self-host Umami) + olaylar: `hero_cta`, `whatsapp_click`, `form_submit_{ok,error}`, `chat_open`, `demo_submit`, `case_view`, `demo_outbound_click`.

### Ö4. Lead teslimatında tek hata noktası; deploy'u tek bir sırra bağlayan hata
- İletişim formu **yalnızca Telegram**'a gidiyor (`contact/route.ts:65-81`). Token iptal olursa lead'ler kaybolur; tek iz `console.error`. Kalıcılık yok, uyarı yok, müşteriye otomatik yanıt yok. → Supabase'e yazın (zaten stack'te) + Telegram + e-posta yedeği + başarısızlık alarmı.
- **`OPENAI_API_KEY` olmadan üretim derlemesi çöküyor (doğrulandı):** `chat/route.ts:6` `const client = new OpenAI();` modül seviyesinde → `next build` "Failed to collect page data for /api/chat". Koddaki "anahtar yoksa 503" yolu (`:50-52`) bu yüzden ölü kod; anahtar bir gün silinirse **tüm site deploy edilemez**. İstemciyi handler içinde, env kontrolünden sonra oluşturun.

### Ö5. Mobil performans
- Kendi Phase 0 ölçümleriniz: mobil `/` Perf 49, LCP 5,8 sn, TBT 530 ms; kalan kaldıraç GSAP değerlendirme süresi + intro temposu.
- Bu incelemede: ana sayfa ilk JS **~982 KB ham / ~312 KB gzip** (Three.js hariç; o ayrıca 492 KB / 121 KB gzip, boot sonrası). Mobilde tam kaydırma sonrası 1.488 DOM düğümü, 62 istek, ~815 KB.
- Fontshare stylesheet'i `<head>`'de **render-blocking**; `globals.css:2` yorumu "non-blocking" diyor — yanlış. Self-host Satoshi (`next/font/local`).
- İki animasyon kütüphanesi birden: framer-motion (16 dosya) + GSAP. Çoğu `whileInView` açılışı GSAP/CSS ile yapılabilir.
- **En büyük tek kazanç:** introyu oturum başına bir kez ve yalnızca ana sayfada oynatmak (≤1,2 sn, görünür "Overslaan").

### Ö6. Erişilebilirlik gerilemeleri
- **axe-core: 15 ciddi `color-contrast` ihlali**, hepsi `Projects.tsx:200` Kanalen listesinin pasif satırlarında (`rgba(255,255,255,0.32)` → 2,78:1; 10 px ve 12,5 px). 13 Eylül'deki "Obys tarzı" yeniden yazımla gelmiş — 7 Eylül'deki "0 ihlal" durumundan gerileme.
- Chat paneli: `role="dialog"`/`aria-modal`/odak tuzağı/Esc yok, kapatma düğmesi "✕" etiketsiz (`ChatWidget.tsx:208-214`), mesaj alanında `aria-live` yok (ekran okuyucu yanıtı duymaz), sohbet metni 11 px mono.
- Vaka sayfalarında `#main-content` yok → "Ga naar hoofdinhoud" skip link'i 8 sayfada hedefsiz; ikinci `<nav>` etiketsiz.
- Başlıklar `<br>` yüzünden birleşik okunuyor: "Mijnstack.", "Laten weBouwen.", "Tellen dietellen.", "Dit is voor uals u…". "K-RAN" H3'ü iki kez.

### Ö7. Sağlamlık
- `error.tsx`, `global-error.tsx`, `not-found.tsx` **yok**. 404 = **beyaz arka planlı, İngilizce** Next.js varsayılanı ("This page could not be found"), başlık ana sayfanınki, alt barda "01/14 ON AIR" (ekran görüntüsüyle doğrulandı). "Geen signaal — dit kanaal bestaat niet" konseptinize birebir uyardı.
- `AutomationDemo.tsx:271-274` n8n/LLM yanıtını doğrulamadan state'e koyuyor; `:190` `result.ai.techStack.map` — LLM bozuk JSON döndürürse render hatası → hata sınırı olmadığı için **tüm sayfa beyaz ekran**. `automation-analyse/route.ts:89-90` n8n yanıtını olduğu gibi geçiriyor. → Route'ta zod ile doğrulayın.
- `contact/route.ts:43-47` `as string` cast'leri: `{"name":123}` veya `null` gövde → yakalanmamış `TypeError`, boş gövdeli 500 (doğrulandı).
- JSON olmayan hata yanıtında ham `SyntaxError` mesajı arayüze sızabiliyor (`AutomationDemo.tsx:276`, `ChatWidget.tsx:105`).

### Ö8. Chatbot durumsuz
`ChatWidget.tsx:96-100` yalnızca son mesajı gönderiyor; model konuşma geçmişini görmüyor. Arayüz sohbet gibi görünüyor ama bot her takip sorusunda hafızasız ("Ve bu ne kadar sürer?" bağlamı kaybeder). Son 6 turu sınırlı karakterle gönderin. `#contact` linki vaka sayfalarında çalışmıyor (`renderMessage`).

### Ö9. Mühendislik süreci
- **Lint başarısız:** `scripts/change_colors.js` — `eslint.config.mjs:17` ignore kalıbı `"change_colors.js"` kök dizini hedefliyor, dosya `scripts/` altında. HANDOFF "0 hata" diyor; AGENTS.md'deki commit öncesi kapı (`npm run lint && npm run build`) şu an geçmiyor. Script zaten bozuk (`__dirname/src` arıyor) → silin.
- **Test yok, CI yok.** Repo GitHub'da ama deploy manuel: `vercel deploy --prod` + `vercel alias set` (unutulursa eski sürüm yayında kalır). GitHub → Vercel entegrasyonu (PR başına preview, `main`'e merge = prod) bu adımı ortadan kaldırır.
- **Ölü kod:** 10 dosya hiçbir yerden import edilmiyor: `magnetic-badge.tsx`, `ui/MouseGlow.tsx`, `ui/VelocityText.tsx`, `ui/Marquee.tsx`, `Services/ServiceCard.tsx`, `hooks/useMagnet.ts`, `lib/utils.ts`, `lib/motion.ts`, `lib/tally.ts`, `store/intentStore.ts`. Bu yüzden `clsx`, `tailwind-merge` (yalnızca `utils.ts`) ve `vanilla-tilt` (yalnızca `ServiceCard.tsx`'te tip importu) fiilen kullanılmıyor.
- **Ölü varlıklar:** `public/` 61 MB / 42 görsel; ~35 MB'ı hiçbir yerde referanslı değil (`images/concepts/*`, `Gemini_Generated_Image_*`, `project-webhook-mesh.png`, `project-doc-intel.png`…) + ~20 MB sahte vaka görseli (`public/work/*`).
- `next.config.ts:29, 59` Unsplash'a izin veriyor ama kullanılmıyor. `.npmrc` `legacy-peer-deps=true` peer çakışmalarını gizliyor (kaldırılan R3F/Theatre döneminden kalma olabilir). `eslint-config-next` 16.2.1 vs `next` 16.3.3; `next` 16.3.6 yaması mevcut. `npm audit`: 0 açık ✔.
- README hâlâ `create-next-app` şablonu. `.gitignore` "public repo" diyor, GitHub'da repo private. HANDOFF, `WallScene`'in kendini dispose edip etmediği konusunda kendi içinde çelişiyor.

---

## 5. Küçük bulgular / cila (P2)
- `globals.css:180` `body { padding-bottom: var(--bar-h) }` kuralı `:253`'teki `padding-bottom: env(safe-area-inset-bottom)` tarafından eziliyor (hesaplanan değer `0px`, doğrulandı). Şu an footer'ın kendi 3rem dolgusu tesadüfen kapatıyor.
- `layout.tsx:158` `overflow-x-hidden` sınıfı, HANDOFF'ta "asla hidden kullanma" diye belgelenen kuralla çelişiyor (CSS katmanı sayesinde etkisiz ama yanıltıcı).
- `IntroLoader.tsx:6-8` hâlâ "Plays once per session" diyor; davranış "her yüklemede" (`:33`).
- Hero göz kaşı etiketinde sabit "2026" — Ocak'ta eskimiş görünecek.
- Mobilde "` TERMINAL" ipucu gösteriliyor (dokunmatikte backtick tuşu yok).
- JSON-LD `Person.name: "SKYHAN"` → `"Salih Kayhan"` + `alternateName: "SKYHAN"`; yerel SEO için `ProfessionalService` (areaServed: Gelderland) ekleyin. Başlık İngilizce ("Automation Specialist") — "Workflow-automatisering & AI in Arnhem | SKYHAN" gibi Hollandaca anahtar kelimeli başlık.
- Sitemap'te `lastModified: now` her derlemede değişiyor → Google zamanla lastmod'u yok sayar.
- Vaka sayfası hero'sunda başlık, arkadaki demo ekran görüntüsünün metniyle çakışıyor (Regie); global nav görüntüdeki metnin üstüne biniyor. Daha güçlü gradyan veya metinsiz görsel.
- `Case {index} / 0{PROJECTS.length}` 10+ projede "010" olur.
- `object-cover` ile uzun kaplarda `sizes` değerleri gerçek render boyutunun altında → retina mobilde yumuşak görseller (örn. statement arka planı ~2,6× büyütülüyor, portre ~1,4×).
- Chat yanıtında `#contact` metni link'e çevriliyor ama vaka sayfalarında bu çapa yok.

---

## 6. Demo ekosistemi (`reply-engine`)

Sitenin güvenilirliği, vitrine koyduğu demolarınkinden bağımsız değil.

| # | Bulgu | Kanıt | Öneri |
|---|---|---|---|
| D1 | Yüklenen PDF'in yanıtları hep "Met vriendelijke groet, **GroenTech Services**" ile imzalanıyor | `demo/api/response_drafter.py:11` | Demonun en etkileyici anı ("kendi kennisbank'ını yükle") kurgusal şirket adıyla bozuluyor. Yükleme modunda nötr imza |
| D2 | "1 saat sonra silinir" uygulanmıyor | `tools/cleanup_uploads.py` hiçbir yerde zamanlanmamış; `Dockerfile:6` yalnızca uvicorn | Uygulama içi TTL (her istekte süresi dolanları sil) veya Render cron; ya da iddiayı kaldırın |
| D3 | "Max 5 vraag" yalnızca istemci tarafında | `demo/index.html:977` `alert(...)` | Sunucuda koleksiyon başına sayaç |
| D4 | Dosya boyutu kontrolünden önce tamamı belleğe okunuyor | `demo/api/main.py:167-168` | `Content-Length` kontrolü + parça parça okuma; küçük instance'ta bellek DoS'u önler |
| D5 | Proxy arkasında `get_remote_address` | `main.py:60`, CMD'de `--forwarded-allow-ips` yok | Render'da tüm ziyaretçiler büyük olasılıkla **tek** 10/dk kovasını paylaşıyor → LinkedIn ani trafiğinde demo herkese 429. `FORWARDED_ALLOW_IPS` ayarlayın (doğrulanmalı) |
| D6 | Rezervasyon müsaitlik kontrolü yapmıyor | `demo/voice/api/vapi_handler.py:61-80` önce insert, sonra slotu kapatıyor | Çift rezervasyon + her birine onay SMS'i. Atomik koşullu update veya `(datum, tijdstip)` unique kısıtı |
| D7 | Telefon regex'i her uluslararası numarayı kabul ediyor | `demo/voice/api/models.py:6` | Herkese açık VAPI widget'ı üzerinden premium numaralara SMS (SMS pumping) riski; 40/saat tavanı hasarı sınırlıyor. Demo için yalnızca NL mobil (`^(\+316|06)\d{8}$`) |
| D8 | SMS'te kurgusal firma + "Vragen? Bel **026-1234567**" | `demo/voice/api/sms.py:17-19` | 026 Arnhem alan kodu; numara gerçek bir kişiye/işletmeye ait olabilir. Kendi numaranız veya net "DEMO" etiketi |
| D9 | Barındırma | `demo/index.html:856-858` → `reply-engine-u1no.onrender.com`; projede "€0 (free tiers)" | Ücretsiz katmansa ilk ziyaretçi 30–60 sn soğuk başlatma bekler; sesli asistanın araç çağrıları görüşme ortasında zaman aşımına uğrayabilir. Aktif tanıttığınız demoları sıcak tutun |
| D10 | VAPI public key sayfada | `demo/voice/index.html:147-148` | Normal (public key), ancak VAPI panelinde izinli origin kısıtı + günlük harcama tavanı olduğundan emin olun. `maxDurationSeconds: 300` iyi |

Olumlu: Reply Engine istemleri prompt-injection'a karşı sertleştirilmiş, global maliyet tavanları var (150 LLM/saat, 40 SMS/saat), VAPI kimlik doğrulaması fail-closed, yanıt metni `textContent` ile render ediliyor (XSS yok), **22/22 test geçiyor**, Python bağımlılıkları sabitlenmiş.

---

## 7. İyi olanlar (korunmalı)
- Özgün, tutarlı konsept ve görsel disiplin; "Regiekamer" sözlüğü gerçekten akılda kalıcı.
- Kanıta dayalı mühendislik kültürü: her karar ölçümle belgelenmiş (HANDOFF ve spec'ler örnek niteliğinde).
- Güvenlik başlıkları: CSP (`frame-ancestors 'none'`, `object-src 'none'`), HSTS preload, COOP, Permissions-Policy, `poweredByHeader: false`.
- Yan etkili rotalarda CSRF'e karşı `Sec-Fetch-Site`/`Origin` koruması, girdi uzunluk limitleri, Telegram için HTML kaçışlama.
- CLS 0, Lighthouse SEO/BP yüksek, `tsc` temiz, `npm audit` 0.
- Ziyaretçinin gerçekten kullanabildiği demolar (Regie, ZorgNotitie, Voice) — tek kişilik bir işletmede nadir.
- İnsan-onaylı AI tezi (De Regelkring) — pazarda gerçek bir farklılaştırıcı.
- `/rundown`: yazdırılabilir, JS'siz çalışan tek sayfalık özet.

---

## 8. Stratejik öneriler (CEO perspektifi)

### 8.1 Bir başlangıç pazarı (beachhead) seçin
Portföyünüz iki doğal pazarı kanıtlıyor:
- **A) Yerel hizmet işletmeleri (installateurs, garages, kappers) — "gemiste oproepen → geboekte afspraken":** Acı net (kaçan çağrılar), ROI kolay anlatılır, demo hazır (Voice Receptionist), bölgede iki gerçek müşteri referansı alınabilir (RMK, Karizma). Kısa satış döngüsü.
- **B) Zorg/apotheek — "AI stelt voor, mens beslist":** Daha yüksek değer ve en güçlü farklılaştırıcı (ZorgNotitie, Regie), ama uzun satış döngüsü ve ağır uyum yükü (AVG art. 9, NEN 7510).

Öneri: hızlı gelir için **A**'yı ana sayfanın odağı yapın, **B**'yi amiral vaka/uzmanlık hikâyesi olarak tutun. İşe alımcı kitlesini `/rundown`'a tamamen ayırın.

### 8.2 Teklifi ürünleştirin ve tekrarlayan gelir kurun
- Paketler + fiyat çapası ("vanaf €…"), örn. "Gratis gemiste-oproepen-scan (20 min)" → "AI-receptionist Starter" → "Maatwerk automatisering".
- "Kendi kendine çalışan sistemler" de API değişikliklerinde bozulur: **aylık beheer/bakım aboneliği** hem müşteri için gerçek bir ihtiyaç hem sizin için MRR.
- ROI hesaplayıcının gizli "standaard implementatiekosten"i bu çapanın doğal yeri.

### 8.3 Ana sayfayı ≤8 bölüme indirin
1. **Hero:** hedef müşteriye sonuç odaklı başlık + tek kanıt satırı + birincil CTA (WhatsApp/gesprek) + "Probeer de AI-receptionist live"
2. **Canlı kanıt:** 3 amiral demo (De Wand'ın sadeleştirilmiş hâli)
3. **Teklif/paketler** (fiyat çapalı)
4. **Nasıl çalışır:** De Regelkring (insan onayı = farklılaştırıcı)
5. **Sosyal kanıt:** isimli referanslar + gerçek ticari sonuçlar
6. **Süreç + SSS** (maliyet, bakım, AVG, veri nerede)
7. **Hakkımda** (kısa, insani, portre)
8. **İletişim** (form + WhatsApp + takvim linki)

Master Control + Stack → `/techniek` (teknik alıcılar ve işe alımcılar için). K-RAN → "overig werk".

### 8.4 Kanıt stratejisi
Şu an tüm "sonuçlar" teknik (hash-chain, 4 agent, <2 sn, %100 onay). Alıcı ticari sonuç arar: saat, €, çağrı, rezervasyon. RMK ve Karizma'dan lansman sonrası tek bir gerçek sayı (örn. "X online afspraken/maand") + isimli bir cümle, sitedeki tüm WebGL'den daha çok satar.

### 8.5 Ölçüm ritmi
Haftalık 15 dakikalık gözden geçirme: ziyaretçi → lead dönüşümü, lead → görüşme, görüşme → teklif, kaynak kanal (LinkedIn/Google/doğrudan). İntro ve sayfa uzunluğu kararlarını görüşle değil veriyle verin (A/B: intro var/yok, kısa/uzun sayfa).

### 8.6 Teslimat süreci
GitHub → Vercel entegrasyonu; GitHub Actions'ta `lint` + `tsc` + `build` + Playwright duman testleri (ana sayfa, form sahte backend'e gönderim, chat) + axe + Lighthouse CI bütçeleri. Manuel `alias set` adımı ortadan kalkar; bu incelemedeki gerilemeler (lint, kontrast) otomatik yakalanırdı.

---

## 9. Yol haritası

### 48 saat — "güven + dönüşüm" sprinti (~1–1,5 iş günü)
1. Chat istemi: SCHARP/STAHL/LUMEN'i sil, istemi `PROJECTS`/`PROFILE`'dan üret, fiyat kuralı ekle; `public/work/` ve sahte görsel script'lerini kaldır. (K1)
2. Rate-limit anahtarlarını ad alanına al; form hatasında kalıcı mesaj + WhatsApp yedeği. (K2)
3. Sayfa başına canonical + OpenGraph. (K3)
4. İmleç CSS düzeltmesi. (K4)
5. OpenAI istemcisini handler içine taşı. (Ö4)
6. İddia temizliği: "100% tevreden", "0 hallucinaties", "<2 s" (yeniden ölç), "1 uur verwijderd" (uygula ya da kaldır), durum etiketlerini hizala, "fictief loodgietersbedrijf", "geen terugkerende kosten". (K5)
7. Footer'a KvK + btw-id; tek yanıt süresi sözü; başarı mesajında "ik". (K6, Ö2)
8. Lint ignore yolunu düzelt, `change_colors.js`'i ve ölü dosyaları/varlıkları sil. (Ö9)

### 2–4 hafta
- Çerezsiz analitik + olaylar (Ö3)
- Markalı `not-found.tsx` + `error.tsx`; zod ile API doğrulama (Ö7)
- Kalıcı rate-limit + Turnstile/honeypot; lead'i Supabase'e yazma + alarm + müşteriye otomatik e-posta (K2, Ö4)
- Kanalen kontrast düzeltmesi; chat paneli dialog semantiği + `aria-live` + konuşma geçmişi (Ö6, Ö8)
- İntro: oturumda bir kez, yalnızca ana sayfa, ≤1,2 sn, görünür "Overslaan" (Ö2, Ö5)
- Satoshi'yi self-host et; gizlilik politikasını yeniden yaz; voorwaarden'i jurist'e kontrol ettir (K6, Ö5)
- RMK + Karizma'dan referans; alan adlı e-posta (Ö2)
- Demo düzeltmeleri: GroenTech imzası, upload TTL, atomik rezervasyon, NL-only telefon, akışlı upload limiti, proxy başlıkları (D1–D8)

### Bu çeyrek
- Başlangıç pazarı kararı + ≤8 bölümlük ana sayfa (§8.1, §8.3)
- Ürünleştirilmiş paketler + bakım aboneliği (§8.2)
- Gerçek ticari metrikli 3 derin vaka (§8.4)
- CI/CD + test + performans bütçeleri (§8.6)

---

## 10. Ek — Doğrulama kayıtları

| Kontrol | Sonuç |
|---|---|
| `npx eslint .` | ✖ 2 hata (`scripts/change_colors.js`, `no-require-imports`) |
| `npx tsc --noEmit` | ✔ temiz |
| `npm audit` | ✔ 0 açık |
| `next build` (OPENAI_API_KEY yok) | ✖ `Failed to collect page data for /api/chat` — `route.ts:6` |
| `next build` (sahte anahtarla) | ✔ 20 statik sayfa |
| Derlenmiş HTML canonical | Tüm sayfalarda `https://skyhan.app` (vakalar, rundown, privacy, voorwaarden, 404) |
| Rate-limit (aynı IP) | 3 chat → ilk ROI `429`; 5 chat → ilk form `429` |
| `/api/contact` bozuk girdi | `{"name":123}`, `null` → `TypeError`, 500 |
| Reduced-motion + fare | `cursor: none` (body/a/button), özel imleç yok |
| `body` padding-bottom | `0px` (beklenen `var(--bar-h)` = 48px) |
| Hero görünür oluş | 5,1 sn (masaüstü), 7,4 sn (4× CPU); vaka sayfasına doğrudan giriş: intro 4,56 sn |
| Mobil sayfa uzunluğu | 27.045 px = 32 ekran; 1.488 DOM düğümü; 62 istek / ~815 KB (fontlar hariç) |
| Ana sayfa ilk JS | ~982 KB ham / ~312 KB gzip (+ Three.js 492 KB / 121 KB gzip boot sonrası) |
| axe-core (tam kaydırma) | 15 ciddi `color-contrast` (Kanalen listesi, 2,78:1) |
| `public/` | 61,1 MB / 42 görsel; ~35 MB referanssız + ~20 MB sahte vaka görseli |
| reply-engine `pytest` | ✔ 22/22 |
| Canlı site | Test edilemedi (ağ politikası: `skyhan.app:443 → 403`) |

---

## 11. Güncelleme — 24 Eylül 2026

48 saatlik liste `SKYHAN51/skyhan-app` reposunda `claude/skyhan-app-review-s2j1o6` dalına uygulandı (birleştirilmedi, deploy edilmedi):

- K1 + Ö4: Chat istemi `PROJECTS`/`PROFILE`'dan üretiliyor; SCHARP/STAHL/LUMEN (eski, kullanılmayan konsept vakalar) istemden, `public/work/`'ten ve üretim script'lerinden kaldırıldı. OpenAI istemcisi artık istek başına oluşturuluyor; `next build` anahtarsız da geçiyor.
- K2: Rate-limit anahtarları rotaya göre ayrıldı; form hatası kalıcı ve WhatsApp linkli.
- K3: Sayfa başına canonical + OpenGraph.
- K4: Yerel imleç yalnızca özel imleç yüklüyken gizleniyor.
- K5: Kaynaksız/savunulamaz iddialar kaldırıldı; demolar "LIVE DEMO" etiketli. SMR Zorgpad metni sahibin girdisini bekliyor.
- K6: KvK/btw eklenmedi — işletme henüz kayıtlı değil. Ücretli iş/fatura başladığında KvK kaydı ve footer'a numara eklenmesi gündeme gelir.
- Ö9: Lint yeniden geçiyor; 10 ölü dosya, 3 kullanılmayan bağımlılık ve ~35 MB kullanılmayan görsel silindi.

Doğrulama: `npm run lint` ✔, `next build` (OPENAI_API_KEY olmadan) ✔, derlenmiş HTML'de sayfa başına canonical ✔, 6 chat mesajı sonrası form artık 429 almıyor ✔, reduced-motion'da `cursor: auto` ✔, form hatası 4,5 sn sonra hâlâ görünür ✔.
