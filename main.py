import discord
from discord.ext import commands
import yt_dlp as youtube_dl
import asyncio
import os

# Configuración del bot
def get_token():
    try:
        # Intenta leer desde variable de entorno (para hosting)
        token = os.getenv('TOKEN')
        if token:
            return token
        
        # Si no hay variable de entorno, lee desde archivo local
        with open('token.txt', 'r') as f:
            return f.read().strip()
    except FileNotFoundError:
        print("❌ Error: No se encontró el archivo token.txt")
        print("📝 Crea un archivo token.txt con tu token de Discord")
        return None

TOKEN = get_token()
if not TOKEN:
    print("❌ No se pudo obtener el token. El bot no puede iniciarse.")
    exit(1)

PREFIX = "!"  # Prefijo para comandos

intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True

bot = commands.Bot(command_prefix=PREFIX, intents=intents)

# Diccionario para manejar colas de canciones por servidor
queues = {}

# Configuración de yt-dlp para extraer solo audio
ydl_opts = {
    'format': 'bestaudio/best',
    'postprocessors': [{
        'key': 'FFmpegExtractAudio',
        'preferredcodec': 'opus',
        'preferredquality': '192',
    }],
    'default_search': 'ytsearch',
    'noplaylist': True,
}

@bot.event
async def on_ready():
    print(f"✅ Bot listo como {bot.user.name}")

@bot.command(name="play", help="Reproduce una canción desde YouTube")
async def play(ctx, *, query):
    # Verifica si el usuario está en un canal de voz
    if not ctx.author.voice:
        return await ctx.send("⚠️ Debes estar en un canal de voz para usar este comando.")

    voice_channel = ctx.author.voice.channel
    voice_client = ctx.voice_client

    # Conecta al bot si no está en un canal
    if not voice_client:
        voice_client = await voice_channel.connect()
    elif voice_client.channel != voice_channel:
        return await ctx.send("🚨 Ya estoy reproduciendo música en otro canal.")

    # Si es una búsqueda (no URL), añade el prefijo ytsearch:
    if not query.startswith(('http://', 'https://')):
        query = f"ytsearch:{query}"

    # Si ya hay una canción en reproducción, la añade a la cola
    if voice_client.is_playing() or voice_client.is_paused():
        if ctx.guild.id not in queues:
            queues[ctx.guild.id] = []
        queues[ctx.guild.id].append(query)
        return await ctx.send(f"🎵 Canción añadida a la cola: {query}")

    # Descarga y reproduce la canción
    await play_song(ctx, voice_client, query)

async def play_song(ctx, voice_client, query):
    try:
        # Extrae información del audio con yt-dlp
        with youtube_dl.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(query, download=False)
            
            # Si es una búsqueda, toma el primer resultado
            if 'entries' in info:
                info = info['entries'][0]
                
            url = info['url']
            title = info.get('title', 'Canción desconocida')

        # Reproduce el audio usando FFmpeg
        FFMPEG_OPTIONS = {
            'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
            'options': '-vn -ac 2 -ar 48000 -b:a 192k',
        }

        voice_client.play(
            discord.FFmpegPCMAudio(url, **FFMPEG_OPTIONS),
            after=lambda e: asyncio.run_coroutine_threadsafe(play_next(ctx), bot.loop)
        )
        await ctx.send(f"🎶 Reproduciendo: **{title}**")
        
    except Exception as e:
        await ctx.send(f"❌ Error al reproducir: {str(e)}")
        print(f"Error: {e}")

async def play_next(ctx):
    if ctx.guild.id in queues and queues[ctx.guild.id]:
        next_query = queues[ctx.guild.id].pop(0)
        voice_client = ctx.voice_client
        await play_song(ctx, voice_client, next_query)

@bot.command(name="skip", help="Salta la canción actual")
async def skip(ctx):
    voice_client = ctx.voice_client
    if voice_client and (voice_client.is_playing() or voice_client.is_paused()):
        voice_client.stop()
        await ctx.send("⏭️ Canción saltada.")
    else:
        await ctx.send("🚨 No hay ninguna canción reproduciéndose.")

@bot.command(name="stop", help="Detiene la música y desconecta al bot")
async def stop(ctx):
    voice_client = ctx.voice_client
    if voice_client:
        if ctx.guild.id in queues:
            queues[ctx.guild.id].clear()
        await voice_client.disconnect()
        await ctx.send("⏹️ Música detenida y bot desconectado.")
    else:
        await ctx.send("🚨 No estoy conectado a un canal de voz.")

@bot.command(name="pause", help="Pausa la canción actual")
async def pause(ctx):
    voice_client = ctx.voice_client
    if voice_client and voice_client.is_playing():
        voice_client.pause()
        await ctx.send("⏸️ Canción pausada.")
    else:
        await ctx.send("🚨 No hay ninguna canción reproduciéndose.")

@bot.command(name="resume", help="Reanuda la canción pausada")
async def resume(ctx):
    voice_client = ctx.voice_client
    if voice_client and voice_client.is_paused():
        voice_client.resume()
        await ctx.send("▶️ Canción reanudada.")
    else:
        await ctx.send("🚨 No hay ninguna canción pausada.")

@bot.command(name="queue", help="Muestra la cola de reproducción")
async def show_queue(ctx):
    if ctx.guild.id in queues and queues[ctx.guild.id]:
        queue_list = ""
        for i, query in enumerate(queues[ctx.guild.id], 1):
            # Elimina el prefijo ytsearch: si existe
            display_query = query.replace("ytsearch:", "") if query.startswith("ytsearch:") else query
            queue_list += f"{i}. {display_query}\n"
        await ctx.send(f"📜 **Cola de reproducción:**\n{queue_list}")
    else:
        await ctx.send("📭 La cola está vacía.")

# Inicia el bot
bot.run(TOKEN)