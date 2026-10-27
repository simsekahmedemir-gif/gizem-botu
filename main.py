import os
import json
import math
import asyncio
import urllib.parse
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
    ImageClip, TextClip, CompositeVideoClip, 
    AudioFileClip, CompositeAudioClip, concatenate_videoclips
)
from moviepy.audio.AudioClip import AudioArrayClip
import moviepy.audio.fx.all as afx

# Pillow 10+ uyumluluk yaması
if not hasattr(Image, 'ANTIALIAS'):
    Image.ANTIALIAS = Image.LANCZOS

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
client = genai.Client(api_key=GEMINI_API_KEY)

# ==========================================
# 1. VİRAL SENARYO VE 5 SAHNELİ GÖRSEL PLANI
# ==========================================
def generate_script():
    print("[1/5] Gemini ile viral gizem senaryosu üretiliyor...")
    prompt = """
    Sen milyonlarca izlenen bir YouTube Shorts gizem ve korku/belgesel kanalı metin yazarısın.
    İzleyiciyi ilk 2 saniyede ekrana kilitleyecek ("Bunu daha önce duymadığınıza eminim...", "1994 yılında..." gibi güçlü bir kanca ile başlayan),
    gerçek ve tüyler ürpertici, çözülememiş bir gizem hikayesi yaz.
    
    Kurallar:
    - Toplam okuma süresi 35-45 saniye civarında olsun (yaklaşık 75-95 kelime).
    - Cümleler kısa, vurucu ve merak uyandırıcı olsun.
    - Son cümlede izleyiciyi yorum yapmaya teşvik eden düşündürücü bir soru sor.
    - Görseller için hikayenin akışına uygun TAM 5 ADET ultra detaylı İngilizce sahne betimlemesi (image_prompts) yaz.

    Yanıtı SADECE aşağıdaki JSON formatında ver:
    {
        "title": "Merak uyandırıcı başlık (Maksimum 55 karakter, emoji kullan)",
        "description": "Kısa açıklama metni",
        "segments": [
            "1. sahnede okunacak vurucu giriş cümlesi.",
            "2. sahnede okunacak gelişme cümlesi.",
            "3. sahnede okunacak gerilimi artıran cümle.",
            "4. sahnede okunacak en şaşırtıcı detay.",
            "5. sahnede okunacak vurucu final ve soru cümlesi."
        ],
        "image_prompts": [
            "Cinematic dark mystery scene 1, photorealistic, 8k, eerie lighting, vertical",
            "Cinematic dark mystery scene 2, photorealistic, 8k, creepy atmosphere, vertical",
            "Cinematic dark mystery scene 3, photorealistic, 8k, dramatic shadows, vertical",
            "Cinematic dark mystery scene 4, photorealistic, 8k, unsettling detail, vertical",
            "Cinematic dark mystery scene 5, photorealistic, 8k, mysterious ending, vertical"
        ]
    }
    """
    
    response = client.models.generate_content(
        model="gemini-2.5-flash",
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
# 2. TOK VE DERİN BELGESEL SESLENDİRMESİ
# ==========================================
async def generate_segment_voices(segments):
    print("[2/5] Tok belgesel sesiyle sahneler seslendiriliyor...")
    audio_files = []
    for i, text in enumerate(segments):
        filename = f"voice_{i}.mp3"
        # Pitch -10Hz ile sesi toklaştırıyoruz, Rate +8% ile akıcı Shorts temposu veriyoruz
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
# 3. FİLİGRANSIZ (NO-LOGO) 5 GÖRSEL ÜRETİMİ
# ==========================================
def download_images(prompts):
    print("[3/5] Filigransız (AI yazısız) sinematik görseller indiriliyor...")
    image_files = []
    for i, prompt in enumerate(prompts):
        # nologo=true ve enhance=true ile sağ alttaki AI yazısını kaldırıyoruz
        clean_prompt = urllib.parse.quote(f"{prompt}, hyperrealistic, dark documentary style, 8k resolution, no text, no watermark")
        url = f"https://image.pollinations.ai/prompt/{clean_prompt}?width=1080&height=1920&nologo=true&enhance=true&seed={i*42}"
        
        filename = f"img_{i}.jpg"
        try:
            res = requests.get(url, timeout=45)
            if res.status_code == 200:
                with open(filename, "wb") as f:
                    f.write(res.content)
                # Güvenlik için alt köşede kalabilecek olası izleri %4 kırparak temizle ve 1080x1920'ye oturt
                img = Image.open(filename).convert("RGB")
                w, h = img.size
                img = img.crop((0, 0, w, int(h * 0.96))).resize((1080, 1920), Image.LANCZOS)
                img.save(filename)
                image_files.append(filename)
        except Exception as e:
            print(f"Görsel {i} hatası, yedek oluşturuluyor: {e}")
            img = Image.new("RGB", (1080, 1920), color=(15, 15, 20))
            img.save(filename)
            image_files.append(filename)
            
    return image_files

# ==========================================
# 4. ARKA PLAN MÜZİĞİ VE DİNAMİK VİDEO MONTAJI
# ==========================================
def generate_dark_ambient_bgm(duration, fps=44100):
    """Eğer depoda bgm.mp3 yoksa otomatik karanlık gerilim ambiyansı (drone sound) üretir."""
    t = np.linspace(0, duration, int(duration * fps), endpoint=False)
    # Derin bas gerilim frekansları (55Hz + 110Hz + hafif LFO dalgalanması)
    wave = 0.5 * np.sin(2 * np.pi * 55 * t) + 0.3 * np.sin(2 * np.pi * 82.4 * t) + 0.2 * np.sin(2 * np.pi * 110 * t)
    mod = 0.5 + 0.5 * np.sin(2 * np.pi * 0.2 * t)
    audio_data = (wave * mod * 0.08).astype(np.float32)
    stereo_data = np.column_stack((audio_data, audio_data))
    return AudioArrayClip(stereo_data, fps=fps)

def create_pro_video(script_data, audio_files, image_files, output_path="output.mp4"):
    print("[4/5] Ken Burns (Zoom) efektli, müzikli ve dinamik altyazılı video kurgulanıyor...")
    scene_clips = []
    
    for i in range(len(script_data["segments"])):
        text = script_data["segments"][i]
        audio_clip = AudioFileClip(audio_files[i])
        duration = audio_clip.duration + 0.15  # Cümleler arası doğal nefes payı
        
        # Görsele yavaşça yaklaşma (Ken Burns / Zoom-in) efekti -> Video hissi verir!
        base_img = ImageClip(image_files[i]).set_duration(duration)
        zoomed_img = base_img.resize(lambda t: 1 + 0.04 * (t / duration)).set_position(('center', 'center'))
        
        # Cümleyi 3-4 kelimelik dinamik altyazı parçalarına böl
        words = text.split()
        chunk_size = 4
        chunks = [" ".join(words[j:j+chunk_size]) for j in range(0, len(words), chunk_size)]
        chunk_duration = duration / max(len(chunks), 1)
        
        txt_clips = []
        for idx, chunk in enumerate(chunks):
            txt = TextClip(
                chunk.upper(),
                fontsize=68,
                color='#FFD700' if idx % 2 == 1 else 'white', # Tek-çift satırda sarı-beyaz vurgu
                stroke_color='black',
                stroke_width=3,
                font='DejaVu-Sans-Bold',
                method='caption',
                size=(920, None),
                align='center'
            ).set_start(idx * chunk_duration).set_duration(chunk_duration).set_position(('center', 1250))
            txt_clips.append(txt)
            
        scene = CompositeVideoClip([zoomed_img] + txt_clips, size=(1080, 1920)).set_duration(duration)
        scene = scene.set_audio(audio_clip)
        scene_clips.append(scene)
        
    final_video = concatenate_videoclips(scene_clips, method="compose")
    total_duration = final_video.duration
    
    # Arka Plan Müziği (BGM) Ekleme
    if os.path.exists("bgm.mp3"):
        print("bgm.mp3 bulundu, arka plana miksleniyor...")
        bgm = AudioFileClip("bgm.mp3")
        bgm = afx.audio_loop(bgm, duration=total_duration)
        bgm = bgm.volumex(0.12) # Konuşmayı bastırmaması için %12 ses seviyesi
    else:
        print("bgm.mp3 bulunamadı, otomatik karanlık gerilim ambiyansı üretiliyor...")
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
    print("Profesyonel video başarıyla oluşturuldu!")

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
    image_files = download_images(script_data["image_prompts"])
    create_pro_video(script_data, audio_files, image_files)
    upload_to_youtube("output.mp4", script_data["title"], script_data["description"])
