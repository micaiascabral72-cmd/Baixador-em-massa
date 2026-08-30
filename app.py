import streamlit as st
import yt_dlp
import os
import re
import shutil
import subprocess
import time

# --------------------------------------------------------------------------------------
# CONFIGURAÇÃO DA PÁGINA
# --------------------------------------------------------------------------------------
st.set_page_config(page_title="Baixador de Vídeos", page_icon="🎬", layout="centered")

st.title("🚀 Mega Downloader de Vídeos")
st.caption(
    "Baixe vídeos únicos ou perfis inteiros, em alta qualidade e sem marca d'água. "
    "Também dá pra extrair apenas o áudio (MP3) — ative na barra lateral."
)

st.warning(
    "⚠️ Use esta ferramenta apenas para baixar conteúdo próprio ou que você tem "
    "autorização para baixar. Respeite os direitos autorais e os termos de uso "
    "de cada plataforma."
)

# --------------------------------------------------------------------------------------
# SIDEBAR - CONFIGURAÇÕES AVANÇADAS
# --------------------------------------------------------------------------------------
with st.sidebar:
    st.header("⚙️ Configurações")

    apenas_audio = st.checkbox("🎵 Extrair apenas o áudio (MP3)", value=False)

    if not apenas_audio:
        qualidade = st.selectbox("Qualidade do vídeo", ["Melhor disponível", "1080p", "720p", "480p"])
    else:
        qualidade = "Melhor disponível"
        st.caption("ℹ️ No modo áudio, o vídeo é descartado e só o som é salvo em MP3.")

    limite = st.number_input(
        "Limite de vídeos (modo perfil completo)",
        min_value=1, max_value=200, value=30, step=1,
        help="Trava de segurança pra não baixar centenas de vídeos sem querer. Aumente se precisar."
    )

    remover_logo = False
    canto = None
    percentual_corte = 12
    if not apenas_audio:
        remover_logo = st.checkbox("Tentar remover logo/marca no canto do vídeo", value=False)
        if remover_logo:
            st.caption(
                "⚠️ Isso usa o filtro 'delogo' do ffmpeg pra apagar uma área do vídeo. "
                "Funciona bem para logos fixas e pequenas, mas não é perfeito em todos os casos."
            )
            canto = st.selectbox(
                "Onde fica a marca?",
                ["Canto superior direito", "Canto superior esquerdo",
                 "Canto inferior direito", "Canto inferior esquerdo"]
            )
            percentual_corte = st.slider("Tamanho da área a cobrir (%)", 5, 25, 12)

# --------------------------------------------------------------------------------------
# INTERFACE PRINCIPAL
# --------------------------------------------------------------------------------------
url = st.text_input(
    "🔗 Cole o link aqui (vídeo único ou perfil):",
    placeholder="Ex: https://www.tiktok.com/@nomedoperfil"
)
modo = st.radio("Modo de download:", ["Vídeo único", "Perfil completo (todos os vídeos)"])

iniciar = st.button("Iniciar Download", type="primary")

FORMAT_MAP = {
    "Melhor disponível": "bv*+ba/b",
    "1080p": "bv*[height<=1080]+ba/b[height<=1080]",
    "720p": "bv*[height<=720]+ba/b[height<=720]",
    "480p": "bv*[height<=480]+ba/b[height<=480]",
}


def sanitize(nome: str) -> str:
    return re.sub(r'[\\/*?:"<>|]', "_", nome)[:80]


def cobrir_logo(caminho_video: str, canto: str, percentual: int) -> bool:
    """Tenta apagar uma área (canto) do vídeo usando o filtro delogo do ffmpeg.
    Best-effort: funciona melhor com logos pequenas e estáticas."""
    try:
        probe = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0",
             "-show_entries", "stream=width,height", "-of", "csv=p=0", caminho_video],
            capture_output=True, text=True, timeout=15
        )
        w, h = map(int, probe.stdout.strip().split(","))
    except Exception:
        return False

    box_w = max(int(w * percentual / 100), 10)
    box_h = max(int(h * percentual / 100), 10)

    posicoes = {
        "Canto superior direito": (w - box_w, 0),
        "Canto superior esquerdo": (0, 0),
        "Canto inferior direito": (w - box_w, h - box_h),
        "Canto inferior esquerdo": (0, h - box_h),
    }
    x, y = posicoes[canto]

    saida = caminho_video + ".tmp.mp4"
    cmd = [
        "ffmpeg", "-y", "-i", caminho_video,
        "-vf", f"delogo=x={x}:y={y}:w={box_w}:h={box_h}:show=0",
        "-c:a", "copy", saida
    ]
    try:
        resultado = subprocess.run(cmd, capture_output=True, timeout=300)
    except Exception:
        return False

    if resultado.returncode == 0 and os.path.exists(saida) and os.path.getsize(saida) > 0:
        os.remove(caminho_video)
        os.rename(saida, caminho_video)
        return True

    if os.path.exists(saida):
        os.remove(saida)
    return False


