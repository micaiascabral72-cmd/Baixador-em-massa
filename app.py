import streamlit as st
import yt_dlp
import os
import re
import shutil
import tempfile
import zipfile

st.set_page_config(page_title="Mega Downloader", page_icon="🎬", layout="centered")

st.title("🚀 Mega Downloader de Vídeos")
st.write(
    "Baixe vídeos únicos ou perfis inteiros em alta qualidade, sem marca d'água da plataforma."
)

# ---------------------------------------------------------------
# Interface
# ---------------------------------------------------------------
url = st.text_input(
    "🔗 Cole o link aqui (URL do Vídeo ou do Perfil):",
    placeholder="Ex: https://www.tiktok.com/@nomedoperfil",
)

modo = st.radio(
    "⚙️ Modo de Download:",
    ["Um por vez (Vídeo Único)", "Baixar Tudo (Perfil Completo)"],
)

col1, col2 = st.columns(2)
with col1:
    qualidade = st.selectbox(
        "🎚️ Qualidade:",
        ["Melhor disponível", "1080p ou menor", "720p ou menor"],
    )
with col2:
    limite = None
    if modo == "Baixar Tudo (Perfil Completo)":
        usar_limite = st.checkbox("Limitar quantidade de vídeos?")
        if usar_limite:
            limite = st.number_input("Máximo de vídeos:", min_value=1, value=20, step=1)

iniciar = st.button("Iniciar Download", type="primary")

# ---------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------
def sanitizar_nome(nome: str, max_len: int = 120) -> str:
    """Remove caracteres problemáticos e limita o tamanho do nome de arquivo."""
    nome = re.sub(r'[\\/:*?"<>|]', "_", nome)
    return nome[:max_len]


def formato_por_qualidade(escolha: str) -> str:
    if escolha == "1080p ou menor":
        return "bestvideo[height<=1080]+bestaudio/best[height<=1080]/best"
    if escolha == "720p ou menor":
        return "bestvideo[height<=720]+bestaudio/best[height<=720]/best"
    return "bestvideo+bestaudio/best"


def montar_opcoes(download_dir, modo, qualidade, limite, progress_bar, status_box, contador):
    def hook(d):
        if d["status"] == "downloading":
            nome = d.get("info_dict", {}).get("title", "vídeo")
            pct = d.get("_percent_str", "").strip()
            status_box.info(f"⬇️ Baixando: {nome[:60]} — {pct}")
        elif d["status"] == "finished":
            contador["ok"] += 1
            status_box.success(f"✅ Concluído: {contador['ok']} vídeo(s) baixado(s) até agora.")

    opts = {
        "outtmpl": os.path.join(download_dir, "%(uploader)s_%(title).80s_%(id)s.%(ext)s"),
        "format": formato_por_qualidade(qualidade),
        "merge_output_format": "mp4",
        "ignoreerrors": True,
        "no_warnings": True,
        "restrictfilenames": False,
        "progress_hooks": [hook],
        "concurrent_fragment_downloads": 4,
        # Evita reprocessar itens que já falharam repetidamente
        "retries": 3,
        "fragment_retries": 3,
    }

    if modo == "Um por vez (Vídeo Único)":
        opts["noplaylist"] = True
    else:
        opts["noplaylist"] = False
        if limite:
            opts["playlistend"] = int(limite)

    return opts


# ---------------------------------------------------------------
# Execução
# ---------------------------------------------------------------
if iniciar:
    if not url:
        st.warning("⚠️ Por favor, insira um link válido.")
    else:
        with tempfile.TemporaryDirectory() as download_dir:
            progress_bar = st.progress(0)
            status_box = st.empty()
            contador = {"ok": 0}

            ydl_opts = montar_opcoes(
                download_dir, modo, qualidade, limite, progress_bar, status_box, contador
            )

            erros = []
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([url])
            except Exception as e:
                erros.append(str(e))

            arquivos = [
                f for f in os.listdir(download_dir)
                if os.path.isfile(os.path.join(download_dir, f))
            ]

            progress_bar.progress(100)

            if not arquivos:
                st.error(
                    "❌ Nenhum vídeo pôde ser baixado. O perfil pode ser privado, "
                    "o link é inválido, ou a plataforma bloqueou o acesso no momento."
                )
                if erros:
                    with st.expander("Detalhes técnicos do erro"):
                        st.code("\n".join(erros))
            else:
                st.success(f"✅ Sucesso! {len(arquivos)} vídeo(s) baixado(s).")

                zip_path = os.path.join(tempfile.gettempdir(), "meus_videos.zip")
                with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                    for f in arquivos:
                        zf.write(os.path.join(download_dir, f), arcname=f)

                with open(zip_path, "rb") as f:
                    st.download_button(
                        label="⬇️ Baixar Arquivo ZIP",
                        data=f,
                        file_name="meus_videos.zip",
                        mime="application/zip",
                    )

                with st.expander("Ver lista de vídeos baixados"):
                    for f in arquivos:
                        st.write(f"• {f}")

                os.remove(zip_path)
