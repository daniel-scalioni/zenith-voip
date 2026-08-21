import argparse
import os
import sys
import subprocess
import tempfile
import shutil

def get_duration(file_path):
    cmd = [
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", file_path
    ]
    res = subprocess.run(cmd, stdout=subprocess.PIPE, text=True, check=True)
    return float(res.stdout.strip())

def ensure_packages(force_cpu=False):
    has_gpu = False
    try:
        import torch
        has_gpu = torch.cuda.is_available()
    except ImportError:
        # Tenta detectar via nvidia-smi
        if subprocess.run(["nvidia-smi"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0:
            has_gpu = True
            
    if force_cpu:
        has_gpu = False

    packages_to_install = []
    
    if has_gpu:
        try:
            import faster_whisper
        except ImportError:
            packages_to_install.append("faster-whisper")
    else:
        try:
            import whisper
        except ImportError:
            packages_to_install.append("openai-whisper")
            packages_to_install.append("torch")

    if packages_to_install:
        print(f"Instalando dependências necessárias: {', '.join(packages_to_install)}")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-q"] + packages_to_install)
        
    return has_gpu

def split_audio(input_file, chunk_dir, chunk_duration):
    base_name = "chunk_%03d.wav"
    out_pattern = os.path.join(chunk_dir, base_name)
    # Converte para WAV (PCM 16k mono) para garantir que não haverá drift de timing nos chunks
    cmd = [
        "ffmpeg", "-y", "-i", input_file,
        "-f", "segment", "-segment_time", str(chunk_duration),
        "-c:a", "pcm_s16le", "-ar", "16000", "-ac", "1",
        out_pattern
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    chunks = sorted([os.path.join(chunk_dir, f) for f in os.listdir(chunk_dir) if f.startswith("chunk_")])
    return chunks

def load_model(has_gpu, model_size="small"):
    if has_gpu:
        from faster_whisper import WhisperModel
        print(f"Carregando modelo faster-whisper '{model_size}' na GPU...")
        return WhisperModel(model_size, device="cuda", compute_type="float16")
    else:
        import whisper
        print(f"Carregando modelo whisper '{model_size}' na CPU...")
        return whisper.load_model(model_size)

def format_timestamp(seconds):
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = seconds % 60
    milliseconds = int((secs - int(secs)) * 1000)
    return f"{hours:02d}:{minutes:02d}:{int(secs):02d},{milliseconds:03d}"

def transcribe_chunk(chunk_path, engine, has_gpu, offset_seconds):
    segments_data = []
    if has_gpu:
        segments, _ = engine.transcribe(chunk_path, language="pt", beam_size=5)
        for segment in segments:
            segments_data.append({
                "start": segment.start + offset_seconds,
                "end": segment.end + offset_seconds,
                "text": segment.text.strip()
            })
    else:
        result = engine.transcribe(chunk_path, language="pt")
        for segment in result["segments"]:
            segments_data.append({
                "start": segment["start"] + offset_seconds,
                "end": segment["end"] + offset_seconds,
                "text": segment["text"].strip()
            })
    return segments_data

def write_segments_to_srt(segments, srt_file_path, start_index):
    with open(srt_file_path, "a", encoding="utf-8") as f:
        for idx, seg in enumerate(segments):
            f.write(f"{start_index + idx}\n")
            f.write(f"{format_timestamp(seg['start'])} --> {format_timestamp(seg['end'])}\n")
            f.write(f"{seg['text']}\n\n")

def transcribe_chunk_with_retry(chunk_path, engine, has_gpu, offset_seconds, current_duration, srt_file_path, srt_index):
    try:
        segments_data = transcribe_chunk(chunk_path, engine, has_gpu, offset_seconds)
        write_segments_to_srt(segments_data, srt_file_path, srt_index)
        return srt_index + len(segments_data)
    except Exception as e:
        error_str = str(e).lower()
        if has_gpu and ("memory" in error_str or "oom" in error_str or "cuda" in error_str):
            print(f"OOM detectado no chunk de {current_duration}s. Tentando reduzir...")
            if current_duration <= 60:
                print("ERRO CRITICO: Memória GPU insuficiente mesmo com chunks pequenos.")
                print("SUGESTAO_CPU")
                sys.exit(2)
                
            temp_dir = tempfile.mkdtemp()
            try:
                sub_duration = current_duration / 2
                subchunks = split_audio(chunk_path, temp_dir, sub_duration)
                
                sub_offset = offset_seconds
                for sub in subchunks:
                    actual_dur = get_duration(sub)
                    srt_index = transcribe_chunk_with_retry(
                        sub, engine, has_gpu, sub_offset, actual_dur, srt_file_path, srt_index
                    )
                    sub_offset += actual_dur
                return srt_index
            finally:
                shutil.rmtree(temp_dir)
        else:
            raise e

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="Arquivo de áudio/vídeo de entrada")
    parser.add_argument("--output", required=True, help="Arquivo .srt de saída")
    parser.add_argument("--force-cpu", action="store_true", help="Força a execução via CPU")
    parser.add_argument("--chunk-duration", type=int, default=600, help="Duração dos blocos em segundos")
    parser.add_argument("--model-size", default="small", help="Tamanho do modelo do Whisper")
    args = parser.parse_args()

    if not os.path.exists(args.input):
        print(f"Arquivo não encontrado: {args.input}")
        sys.exit(1)

    print("Verificando ambiente e instalando dependências se necessário...")
    has_gpu = ensure_packages(args.force_cpu)
    
    # Prepara o arquivo final
    with open(args.output, "w", encoding="utf-8") as f:
        f.write("")

    temp_dir = tempfile.mkdtemp()
    try:
        print(f"Dividindo áudio em blocos de no máximo {args.chunk_duration} segundos...")
        chunks = split_audio(args.input, temp_dir, args.chunk_duration)
        
        try:
            engine = load_model(has_gpu, args.model_size)
        except Exception as e:
            if has_gpu and "memory" in str(e).lower():
                print("ERRO CRITICO: Falha ao alocar o modelo na GPU (OOM).")
                print("SUGESTAO_CPU")
                sys.exit(2)
            raise e

        srt_index = 1
        offset = 0.0
        for i, chunk in enumerate(chunks):
            actual_dur = get_duration(chunk)
            print(f"Processando bloco {i+1}/{len(chunks)} ({actual_dur:.1f}s)...")
            srt_index = transcribe_chunk_with_retry(
                chunk, engine, has_gpu, offset, actual_dur, args.output, srt_index
            )
            offset += actual_dur
            
        print(f"Transcrição concluída com sucesso: {args.output}")

    finally:
        shutil.rmtree(temp_dir)

if __name__ == "__main__":
    main()
