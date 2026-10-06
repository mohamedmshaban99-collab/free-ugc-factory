import os
import asyncio
import subprocess
import edge_tts
from fastapi import FastAPI, BackgroundTasks
from fastapi.responses import FileResponse
from pydantic import BaseModel

app = FastAPI(title="Free Cloud UGC Renderer API")

# Ensure directories exist
os.makedirs("temp", exist_ok=True)
os.makedirs("output", exist_ok=True)

class VideoRequest(BaseModel):
    script: str
    video_query: str

async def generate_ugc_video(task_id: str, req: VideoRequest):
    print(f"[{task_id}] Starting video generation...")
    
    # 1. Generate Voiceover using Free Edge-TTS
    voice_path = f"temp/{task_id}_voice.mp3"
    print(f"[{task_id}] Generating TTS...")
    communicate = edge_tts.Communicate(req.script, "ar-EG-SalmaNeural", rate="+5%")
    await communicate.save(voice_path)
    
    # 2. Fetch Real UGC Video from YouTube Shorts (100% Free, No API Key needed)
    print(f"[{task_id}] Fetching video from YouTube Shorts for query: {req.video_query}")
    raw_video_path = f"temp/{task_id}_raw.mp4"
    
    # We use yt-dlp to search for the top Short matching the query and download it
    # 'ytsearch1:shorts <query>' downloads the first result
    search_query = f"ytsearch1:shorts {req.video_query} UGC"
    
    ytdlp_cmd = [
        "yt-dlp",
        search_query,
        "-f", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/mp4",
        "-o", raw_video_path,
        "--no-playlist",
        "--match-filter", "duration < 60" # Ensure it's a short
    ]
    subprocess.run(ytdlp_cmd, check=False) # check=False so it doesn't crash if no video found
    
    if not os.path.exists(raw_video_path):
        # Fallback if yt-dlp fails
        print(f"[{task_id}] Failed to get video from YouTube. Using fallback.")
        import urllib.request
        fallback_url = "https://test-videos.co.uk/vids/bigbuckbunny/mp4/h264/720/Big_Buck_Bunny_720_10s_1MB.mp4"
        urllib.request.urlretrieve(fallback_url, raw_video_path)

    # 3. Assemble with FFmpeg
    output_path = f"output/{task_id}_final.mp4"
    print(f"[{task_id}] Assembling Final Video...")
    
    # Mix original video (looping if shorter than audio) with our new voiceover
    ffmpeg_cmd = [
        "ffmpeg", "-y",
        "-stream_loop", "-1", "-i", raw_video_path,
        "-i", voice_path,
        "-c:v", "libx264", "-c:a", "aac",
        "-shortest",
        "-vf", "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920",
        output_path
    ]
    subprocess.run(ffmpeg_cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print(f"[{task_id}] Video Ready: {output_path}")

@app.post("/generate")
async def generate_video_endpoint(req: VideoRequest, background_tasks: BackgroundTasks):
    import uuid
    task_id = str(uuid.uuid4())[:8]
    background_tasks.add_task(generate_ugc_video, task_id, req)
    return {"status": "processing", "task_id": task_id, "download_url": f"/download/{task_id}"}

@app.get("/download/{task_id}")
async def download_video(task_id: str):
    file_path = f"output/{task_id}_final.mp4"
    if os.path.exists(file_path):
        return FileResponse(file_path, media_type="video/mp4", filename=f"UGC_{task_id}.mp4")
    return {"error": "Video still processing or not found."}

# Run via: uvicorn cloud_video_api:app --host 0.0.0.0 --port 8000
