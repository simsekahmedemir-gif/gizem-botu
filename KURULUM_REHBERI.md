# Sıfır Maliyetli Otonom Gizem & Tarih Video Fabrikası (v2 - Pexels Anahtarsız / AI Görselli)

Bu sürümde **Pexels API tamamen kaldırılmıştır**. Bunun yerine %100 ücretsiz ve **hiçbir üyelik/API anahtarı istemeyen Pollinations AI** entegre edilmiştir. Sistem her gün kendi yazdığı gizem senaryosuna özel karanlık, sinematik yapay zeka görselleri üretir, seslendirir, altyazı ekler ve YouTube Shorts kanalınıza yükler.

## Kurulum Adımları (Sadece 1 Kez Yapılır)

### 1. Ücretsiz API Anahtarlarını Alın
1. **GEMINI_API_KEY (Senaryo ve Görsel Promptları İçin):**
   - [Google AI Studio](https://aistudio.google.com/) adresine gidin.
   - Sol menüden **"Get API key"** -> **"Create API key"** butonuna tıklayın ve anahtarı kopyalayın.
2. **YouTube API Bilgileri (Otomatik Yükleme İçin):**
   - [Google Cloud Console](https://console.cloud.google.com/) üzerinden yeni bir proje açın ve **YouTube Data API v3**'ü etkinleştirin.
   - **Credentials** menüsünden bir **OAuth 2.0 Client ID** (Web application) oluşturun ve Authorized redirect URI kısmına `https://developers.google.com/oauthplayground` ekleyin.
   - [Google OAuth Playground](https://developers.google.com/oauthplayground) adresine gidin, sağ üstteki çark (Settings) ikonuna tıklayıp *"Use your own OAuth credentials"* kutusunu işaretleyin ve Client ID / Secret bilgilerinizi girin.
   - Sol listeden `https://www.googleapis.com/auth/youtube.upload` iznini seçip **Authorize APIs** deyin ve **Exchange authorization code for tokens** butonuna basarak **`Refresh token`** kodunu kopyalayın.

---

### 2. GitHub'a Yükleyin ve Otomasyonu Başlatın
1. [GitHub](https://github.com/) üzerinde yeni bir Repository oluşturun ve ZIP içindeki dosyaları yükleyin.
2. GitHub deponuzda **Settings** -> **Secrets and variables** -> **Actions** kısmına girin.
3. **New repository secret** butonuna basarak sadece şu **4 anahtarı** ekleyin (Pexels anahtarına artık gerek yok!):
   - `GEMINI_API_KEY`
   - `YT_CLIENT_ID`
   - `YT_CLIENT_SECRET`
   - `YT_REFRESH_TOKEN`
4. Üst menüden **Actions** sekmesine tıklayın, soldan **"Günlük Otomatik Gizem Videosu Üretici (AI Görselli)"** akışını seçin ve **"Run workflow"** butonuna basarak ilk videonuzu hemen test edin!
