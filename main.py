import os
import json
import random
import asyncio
from google import genai
from google.genai import types
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
import edge_tts
from moviepy.editor import TextClip, CompositeVideoClip, AudioFileClip, ColorClip

# API Anahtarlarını Al
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# Gemini İstemcisini Başlat (En güncel ve kararlı yöntem)
client = genai.Client(api_key=GEMINI_API_KEY)

def generate_script():
    print("1/5 Gemini ile gizemli senaryo üretiliyor...")
    
    prompt = """
    YouTube Shorts için çok sürükleyici, kısa ve gizemli bir hikaye senaryosu yaz. 
    Hikaye yarım kalmasın, kısa bir giriş, şaşırtıcı bir olay ve vurucu bir finali olsun.
    Konu: Tarihin aydınlatılamamış gizemlerinden, paranormal olaylardan veya tuhaf uzay/doğa olaylarından biri olsun.
    Dil: Türkçe, akıcı ve merak uyandırıcı.
    
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
    
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.8
        )
    )
    
    data = json.loads(response.text)
    print(f"Başlık: {data['title']}")
    return data

async def generate_voice(text, output_path="voice.mp3"):
    print("2/5 Edge-TTS ile seslendirme yapılıyor...")
    communicate = edge_tts.Communicate(text, "tr-TR-AhmetNeural")
    await communicate.save(output_path)

def create_video(script_data, audio_path="voice.mp3", output_path="output.mp4"):
    print("3/5 Video montajı hazırlanıyor...")
    
    # Ses dosyasını yükle
    audio = AudioFileClip(audio_path)
    duration = audio.duration
    
    # Arka plan (Dikey Shorts formatı: 1080x1920)
    bg = ColorClip(size=(1080, 1920), color=(10, 10, 10), duration=duration)
    
    # Altyazı/Metin katmanı
    txt_clip = TextClip(
        script_data['script'], 
        fontsize=50, 
        color='white', 
        size=(900, None), 
        method='caption',
        align='center',
        font='DejaVu-Sans-Bold'
    ).set_duration(duration).set_position('center')
    
    video = CompositeVideoClip([bg, txt_clip])
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
    # OAuth kimlik bilgileri
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
            "title": title + " #shorts",
            "description": description + "\n\n#gizem #korkunç #bilgi #shorts",
            "tags": ["gizem", "korkunç", "bilgi", "shorts"],
            "categoryId": "24"  # Entertainment
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
