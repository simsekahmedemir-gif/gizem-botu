import os
import json
import asyncio
import requests
import numpy as np
from PIL import Image
from google import genai
from google.genai import types
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2.credentials import Credentials
import edge_tts
from moviepy.editor import (
    VideoFileClip, TextClip, CompositeVideoClip, 
    AudioFileClip, CompositeAudioClip, concatenate_videoclips
)
from moviepy.audio.AudioClip import AudioArrayClip
import moviepy.audio.fx.all as afx

if not hasattr(Image, 'ANTIALIAS'):
    Image.ANTIALIAS = Image.LANCZOS

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
PEXELS_API_KEY = os.environ.get("PEXELS_API_KEY")

# Yeni nesil official Google GenAI istemcisi
client = genai.Client(api_key=GEMINI_API_KEY)

# ==========================================
# 1. VİRAL SENARYO VE PEXELS PROMPTLARI
# ==========================================
def generate_script():
    print("[1/5] Gemini ile viral gizem senaryosu üretiliyor...")
    prompt = """
    Sen profesyonel bir YouTube Shorts gizem ve belgesel kanalı metin yazarısın.
    İzleyiciyi ilk 2 saniyede kilitleyecek çarpıcı bir kanca ile başlayan, çözülememiş gizemli bir hikaye yaz.
    
    Kurallar:
    - Toplam okuma süresi 35-45 saniye olsun (75-95 kelime).
    - Cümleler kısa ve vurucu olsun.
    - Son cümlede izleyiciyi yorum yapmaya teşvik eden bir soru sor.
    - Pexels stok video aramasında kullanılmak üzere TAM 5 ADET kısa, İngilizce arama anahtar kelimesi yaz.

    Yanıtı SADECE aşağıdaki JSON formatında ver:
    {
        "title": "Merak uyandırıcı başlık (Maksimum 55 karakter, emoji ekle)",
        "description": "Kısa açıklama",
        "segments": [
            "1. sahnede okunacak vurucu giriş cümlesi.",
            "2. sahnede okunacak gelişme cümlesi.",
            "3. sahnede okunacak gerilimi artıran cümle.",
            "4. sahnede okunacak en şaşırtıcı detay.",
            "5. sahnede okunacak vurucu final ve soru cümlesi."
        ],
        "pexels_queries": [
            "dark mysterious forest aerial",
            "creepy abandoned hallway",
            "dark stormy night rain",
            "mysterious ancient ruins",
            "dark foggy road night"
        ]
    }
    """
    
    # En güncel ve her anahtarla çalışan flash modeli
    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.85
        )
    )
    
    data = json.loads(response.text)
    print(f"Başlık: {data['title']}")
    return data

# ==========================================
# 2. TOK BELGESEL SESLENDİRMESİ
# ==========================================
async def generate_segment_voices(segments):
    print("[2/5] Tok belgesel sesiyle sahneler seslendiriliyor...")
    audio_files = []
    for i, text in enumerate(segments):
        filename = f"voice_{i}.mp3"
        communicate = edge_tts.Communicate(
            text, 
            voice="tr-TR-AhmetNeural", 
            rate="+8%", 
            pitch="-10Hz"
        )
        await communicate.save(filename)
        audio_files.append(filename)
    return audio_files

# ==========================================
# 3. PEXELS'TEN GERÇEK STOK VİDEO İNDİRME
# ==========================================
def download_pexels_videos(queries):
    print("[3/5] Pexels'ten gerçek sinematik stok videolar indiriliyor...")
    video_files = []
    headers = {"Authorization": PEXELS_API_KEY} if PEXELS_API_KEY else {}
    
    for i, query in enumerate(queries):
        filename = f"stock_{i}.mp4"
        try:
            url = f"https://api.pexels.com/videos/search?query={query}&orientation=portrait&per_page=1"
            res = requests.get(url, headers=headers, timeout=30)
            
            video_url = None
            if res.status_code == 200:
                data = res.json()
                if data.get("videos"):
                    video_files_list = data["videos"][0]["video_files"]
                    for vf in video_files_list:
                        if vf.get("width") and vf["width"] <= 1080 and vf.get("link"):
                            video_url = vf["link"]
                            break
                    if not video_url and video_files_list:
                        video_url = video_files_list[0]["link"]
            
            if video_url:
                v_res = requests.get(video_url, timeout=60)
                if v_res.status_code == 200:
                    with open(filename, "wb") as f:
                        f.write(v_res.content)
                    video_files.append(filename)
                    continue
        except Exception as e:
            print(f"Pexels video {i} indirilemedi: {e}")
            
        print(f"Sahne {i} için yedek arka plan oluşturuluyor...")
        from moviepy.editor import ColorClip
        fallback = ColorClip(size=(1080, 1920), color=(10, 10, 15), duration=5)
        fallback.write_videofile(filename, fps=24, codec="libx264", audio=False, logger=None)
        video_files.append(filename)
        
    return video_files

