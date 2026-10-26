import os
import json
import time
import urllib.parse
import subprocess
import requests
from google import genai
from google.genai import types
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# =====================================================================
# 1. SENARYO VE GÖRSEL PROMPT ÜRETİMİ (Google Gemini API - Ücretsiz)
# =====================================================================
def generate_mystery_script():
    print("[1/5] Gemini API ile Gizem/Tarih senaryosu ve AI görsel promptları üretiliyor...")
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    
    prompt = """
    Sen viral bir YouTube Shorts / TikTok 'Gizem, Tarih ve Komplo/İlginç Bilgiler' içerik üreticisisin.
    Bana yaklaşık 40-50 saniyelik (ortalama 100-120 kelimelik), izleyiciyi ilk 3 saniyede ekrana kilitleyecek (kuvvetli bir Hook ile başlayan), 
    az bilinen karanlık bir tarihi olay, gizemli bir vaka veya ilginç bir bilimsel/tarihi gerçek hakkında Türkçe bir video metni yaz.

    Kurallar:
    - Metin doğrudan konuşma diliyle, akıcı ve merak uyandırıcı olmalı.
    - Asla "Merhaba arkadaşlar" gibi girişler yapma, doğrudan vurucu bir soru veya şok edici bir gerçekle başla.
    - Sonunda izleyiciyi yorum yapmaya teşvik eden gizemli bir soru sor (Örn: "Sizce bu bir tesadüf müydü?").
    
    Yanıtı SADECE aşağıdaki JSON formatında ver:
    {
      "title": "Videonun dikkat çekici başlığı (Maksimum 60 karakter, #shorts #gizem #tarih etiketleri dahil)",
      "description": "Video açıklama metni ve etiketler",
      "script": "Seslendirilecek tam Türkçe metin (noktalama işaretlerine dikkat et)",
      "image_prompts": [
        "Detailed English prompt 1 for AI image generation, dark cinematic mystery style, vertical 9:16",
        "Detailed English prompt 2 for AI image generation, dark cinematic historical mystery style, vertical 9:16",
        "Detailed English prompt 3 for AI image generation, eerie atmospheric cinematic lighting, vertical 9:16",
        "Detailed English prompt 4 for AI image generation, hyperrealistic dark mystery, vertical 9:16"
      ]
    }
    Not: image_prompts kısmı yapay zeka görsel üreticisi için İNGİLİZCE, detaylı ve sinematik/karanlık atmosferli betimlemeler olmalı. Görsel içinde yazı (text) olmamalı.
    """

    response = client.models.generate_content(
        model="gemini-1.5-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.8
        )
    )
    
    data = json.loads(response.text)
    print(f"Başlık: {data['title']}")
    return data

# =====================================================================
# 2. SESLENDİRME VE ALTYAZI ÜRETİMİ (Edge-TTS - %100 Ücretsiz)
# =====================================================================
def generate_voice_and_subs(script_text, audio_path="voice.mp3", subs_path="subs.srt"):
    print("[2/5] Edge-TTS ile seslendirme ve altyazı oluşturuluyor...")
    voice = "tr-TR-AhmetNeural"
    
    cmd = [
        "edge-tts",
        "--voice", voice,
        "--rate=+5%",
        "--pitch=-5Hz",
        "--text", script_text,
        "--write-media", audio_path,
        "--write-subtitles", subs_path
    ]
    subprocess.run(cmd, check=True)
    print("Ses ve altyazı başarıyla oluşturuldu.")

