import os
import re
import json
import asyncio
import urllib.parse
from io import BytesIO

import requests
import numpy as np
from PIL import Image
import google.generativeai as genai
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
import edge_tts
from moviepy.editor import (
    TextClip, CompositeVideoClip, AudioFileClip, ColorClip, ImageClip,
    concatenate_videoclips,
)

W, H = 1080, 1920

# API Anahtarını Ayarla
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
genai.configure(api_key=GEMINI_API_KEY)


def get_candidate_models():
    """Hesapta kullanılabilir Gemini modellerini, en yeniden eskiye doğru aday listesi olarak döndürür."""
    available = []
    for m in genai.list_models():
        if 'generateContent' in m.supported_generation_methods:
            available.append(m.name)

    print("Hesapta bulunan modeller:", available)

    skip = ['image', 'tts', 'live', 'audio', 'embedding', 'robotics', 'computer-use', 'vision']
    flash = sorted(
        [m for m in available if 'flash' in m and not any(x in m for x in skip)], reverse=True
    )
    pro = sorted(
        [m for m in available if 'pro' in m and not any(x in m for x in skip)], reverse=True
    )

    candidates = []
    if 'models/gemini-flash-latest' in flash:
        candidates.append('models/gemini-flash-latest')
    for m in flash + pro:
        if m not in candidates:
            candidates.append(m)

    if not candidates:
        raise RuntimeError("Kullanılabilir hiçbir Gemini modeli bulunamadı. API anahtarını kontrol edin.")

    return candidates[:10]


def generate_script():
    print("1/5 Gemini ile gizemli senaryo üretiliyor...")

    prompt = """
    YouTube Shorts için çok sürükleyici, kısa ve gizemli bir hikaye senaryosu yaz.
    Hikaye yarım kalmasın, kısa bir giriş, şaşırtıcı bir olay ve vurucu bir finali olsun.
    Konu: Tarihin aydınlatılamamış gizemlerinden, paranormal olaylardan veya tuhaf uzay/doğa olaylarından biri olsun.
    Dil: Türkçe, akıcı ve merak uyandırıcı.
    Senaryo en fazla 600 karakter olsun (yaklaşık 45-55 saniyelik konuşma).

    Yanıtı SADECE aşağıdaki JSON formatında ver:
    {
        "title": "Videonun dikkat çekici başlığı (Maksimum 60 karakter)",
        "description": "Video açıklama metni ve etiketler",
        "script": "Seslendirilecek tam Türkçe metin",
        "image_prompts": [
            "Detailed English prompt 1 for AI image generation, dark cinematic style",
            "Detailed English prompt 2 for AI image generation, dark cinematic style",
            "Detailed English prompt 3 for AI image generation, dark cinematic style"
        ]
    }
    """

    data = None
    last_error = None
    for model_name in get_candidate_models():
        print(f"Model deneniyor: {model_name}")
        try:
            model = genai.GenerativeModel(model_name)
            response = model.generate_content(
                prompt,
                generation_config={"response_mime_type": "application/json", "temperature": 0.8}
            )
            data = json.loads(response.text)
            # Bazen model liste döndürür, ilk elemanı al
            if isinstance(data, list):
                data = data[0]
            _ = data['title'], data['script']
            print(f"Seçilen model: {model_name}")
            break
        except Exception as e:
            print(f"{model_name} çalışmadı: {str(e)[:300]}")
            last_error = e
            data = None

    if data is None:
        raise RuntimeError(f"Hiçbir Gemini modeli çalışmadı. Son hata: {last_error}")

    print(f"Başlık: {data['title']}")
    return data


async def generate_voice(text, output_path="voice.mp3"):
    print("2/5 Edge-TTS ile seslendirme yapılıyor...")
    communicate = edge_tts.Communicate(text, "tr-TR-AhmetNeural")
    await communicate.save(output_path)


def download_image(prompt, index):
    """Ücretsiz Pollinations servisinden AI görsel indirir. Başarısız olursa None döner."""
    url = (
        "https://image.pollinations.ai/prompt/"
        + urllib.parse.quote(prompt)
        + f"?width={W}&height={H}&nologo=true&seed={index + 7}"
    )
    for attempt in range(3):
        try:
            r = requests.get(url, timeout=90)
            if r.status_code == 200 and r.content:
                img = Image.open(BytesIO(r.content)).convert("RGB")
                # Tam 1080x1920'ye ortadan kırparak ölçekle
                scale = max(W / img.width, H / img.height)
                img = img.resize((int(img.width * scale) + 1, int(img.height * scale) + 1))
                left = (img.width - W) // 2
                top = (img.height - H) // 2
                img = img.crop((left, top, left + W, top + H))
                # Altyazı okunsun diye hafif karart
                arr = (np.array(img) * 0.55).astype("uint8")
                return arr
            print(f"Görsel {index + 1} indirilemedi (kod {r.status_code}), tekrar deneniyor...")
        except Exception as e:
            print(f"Görsel {index + 1} hatası: {e}")
    return None