# ==========================================
# 4. MÜZİK VE VİDEO MONTAJI
# ==========================================
def generate_dark_ambient_bgm(duration, fps=44100):
    t = np.linspace(0, duration, int(duration * fps), endpoint=False)
    wave = 0.5 * np.sin(2 * np.pi * 55 * t) + 0.3 * np.sin(2 * np.pi * 82.4 * t) + 0.2 * np.sin(2 * np.pi * 110 * t)
    mod = 0.5 + 0.5 * np.sin(2 * np.pi * 0.2 * t)
    audio_data = (wave * mod * 0.08).astype(np.float32)
    return AudioArrayClip(np.column_stack((audio_data, audio_data)), fps=fps)

def create_pro_video(script_data, audio_files, video_files, output_path="output.mp4"):
    print("[4/5] Gerçek stok videolar, müzik ve dinamik altyazılar birleştiriliyor...")
    scene_clips = []
    
    for i in range(len(script_data["segments"])):
        text = script_data["segments"][i]
        audio_clip = AudioFileClip(audio_files[i])
        duration = audio_clip.duration + 0.15
        
        try:
            v_clip = VideoFileClip(video_files[i])
            if v_clip.duration < duration:
                v_clip = v_clip.loop(duration=duration)
            else:
                v_clip = v_clip.subclip(0, duration)
            
            v_clip = v_clip.resize(height=1920)
            w, h = v_clip.size
            if w > 1080:
                x1 = (w - 1080) / 2
                v_clip = v_clip.crop(x1=x1, y1=0, x2=x1+1080, y2=1920)
            elif w < 1080:
                v_clip = v_clip.resize(width=1080)
        except:
            from moviepy.editor import ColorClip
            v_clip = ColorClip(size=(1080, 1920), color=(10, 10, 15), duration=duration)
            
        v_clip = v_clip.set_duration(duration)
        
        words = text.split()
        chunk_size = 4
        chunks = [" ".join(words[j:j+chunk_size]) for j in range(0, len(words), chunk_size)]
        chunk_duration = duration / max(len(chunks), 1)
        
        txt_clips = []
        for idx, chunk in enumerate(chunks):
            txt = TextClip(
                chunk.upper(),
                fontsize=68,
                color='#FFD700' if idx % 2 == 1 else 'white',
                stroke_color='black',
                stroke_width=3,
                font='DejaVu-Sans-Bold',
                method='caption',
                size=(920, None),
                align='center'
            ).set_start(idx * chunk_duration).set_duration(chunk_duration).set_position(('center', 1250))
            txt_clips.append(txt)
            
        scene = CompositeVideoClip([v_clip] + txt_clips, size=(1080, 1920)).set_duration(duration)
        scene = scene.set_audio(audio_clip)
        scene_clips.append(scene)
        
    final_video = concatenate_videoclips(scene_clips, method="compose")
    total_duration = final_video.duration
    
    if os.path.exists("bgm.mp3"):
        bgm = AudioFileClip("bgm.mp3")
        bgm = afx.audio_loop(bgm, duration=total_duration)
        bgm = bgm.volumex(0.12)
    else:
        bgm = generate_dark_ambient_bgm(total_duration)
        
    final_audio = CompositeAudioClip([final_video.audio, bgm])
    final_video = final_video.set_audio(final_audio)
    
    final_video.write_videofile(
        output_path,
        fps=30,
        codec="libx264",
        audio_codec="aac",
        preset="faster",
        threads=4
    )
    print("Profesyonel stok video başarıyla oluşturuldu!")

# ==========================================
# 5. YOUTUBE SHORTS YÜKLEME
# ==========================================
def upload_to_youtube(video_file, title, description):
    print("[5/5] YouTube'a yükleniyor...")
    creds = Credentials(
        None,
        refresh_token=os.environ.get("YT_REFRESH_TOKEN"),
        client_id=os.environ.get("YT_CLIENT_ID"),
        client_secret=os.environ.get("YT_CLIENT_SECRET"),
        token_uri="https://oauth2.googleapis.com/token"
    )
    
    youtube = build("youtube", "v3", credentials=creds)
    
    body = {
        "snippet": {
            "title": f"{title} #shorts #gizem",
            "description": f"{description}\n\nDaha fazla gizemli olay için abone olmayı unutmayın!\n\n#gizem #korku #bilgi #belgesel #shorts",
            "tags": ["gizem", "korku", "gerçek hikayeler", "belgesel", "shorts"],
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
            print(f"Yükleme: %{int(status.progress() * 100)}")
            
    print(f"Yükleme Tamamlandı! Video ID: {response.get('id')}")

if __name__ == "__main__":
    script_data = generate_script()
    audio_files = asyncio.run(generate_segment_voices(script_data["segments"]))
    video_files = download_pexels_videos(script_data["pexels_queries"])
    create_pro_video(script_data, audio_files, video_files)
    upload_to_youtube("output.mp4", script_data["title"], script_data["description"])
