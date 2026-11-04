"""Telegram call bot (userbot): answers incoming 1-to-1 calls and streams a saved
video / audio clip into the call. Same idea as the WhatsApp `callbot`.

Commands (send them from your own account, any chat, e.g. "Saved Messages"):
  .setcall          reply to a video / audio / voice note -> saves it as the call clip
  .callpreview      sends the saved clip back to you
  .delcall          deletes the saved clip
  .callmode answer|reject|off   what to do when someone calls you
  .callmsg <text>   (reject mode) message sent to the caller; '.callmsg off' clears it
  .callto <@user|+number|id>  (experimental) call someone and play the clip
  .hangup <@user|id>  end a call
  .callstatus       show settings
  .menu             pretty command menu (with image + animation)
  .alive            status card (with image + animation)
  .setalive         reply to a photo -> use it as the alive/menu image
  .alivetext <text> custom line on the alive card ('.alivetext off' clears it)
  .resetalive       back to the default image / text
  .ping             latency
"""
import asyncio
import json
import logging
import os
import platform
import time
from pathlib import Path

from dotenv import load_dotenv
from pyrogram import Client, filters
from pyrogram.errors import PeerIdInvalid, UsernameNotOccupied
from pyrogram.types import InputPhoneContact
from pytgcalls import PyTgCalls, filters as tg_filters
from pytgcalls.exceptions import CallBusy, CallDeclined, NotInCallError, TimedOutAnswer
from pytgcalls.types import ChatUpdate, MediaStream

import ui

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("callbot")

