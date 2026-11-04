# Telegram Call Bot (userbot)

ඔයාට එන Telegram call එකක් auto answer කරලා, save කරපු video / audio එකක් call එකට stream කරනවා.
(WhatsApp RIO X MD `callbot` එකේ වගේ idea එක.)

## 1. Setup (එක පාරක්)
1. https://my.telegram.org -> **API development tools** -> app එකක් හදලා `api_id`, `api_hash` ගන්න.
2. `pip install -r requirements.txt`  (සාමාන්‍ය `pyrogram` install කරන්න එපා)
3. `ffmpeg` install කරලා තියෙන්න ඕනේ.
4. `cp .env.example .env` -> `API_ID`, `API_HASH` දාන්න.
5. `python make_session.py` -> number, code (2FA තිබුණොත් password) දාන්න -> `SESSION_STRING` එක print වෙනවා -> `.env` එකේ දාන්න.
6. `python bot.py`

## 2. Commands (ඔයාගේම account එකෙන්, ඕනෑම chat එකක / Saved Messages)
| Command | මොකද කරන්නේ |
|---|---|
| `.setcall` | video / audio / voice note එකකට **reply** කරලා, call clip එක විදිහට save කරනවා |
| `.callmode answer` / `reject` / `off` | call එකක් ආවම answer කරනවා / reject කරනවා / ඉබේ ring වෙනවා |
| `.callmsg <text>` | reject කරද්දී caller ට යවන message එක (`.callmsg off` = ඉවත් කරනවා) |
| `.callpreview` | save කරපු clip එක ආපහු එවනවා |
| `.delcall` | clip එක මකනවා |
| `.callto @user` | (experimental) අනිත් කෙනාට call කරලා clip එක play කරනවා |
| `.hangup @user` | call එක කපනවා |
| `.callstatus` | settings පෙන්වනවා |
| `.menu` | animation එකකින් පස්සේ image එක සමඟ lassana command menu එක පෙන්වනවා |
| `.alive` | animation + image + status card (mode, clip, uptime, ping) |
| `.setalive` | photo එකකට **reply** කරලා alive/menu image එක වෙනස් කරනවා |
| `.alivetext <text>` | alive card එකට ඔයාගේම line එකක් (`.alivetext off` = ඉවත් කරනවා) |
| `.resetalive` | image + text default වලට හරවනවා |
| `.ping` | latency |

Clip එක ඉවර වුණාම call එක ඉබේ කැපෙනවා.

## 3. Deploy (Docker)
`docker build -t tgcall .` -> run කරද්දී env 3 (`API_ID`, `API_HASH`, `SESSION_STRING`) දාන්න, `/var/data` එකට persistent disk එකක් mount කරන්න (clip + settings එතන save වෙනවා).

## ⚠️ අවවාද
- `SESSION_STRING` = ඔයාගේ account එකේ password එක වගේමයි. කාටවත් දෙන්න එපා, GitHub එකට දාන්න එපා.
- Userbot එකක් Telegram ToS එකට හොඳට ගැළපෙන්නේ නෑ. ඔයාගේම (හැකි නම් වෙනම) account එකක් විතරක් පාවිච්චි කරන්න, spam / bulk එපා.
- Telegram වෙනස් වුණොත් library එක update වෙනකම් වැඩ නොකර හිටින්න පුළුවන්.
