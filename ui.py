"""All the pretty text for the bot (menu / alive / animation frames).
No heavy imports here, so it can be tested on its own.
Telegram photo captions are limited to 1024 chars (non-premium) -> keep texts short."""
from html import escape

BOT_NAME = "𝗖𝗔𝗟𝗟 𝗕𝗢𝗧"
VERSION = "2.0"


def fmt_uptime(seconds: float) -> str:
    s = int(seconds)
    d, s = divmod(s, 86400)
    h, s = divmod(s, 3600)
    m, s = divmod(s, 60)
    parts = [f"{d}d"] if d else []
    parts += [f"{h}h"] if (h or d) else []
    parts += [f"{m}m", f"{s}s"]
    return " ".join(parts)


# ---------- animation frames (edited into the command message, one after another) ----------
def _bar(p: int, width: int = 10) -> str:
    filled = round(width * p / 100)
    return "▰" * filled + "▱" * (width - filled)


def alive_frames() -> list[str]:
    frames = ["<b>⚡ Waking up...</b>"]
    for p in (15, 40, 65, 90, 100):
        frames.append(f"<b>⚡ Booting</b>\n<code>{_bar(p)}  {p}%</code>")
    frames.append("<b>✅ Online!</b>")
    return frames


def menu_frames() -> list[str]:
    return [
        "<b>📂 Opening menu</b>\n<code>▰▱▱▱▱</code>",
        "<b>📂 Opening menu</b>\n<code>▰▰▰▱▱</code>",
        "<b>📂 Opening menu</b>\n<code>▰▰▰▰▰</code>",
    ]


# ---------- captions ----------
def alive_text(*, prefix, mode, clip, uptime, ping_ms, py, custom=""):
    mode_icon = {"answer": "🟢", "reject": "🔴", "off": "⚪"}.get(mode, "⚪")
    lines = [
        f"<b>╭━━━━ ⚡ {BOT_NAME} ⚡ ━━━━╮</b>",
        "",
        "<b>   ✨ I'm Alive &amp; Running ✨</b>",
    ]
    if custom:
        lines += ["", f"<i>{escape(custom)}</i>"]
    lines += [
        "",
        f"<b>┃ 📞 Mode</b>    ›  {mode_icon} <code>{mode}</code>",
        f"<b>┃ 🎞 Clip</b>    ›  <code>{clip or 'none'}</code>",
        f"<b>┃ ⏱ Uptime</b>  ›  <code>{uptime}</code>",
        f"<b>┃ 🏓 Ping</b>     ›  <code>{ping_ms} ms</code>",
        f"<b>┃ 🐍 Python</b>  ›  <code>{py}</code>",
        f"<b>┃ 🔖 Version</b> ›  <code>v{VERSION}</code>",
        "",
        f"<b>╰━━━━━━━━━━━━━━━━━━━╯</b>",
        f"💡 <code>{prefix}menu</code> to see all commands",
    ]
    return "\n".join(lines)


def menu_text(prefix: str) -> str:
    p = prefix
    return (
        f"<b>╭━━━━ 📜 {BOT_NAME} MENU ━━━━╮</b>\n"
        "\n"
        "<b>📞 CALL</b>\n"
        f"┣ <code>{p}setcall</code>  ‣ reply to clip → save\n"
        f"┣ <code>{p}callpreview</code>  ‣ send saved clip\n"
        f"┣ <code>{p}delcall</code>  ‣ delete clip\n"
        f"┣ <code>{p}callmode</code> answer | reject | off\n"
        f"┣ <code>{p}callmsg</code> &lt;text&gt;  ‣ reject message\n"
        f"┣ <code>{p}callto</code> @user  ‣ call + play\n"
        f"┗ <code>{p}hangup</code> @user  ‣ end call\n"
        "\n"
        "<b>🎨 ALIVE</b>\n"
        f"┣ <code>{p}alive</code>  ‣ status card\n"
        f"┣ <code>{p}setalive</code>  ‣ reply to photo → new image\n"
        f"┣ <code>{p}alivetext</code> &lt;text&gt;  ‣ custom line\n"
        f"┗ <code>{p}resetalive</code>  ‣ back to default\n"
        "\n"
        "<b>⚙️ INFO</b>\n"
        f"┣ <code>{p}ping</code> · <code>{p}callstatus</code> · <code>{p}menu</code>\n"
        "\n"
        "<b>╰━━━━━━━━━━━━━━━━━━━━━╯</b>"
    )