# --------------------------------------------------------------------------------------
# LÓGICA DE DOWNLOAD
# --------------------------------------------------------------------------------------
if iniciar:
    if not url.strip():
        st.warning("⚠️ Por favor, insira um link válido.")
    else:
        download_dir = f"temp_downloads_{int(time.time())}"
        os.makedirs(download_dir, exist_ok=True)

        progress_bar = st.progress(0)
        status_text = st.empty()
        contador = {"feito": 0, "total": 0}

        def hook(d):
            if d["status"] == "downloading":
                titulo = d.get("info_dict", {}).get("title", "vídeo")
                status_text.text(f"⬇️ Baixando: {str(titulo)[:50]}...")
            elif d["status"] == "finished":
                contador["feito"] += 1
                if contador["total"]:
                    progress_bar.progress(min(contador["feito"] / contador["total"], 1.0))

        ydl_opts = {
            "outtmpl": f"{download_dir}/%(uploader)s_%(title).60s.%(ext)s",
            "ignoreerrors": True,
            "no_warnings": True,
            "quiet": True,
            "progress_hooks": [hook],
            "restrictfilenames": True,
            "retries": 5,
            "fragment_retries": 5,
            "concurrent_fragment_downloads": 4,
        }

        if apenas_audio:
            ydl_opts["format"] = "bestaudio/best"
            ydl_opts["postprocessors"] = [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }]
        else:
            ydl_opts["format"] = FORMAT_MAP[qualidade]
            ydl_opts["merge_output_format"] = "mp4"

        if modo == "Vídeo único":
            ydl_opts["noplaylist"] = True
        else:
            ydl_opts["noplaylist"] = False
            ydl_opts["playlistend"] = int(limite)

        try:
            # Tenta descobrir quantos vídeos existem, só pra alimentar a barra de progresso.
            # Se falhar, segue sem número exato (a barra fica indeterminada).
            try:
                with yt_dlp.YoutubeDL({**ydl_opts, "extract_flat": True, "quiet": True}) as ydl_info:
                    info = ydl_info.extract_info(url, download=False)
                    if info and "entries" in info and info["entries"]:
                        entradas = [e for e in info["entries"] if e]
                        contador["total"] = min(len(entradas), int(limite)) if modo != "Vídeo único" else 1
                    else:
                        contador["total"] = 1
            except Exception:
                contador["total"] = 0

            with st.spinner("Baixando... isso pode demorar dependendo da quantidade de vídeos."):
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([url])

            extensoes = (".mp3",) if apenas_audio else (".mp4", ".mov", ".webm", ".mkv")
            arquivos = sorted(
                f for f in os.listdir(download_dir)
                if f.lower().endswith(extensoes)
            )

            if not arquivos:
                item = "áudio" if apenas_audio else "vídeo"
                st.error(
                    f"❌ Nenhum {item} pôde ser baixado. O perfil pode ser privado, "
                    "o link pode estar inválido, ou a plataforma bloqueou o acesso."
                )
            else:
                if remover_logo:
                    with st.spinner(f"Tentando remover a marca em {len(arquivos)} vídeo(s)..."):
                        for arq in arquivos:
                            caminho = os.path.join(download_dir, arq)
                            if caminho.lower().endswith(".mp4"):
                                cobrir_logo(caminho, canto, percentual_corte)

                item_label = "áudio(s)" if apenas_audio else "vídeo(s)"
                st.success(f"✅ Sucesso! {len(arquivos)} {item_label} baixado(s).")

                if len(arquivos) == 1:
                    caminho_unico = os.path.join(download_dir, arquivos[0])
                    with open(caminho_unico, "rb") as f:
                        arquivo_bytes = f.read()
                    if apenas_audio:
                        st.download_button(
                            "⬇️ Baixar Áudio (MP3)",
                            data=arquivo_bytes,
                            file_name=sanitize(arquivos[0]),
                            mime="audio/mpeg",
                        )
                    else:
                        st.download_button(
                            "⬇️ Baixar Vídeo",
                            data=arquivo_bytes,
                            file_name=sanitize(arquivos[0]),
                            mime="video/mp4",
                        )
                else:
                    prefixo = "audios_baixados" if apenas_audio else "videos_baixados"
                    zip_base = f"{prefixo}_{int(time.time())}"
                    zip_path = shutil.make_archive(zip_base, "zip", download_dir)
                    with open(zip_path, "rb") as f:
                        zip_bytes = f.read()
                    label_zip = "⬇️ Baixar Todos os Áudios (.zip)" if apenas_audio else "⬇️ Baixar Todos (.zip)"
                    nome_zip = "meus_audios.zip" if apenas_audio else "meus_videos.zip"
                    st.download_button(
                        label_zip,
                        data=zip_bytes,
                        file_name=nome_zip,
                        mime="application/zip",
                    )
                    os.remove(zip_path)

        except Exception as e:
            st.error(f"Ocorreu um erro: {str(e)}")
        finally:
            shutil.rmtree(download_dir, ignore_errors=True)