API_ID = int(os.environ["API_ID"])
API_HASH = os.environ["API_HASH"]
SESSION_STRING = os.environ["SESSION_STRING"]
PREFIX = os.getenv("PREFIX", ".")
DATA_DIR = Path(os.getenv("DATA_DIR", "./data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)
SETTINGS_FILE = DATA_DIR / "settings.json"

DEFAULTS = {"mode": "answer", "clip": None, "kind": None, "reject_msg": "", "alive_img": None, "alive_text": ""}
DEFAULT_IMG = Path(__file__).parent / "assets" / "alive.png"
START_TIME = time.time()


# ---------- settings (small JSON file, written atomically) ----------
def load_settings() -> dict:
    try:
        return {**DEFAULTS, **json.loads(SETTINGS_FILE.read_text())}
    except (FileNotFoundError, json.JSONDecodeError):
        return dict(DEFAULTS)


def save_settings(s: dict) -> None:
    tmp = SETTINGS_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(s, indent=2))
    os.replace(tmp, SETTINGS_FILE)


settings = load_settings()

try:
    import tgcrypto  # noqa: F401
    log.info("TgCrypto: ON (fast crypto)")
except ImportError:
    log.warning("TgCrypto: MISSING -> downloads will be slow and may time out")

# one explicit event loop, created BEFORE Pyrogram / PyTgCalls (both grab the current loop when built)
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

app = Client("callbot", api_id=API_ID, api_hash=API_HASH, session_string=SESSION_STRING, in_memory=True)
calls = PyTgCalls(app)

# callers we already handle (stops double-processing the same ring)
_busy: set[int] = set()


def clip_stream() -> MediaStream | None:
    """Build the MediaStream for the saved clip (audio-only clips send no video)."""
    path = settings.get("clip")
    if not path or not Path(path).exists():
        return None
    if settings.get("kind") == "audio":
        return MediaStream(path, video_flags=MediaStream.Flags.IGNORE)
    return MediaStream(path)  # video: ffmpeg auto-detects audio + video


def own(cmd: str):
    """Only messages sent by YOUR account, starting with the prefix + command."""
    return filters.me & filters.command(cmd, prefixes=PREFIX)


# ---------- incoming calls ----------
async def _handle_incoming(user_id: int):
    try:
        mode = settings["mode"]
        if mode == "off":
            return  # let it ring normally
        if mode == "reject":
            await calls.leave_call(user_id)  # declines the ringing call
            if settings["reject_msg"]:
                await app.send_message(user_id, settings["reject_msg"])
            log.info("rejected call from %s", user_id)
            return
        stream = clip_stream()
        if stream is None:
            log.warning("call from %s but no clip saved (.setcall) -> rejecting", user_id)
            await calls.leave_call(user_id)
            return
        await calls.play(user_id, stream)  # play() on an incoming call = accept + stream
        log.info("answered call from %s", user_id)
    except (CallBusy, CallDeclined, TimedOutAnswer, NotInCallError) as e:
        log.info("call %s ended early: %r", user_id, e)
    except Exception:
        log.exception("incoming call handler failed for %s", user_id)
    finally:
        _busy.discard(user_id)


@calls.on_update(tg_filters.chat_update(ChatUpdate.Status.INCOMING_CALL))
async def on_incoming(_, update: ChatUpdate):
    if update.chat_id in _busy:
        return
    _busy.add(update.chat_id)
    asyncio.create_task(_handle_incoming(update.chat_id))  # play() waits for connect, don't block updates


@calls.on_update(tg_filters.stream_end())
async def on_stream_end(_, update):
    """Clip finished -> hang up (only for 1-to-1 calls, chat ids > 0)."""
    if update.chat_id > 0:
        await asyncio.sleep(1)
        try:
            await calls.leave_call(update.chat_id)
        except NotInCallError:
            pass


# ---------- commands ----------
@app.on_message(own("setcall"))
async def set_call(_, m):
    src = m.reply_to_message
    media = src and (src.video or src.animation or src.video_note or src.audio or src.voice or src.document)
    if not media:
        return await m.reply("Reply to a video / audio / voice note with .setcall")
    is_audio = bool(src.audio or src.voice)
    size_mb = (getattr(media, "file_size", 0) or 0) / 1_048_576
    note = await m.reply(f"Downloading... ({size_mb:.0f} MB)")
    dest = DATA_DIR / f"clip_{int(time.time())}"
    last = [0.0]

    async def progress(cur, total):  # edit at most every 5s, never fail the download because of it
        if time.time() - last[0] < 5 or not total:
            return
        last[0] = time.time()
        try:
            await note.edit(f"Downloading... {cur * 100 // total}%")
        except Exception:
            pass

    try:
        path = await asyncio.wait_for(
            src.download(file_name=str(dest) + "_", progress=progress), timeout=600
        )
    except asyncio.TimeoutError:
        return await note.edit("Download timed out (10 min). Try a smaller clip (<30 MB) or restart the server.")
    except Exception as e:
        log.exception("download failed")
        return await note.edit(f"Download failed: {e!r}\nTry a smaller clip, then .setcall again.")
    if not path:
        return await note.edit("Download failed. Try a smaller clip, then .setcall again.")
    old = settings.get("clip")
    settings.update(clip=str(path), kind="audio" if is_audio else "video")
    save_settings(settings)
    if old and old != str(path):
        Path(old).unlink(missing_ok=True)
    await note.edit(f"Saved ({settings['kind']}). Mode: {settings['mode']}")


@app.on_message(own("callpreview"))
async def preview(_, m):
    p = settings.get("clip")
    if not p or not Path(p).exists():
        return await m.reply("No clip saved. Reply to a video with .setcall")
    await m.reply_document(p, caption=f"Call clip ({settings['kind']})")


@app.on_message(own("delcall"))
async def del_call(_, m):
    p = settings.get("clip")
    if p:
        Path(p).unlink(missing_ok=True)
    settings.update(clip=None, kind=None)
    save_settings(settings)
    await m.reply("Clip deleted.")


@app.on_message(own("callmode"))
async def call_mode(_, m):
    arg = (m.command[1] if len(m.command) > 1 else "").lower()
    if arg not in ("answer", "reject", "off"):
        return await m.reply(f"Usage: {PREFIX}callmode answer|reject|off  (now: {settings['mode']})")
    settings["mode"] = arg
    save_settings(settings)
    await m.reply(f"Call mode: {arg}")


@app.on_message(own("callmsg"))
async def call_msg(_, m):
    text = " ".join(m.command[1:]).strip()
    settings["reject_msg"] = "" if text.lower() == "off" else text
    save_settings(settings)
    await m.reply("Reject message cleared." if not settings["reject_msg"] else "Reject message saved.")


async def resolve_user(raw_target: str) -> int:
    """@username, numeric user id or phone number (+94...) -> Telegram user id.
    The session is in-memory, so Pyrogram knows nobody until we resolve them first."""
    t = raw_target.strip().replace(" ", "").replace("-", "")
    if t.startswith("@") or (not t.lstrip("+").isdigit()):
        return (await app.get_users(t.lstrip("@"))).id  # username
    digits = t.lstrip("+")
    if not t.startswith("+"):
        try:  # maybe a real user id we already know
            return (await app.get_users(int(digits))).id
        except (PeerIdInvalid, KeyError):
            if len(digits) < 9:
                raise
    # phone number: import as a contact so Telegram hands us the user + access hash
    res = await app.import_contacts([InputPhoneContact("+" + digits, "Call")])
    if not res.users:
        raise ValueError("That number is not on Telegram (or hides it from non-contacts).")
    await app.fetch_peers(res.users)
    return res.users[0].id


@app.on_message(own("callto"))
async def call_to(_, m):
    if len(m.command) < 2:
        return await m.reply(f"Usage: {PREFIX}callto @username  |  +94771234567  |  user id")
    stream = clip_stream()
    if stream is None:
        return await m.reply("No clip saved. Reply to a video with .setcall")
    try:
        uid = await resolve_user("".join(m.command[1:]))
    except (PeerIdInvalid, UsernameNotOccupied, KeyError):
        return await m.reply("Can't find that user. Use @username or the full number with country code (+94...).")
    except ValueError as e:
        return await m.reply(str(e))
    except Exception as e:
        log.exception("resolve failed")
        return await m.reply(f"Lookup failed: {e!r}")
    await m.reply("Calling...")
    try:
        await calls.play(uid, stream)
    except CallDeclined:
        await m.reply("Declined.")
    except CallBusy:
        await m.reply("Busy.")
    except TimedOutAnswer:
        await m.reply("No answer.")
    except Exception as e:  # experimental path, show the reason
        log.exception("callto failed")
        await m.reply(f"Call failed: {e!r}")


@app.on_message(own("hangup"))
async def hangup(_, m):
    if len(m.command) < 2:
        return await m.reply(f"Usage: {PREFIX}hangup @username|id")
    t = m.command[1]
    try:
        await calls.leave_call(int(t) if t.lstrip("-").isdigit() else t)
        await m.reply("Call ended.")
    except NotInCallError:
        await m.reply("Not in a call with that user.")


@app.on_message(own("callstatus"))
async def status(_, m):
    await m.reply(
        "<b>📊 Call status</b>\n"
        f"┣ mode: <code>{settings['mode']}</code>\n"
        f"┣ clip: <code>{settings['kind'] or 'none'}</code>\n"
        f"┗ reject msg: <code>{settings['reject_msg'] or '-'}</code>"
    )


# ---------- menu / alive (image + animation) ----------
def alive_image() -> str | None:
    """Custom image (.setalive) if it still exists, else the bundled default."""
    custom = settings.get("alive_img")
    if custom and Path(custom).exists():
        return custom
    return str(DEFAULT_IMG) if DEFAULT_IMG.exists() else None


async def animate(m, frames: list[str], delay: float = 0.45):
    """Edit the command message through the frames (looks like a loading animation)."""
    for f in frames:
        try:
            await m.edit_text(f)
        except Exception:  # message edited too fast / not modified -> just skip the frame
            pass
        await asyncio.sleep(delay)


async def send_card(m, caption: str):
    """Replace the animated command message with image + caption (text-only if no image)."""
    img = alive_image()
    try:
        if img:
            await app.send_photo(m.chat.id, img, caption=caption, reply_to_message_id=m.reply_to_message_id)
        else:
            await app.send_message(m.chat.id, caption)
        await m.delete()
    except Exception:
        log.exception("send_card failed, falling back to text")
        await m.edit_text(caption)


@app.on_message(own("menu"))
async def menu(_, m):
    await animate(m, ui.menu_frames(), 0.4)
    await send_card(m, ui.menu_text(PREFIX))


@app.on_message(own("alive"))
async def alive(_, m):
    await animate(m, ui.alive_frames(), 0.45)
    t0 = time.perf_counter()
    await app.get_me()  # real round trip to Telegram = ping
    ping = round((time.perf_counter() - t0) * 1000, 1)
    await send_card(
        m,
        ui.alive_text(
            prefix=PREFIX,
            mode=settings["mode"],
            clip=settings["kind"],
            uptime=ui.fmt_uptime(time.time() - START_TIME),
            ping_ms=ping,
            py=platform.python_version(),
            custom=settings.get("alive_text", ""),
        ),
    )


@app.on_message(own("setalive"))
async def set_alive(_, m):
    src = m.reply_to_message
    if not src or not (src.photo or (src.document and (src.document.mime_type or "").startswith("image/"))):
        return await m.reply("Reply to a photo with .setalive")
    note = await m.reply("Saving image...")
    path = await src.download(file_name=str(DATA_DIR / f"alive_{int(time.time())}_"))
    old = settings.get("alive_img")
    settings["alive_img"] = str(path)
    save_settings(settings)
    if old and old != str(path):
        Path(old).unlink(missing_ok=True)
    await note.edit(f"✅ Alive/menu image updated. Try {PREFIX}alive")


@app.on_message(own("alivetext"))
async def alive_text_cmd(_, m):
    text = " ".join(m.command[1:]).strip()
    if not text:
        return await m.reply(f"Usage: {PREFIX}alivetext <text>   ({PREFIX}alivetext off to clear)")
    settings["alive_text"] = "" if text.lower() == "off" else text[:120]
    save_settings(settings)
    await m.reply("Alive text cleared." if not settings["alive_text"] else "✅ Alive text saved.")


@app.on_message(own("resetalive"))
async def reset_alive(_, m):
    old = settings.get("alive_img")
    if old:
        Path(old).unlink(missing_ok=True)
    settings.update(alive_img=None, alive_text="")
    save_settings(settings)
    await m.reply("Alive image + text reset to default.")


@app.on_message(own("ping"))
async def ping(_, m):
    t0 = time.perf_counter()
    msg = await m.reply("🏓 ...")
    ms = round((time.perf_counter() - t0) * 1000, 1)
    await msg.edit_text(f"🏓 <b>Pong!</b>  <code>{ms} ms</code>")


async def start_health_server():
    """Tiny HTTP server so Render 'Web Service' sees an open port (and so an
    uptime pinger can keep a free instance awake). Only runs if PORT is set."""
    port = os.getenv("PORT")
    if not port:
        return

    async def handle(reader, writer):
        try:
            await reader.read(1024)
            writer.write(b"HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\nContent-Length: 2\r\nConnection: close\r\n\r\nok")
            await writer.drain()
        finally:
            writer.close()

    await asyncio.start_server(handle, "0.0.0.0", int(port))
    log.info("health server listening on port %s", port)


async def main():
    await start_health_server()
    await calls.start()  # also starts the Pyrogram client
    log.info("callbot running (mode=%s)", settings["mode"])
    from pytgcalls import idle
    await idle()


if __name__ == "__main__":
    loop.run_until_complete(main())