# =====================================================================
# 3. YAPAY ZEKA GÖRSEL ÜRETİMİ (Pollinations AI - API Key Gerektirmez!)
# =====================================================================
def generate_ai_images(prompts, count=4):
    print("[3/5] Pollinations AI ile dikey (9:16) yapay zeka görselleri üretiliyor (API Key gerekmez)...")
    downloaded_images = []

    for idx, prompt in enumerate(prompts[:count]):
        encoded_prompt = urllib.parse.quote(f"{prompt}, dark cinematic lighting, photorealistic, 8k, no text")
        seed = int(time.time()) + idx * 100
        url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1080&height=1920&seed={seed}&nologo=true"
        
        filename = f"scene_{idx}.jpg"
        for attempt in range(3):
            try:
                res = requests.get(url, timeout=60)
                if res.status_code == 200:
                    with open(filename, "wb") as f:
                        f.write(res.content)
                    downloaded_images.append(filename)
                    print(f"Görsel üretildi: {filename}")
                    break
            except Exception as e:
                print(f"Görsel indirme denemesi {attempt+1} başarısız, tekrar deneniyor... ({e})")
                time.sleep(3)

    if not downloaded_images:
        raise Exception("Görseller üretilemedi!")
    return downloaded_images

# =====================================================================
# 4. VİDEO KURGU, HAREKETLİ EFEKT VE ALTYAZI GÖMME (FFmpeg / MoviePy)
# =====================================================================
def assemble_video(images, audio_path="voice.mp3", subs_path="subs.srt", output_path="final_short.mp4"):
    print("[4/5] Görseller, ses ve altyazı birleştiriliyor...")
    from moviepy.editor import ImageClip, AudioFileClip, concatenate_videoclips

    audio = AudioFileClip(audio_path)
    total_duration = audio.duration + 0.5
    clip_duration = total_duration / len(images)

    processed_clips = []
    for img_path in images:
        clip = ImageClip(img_path).set_duration(clip_duration)
        clip = clip.resize((1080, 1920))
        processed_clips.append(clip)

    final_video = concatenate_videoclips(processed_clips, method="compose")
    final_video = final_video.set_audio(audio)
    temp_video = "temp_no_subs.mp4"
    
    final_video.write_videofile(
        temp_video,
        fps=30,
        codec="libx264",
        audio_codec="aac",
        threads=4,
        preset="ultrafast"
    )

    # FFmpeg ile dinamik, okunaklı, sarı/beyaz gizem konseptli altyazıyı videoya göm
    ffmpeg_cmd = [
        "ffmpeg", "-y",
        "-i", temp_video,
        "-vf", f"subtitles={subs_path}:force_style='Fontname=DejaVu Sans,Fontsize=16,PrimaryColour=&H0000FFFF,OutlineColour=&H00000000,BackColour=&H80000000,BorderStyle=3,Outline=2,Shadow=1,Alignment=2,MarginV=65'",
        "-c:a", "copy",
        output_path
    ]
    subprocess.run(ffmpeg_cmd, check=True)
    print(f"Video başarıyla oluşturuldu: {output_path}")

# =====================================================================
# 5. OTOMATİK YOUTUBE SHORTS YÜKLEME (YouTube Data API v3)
# =====================================================================
def upload_to_youtube(video_path, title, description):
    print("[5/5] YouTube'a otomatik yükleniyor...")
    client_id = os.environ.get("YT_CLIENT_ID")
    client_secret = os.environ.get("YT_CLIENT_SECRET")
    refresh_token = os.environ.get("YT_REFRESH_TOKEN")

    if not all([client_id, client_secret, refresh_token]):
        print("YouTube API bilgileri eksik! Yükleme adımı atlandı, ancak video hazır.")
        return

    creds = Credentials(
        None,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=client_id,
        client_secret=client_secret
    )

    youtube = build("youtube", "v3", credentials=creds)

    body = {
        "snippet": {
            "title": title[:100],
            "description": description + "\n\n#shorts #gizem #tarih #ilginçbilgiler",
            "tags": ["gizem", "tarih", "komplo", "ilginç bilgiler", "shorts"],
            "categoryId": "27"
        },
        "status": {
            "privacyStatus": "public",
            "selfDeclaredMadeForKids": False
        }
    }

    media = MediaFileUpload(video_path, chunksize=-1, resumable=True, mimetype="video/mp4")
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
    response = request.execute()
    print(f"Başarıyla Yüklendi! Video ID: {response['id']}")

if __name__ == "__main__":
    data = generate_mystery_script()
    generate_voice_and_subs(data["script"])
    images = generate_ai_images(data["image_prompts"])
    assemble_video(images)
    upload_to_youtube("final_short.mp4", data["title"], data["description"])
