"""Бесплатный публичный https-адрес для мини-приложения, если своего хоста нет.

Запускает cloudflared quick tunnel (trycloudflare.com) на порт веб-сервера бота и отдаёт найденный адрес.
Адрес меняется при каждом перезапуске бота - кнопки в меню подхватывают новый сам.
Если у тебя есть постоянный домен, задай SITE_URL - туннель тогда не запускается.
"""
import asyncio
import logging
import os
import re
import stat
import urllib.request

BIN = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cloudflared")
URL = "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64"
_RE = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com")


def _download():
    if os.path.exists(BIN):
        return True
    try:
        tmp = BIN + ".part"
        urllib.request.urlretrieve(URL, tmp)
        os.chmod(tmp, os.stat(tmp).st_mode | stat.S_IEXEC)
        os.replace(tmp, BIN)
        return True
    except Exception:
        logging.exception("не удалось скачать cloudflared")
        return False


async def start(port, on_url):
    """Держит туннель живым; при каждом новом адресе вызывает on_url(url)."""
    ok = await asyncio.get_running_loop().run_in_executor(None, _download)
    if not ok:
        return
    while True:
        try:
            proc = await asyncio.create_subprocess_exec(
                BIN, "tunnel", "--no-autoupdate", "--url", f"http://127.0.0.1:{port}",
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)
            while True:
                line = await proc.stdout.readline()
                if not line:
                    break
                m = _RE.search(line.decode(errors="ignore"))
                if m:
                    await on_url(m.group(0))
            await proc.wait()
        except Exception:
            logging.exception("туннель упал")
        await asyncio.sleep(15)


def named_token():
    """Токен постоянного туннеля Cloudflare: переменная CF_TUNNEL_TOKEN или файл tunnel_token.txt рядом с ботом."""
    tok = os.getenv("CF_TUNNEL_TOKEN", "").strip()
    if not tok:
        try:
            with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "tunnel_token.txt"), encoding="utf-8") as f:
                tok = f.read().strip()
        except Exception:
            tok = ""
    return tok


async def start_named(token):
    """Постоянный туннель: свой домен (например phonkershop.com) -> веб-сервер бота. Адрес не меняется."""
    ok = await asyncio.get_running_loop().run_in_executor(None, _download)
    if not ok:
        return
    while True:
        try:
            proc = await asyncio.create_subprocess_exec(
                BIN, "tunnel", "--no-autoupdate", "run", "--token", token,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)
            while True:
                line = await proc.stdout.readline()
                if not line:
                    break
                logging.info("cloudflared: %s", line.decode(errors="ignore").rstrip()[:200])
            await proc.wait()
        except Exception:
            logging.exception("постоянный туннель упал")
        await asyncio.sleep(15)