def split_script(text, max_len=110):
    """Metni cümlelere bölüp, ekrana sığacak kısa parçalar halinde gruplar."""
    sentences = [s.strip() for s in re.split(r'(?<=[.!?…])\s+', text.strip()) if s.strip()]
    chunks, current = [], ""
    for s in sentences:
        if current and len(current) + len(s) + 1 > max_len:
            chunks.append(current)
            current = s
        else:
            current = (current + " " + s).strip()
    if current:
        chunks.append(current)
    # Hâlâ çok uzun olan parçaları kelimeden böl
    final = []
    for c in chunks:
        while len(c) > max_len * 1.5:
            cut = c.rfind(" ", 0, max_len)
            cut = cut if cut > 0 else max_len
            final.append(c[:cut])
            c = c[cut:].strip()
        final.append(c)
    return final


def create_video(script_data, audio_path="voice.mp3", output_path="output.mp4"):
    print("3/5 Video montajı hazırlanıyor...")

    audio = AudioFileClip(audio_path)
    duration = audio.duration

    # --- Arka plan görselleri ---
    prompts = script_data.get("image_prompts") or []
    images = []
    for i, p in enumerate(prompts):
        print(f"Görsel {i + 1}/{len(prompts)} üretiliyor...")
        arr = download_image(p, i)
        if arr is not None:
            images.append(arr)

    if images:
        per = duration / len(images)
        bg_clips = [ImageClip(a).set_duration(per) for a in images]
        bg = concatenate_videoclips(bg_clips, method="compose").set_duration(duration)
    else:
        print("Görsel alınamadı, düz arka plan kullanılacak.")
        bg = ColorClip(size=(W, H), color=(10, 10, 10), duration=duration)

    # --- Altyazı parçaları (süre, karakter sayısına göre dağıtılır) ---
    chunks = split_script(script_data['script'])
    total_chars = sum(len(c) for c in chunks) or 1
    layers = [bg]
    t = 0.0
    for c in chunks:
        d = duration * len(c) / total_chars
        txt = (
            TextClip(
                c,
                fontsize=56,
                color='white',
                stroke_color='black',
                stroke_width=2,
                size=(900, None),
                method='caption',
                align='center',
                font='DejaVu-Sans-Bold',
            )
            .set_start(t)
            .set_duration(d)
            .set_position(('center', 'center'))
        )
        layers.append(txt)
        t += d

    video = CompositeVideoClip(layers, size=(W, H)).set_duration(duration)
    video = video.set_audio(audio)

    video.write_videofile(
        output_path,
        fps=24,
        codec='libx264',
        audio_codec='aac',
        preset='ultrafast'
    )
    print("Video başarıyla oluşturuldu!")


def upload_to_youtube(video_file, title, description):
    print("4/5 YouTube'a yükleniyor...")
    client_id = os.environ.get("YT_CLIENT_ID")
    client_secret = os.environ.get("YT_CLIENT_SECRET")
    refresh_token = os.environ.get("YT_REFRESH_TOKEN")

    from google.oauth2.credentials import Credentials
    creds = Credentials(
        None,
        refresh_token=refresh_token,
        client_id=client_id,
        client_secret=client_secret,
        token_uri="https://oauth2.googleapis.com/token"
    )

    youtube = build("youtube", "v3", credentials=creds)

    body = {
        "snippet": {
            "title": title[:90] + " #shorts",
            "description": description + "\n\n#gizem #korkunç #bilgi #shorts",
            "tags": ["gizem", "korkunç", "bilgi", "shorts"],
            "categoryId": "24"
        },
        "status": {
            "privacyStatus": "public",
            "selfDeclaredMadeForKids": False
        }
    }

    media = MediaFileUpload(video_file, chunksize=-1, resumable=True, mimetype="video/mp4")
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"Yükleme yüzdesi: {int(status.progress() * 100)}%")

    print(f"Video başarıyla yüklendi! ID: {response.get('id')}")


if __name__ == "__main__":
    script_data = generate_script()
    asyncio.run(generate_voice(script_data['script']))
    create_video(script_data)
    upload_to_youtube("output.mp4", script_data['title'], script_data['description'])
    print("5/5 Tamamlandı.")
