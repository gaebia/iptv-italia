import gzip
import re
import urllib.request
import urllib.error
from pathlib import Path

OUTPUT = Path("playlist_italia.m3u8")
EPG_OUTPUT = Path("epg_italia.xml")

SOURCE = "https://raw.githubusercontent.com/Free-TV/IPTV/master/playlist.m3u8"
EPG_SOURCE = "https://epgshare01.online/epgshare01/epg_ripper_IT1.xml.gz"

EPG_URL = (
    "https://raw.githubusercontent.com/"
    "gaebia/iptv-italia/main/epg_italia.xml"
)

HEADERS = {
    "User-Agent": "Mozilla/5.0 IPTV-Italia-Updater"
}


# ============================================================
# DOWNLOAD
# ============================================================

def download(url):
    request = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(request, timeout=120) as response:
        return response.read()


def stream_is_alive(url):
    if not url:
        return False

    url = url.strip()
    if not url.startswith(("http://", "https://")):
        return False

    attempts = [
        urllib.request.Request(url, headers=HEADERS, method="HEAD"),
        urllib.request.Request(
            url,
            headers={**HEADERS, "Range": "bytes=0-0"},
            method="GET",
        ),
    ]

    for request in attempts:
        try:
            with urllib.request.urlopen(request, timeout=15) as response:
                code = getattr(response, "status", 200)
                if 200 <= code < 400:
                    return True
        except urllib.error.HTTPError:
            continue
        except Exception:
            continue

    return False


# ============================================================
# PARSER M3U
# ============================================================

def parse_m3u(text):
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    entries = []
    i = 0

    while i < len(lines):
        if not lines[i].startswith("#EXTINF"):
            i += 1
            continue

        info = lines[i]
        extras = []
        j = i + 1

        while j < len(lines) and lines[j].startswith("#"):
            if lines[j].startswith("#EXTVLCOPT"):
                extras.append(lines[j])
            j += 1

        if j < len(lines):
            stream = lines[j]
            if stream.startswith(("http://", "https://")):
                entries.append({
                    "info": info,
                    "extras": extras,
                    "stream": stream
                })

        i = j + 1

    return entries


# ============================================================
# NORMALIZZAZIONE E ATTRIBUTI
# ============================================================

def normalize_text(value):
    if value is None:
        return ""

    value = str(value).lower()
    value = value.replace("&", " and ")
    value = re.sub(r"[^a-z0-9\s]+", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def get_attr(info, name):
    match = re.search(rf'{re.escape(name)}="([^"]*)"', info, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return ""


def get_channel_name(info):
    if "," not in info:
        return ""
    return info.split(",", 1)[1].strip()


def get_chno(info):
    value = get_attr(info, "tvg-chno")
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def normalized_name(name):
    value = name.lower().strip()
    for symbol in ["ⓖ", "Ⓖ", "Ⓢ", "Ⓣ", "Ⓨ"]:
        value = value.replace(symbol, "")
    value = re.sub(r"\s+", " ", value)
    return value.strip()


# ============================================================
# FILTRI ITALIANI E BLOCCATI
# ============================================================

ITALIAN_MARKERS = (
    "italy", "italia", "rai", "mediaset", "sky", "tv8", "cielo",
    "canale", "dmax", "sportitalia", "deejay", "rtl", "giallo",
    "focus", "tgcom", "tg24", "top crime", "rai news", "rai sport",
    "italia 1", "italia 2", "tv 2000", "sicilia", "lazio", "campania",
    "veneto", "emilia", "liguria", "piemonte", "toscana", "regione",
    "umbria", "marche", "friuli", "calabria", "puglia", "basilicata",
    "trentino", "veneto", "abruzzo", "sardegna", "lombardia", "emilia romagna",
    "rete 4", "canale 5", "la7", "nove", "real time", "qvc", "food network",
    "paramount", "fox", "mtv", "euronews", "telecolor", "deejay"
)

BLOCKED_PATTERNS = (
    "radio",
    "radiotv",
    "radio italia",
    "radio 105",
    "r101",
    "deejay radio",
    "kiss kiss",
    "m2o",
    "boing",
    "cartoonito",
    "cartoon",
    "disney",
    "nickelodeon",
    "baby tv",
    "k2",
    "frisbee",
    "super!",
    "yoyo",
    "gulp"
)

def is_italian(info):
    country = normalize_text(get_attr(info, "tvg-country"))
    group = normalize_text(get_attr(info, "group-title"))
    name = normalize_text(get_attr(info, "tvg-name"))
    channel_name = normalize_text(get_channel_name(info))
    combined = " ".join(part for part in (country, group, name, channel_name) if part)

    if not combined:
        return False

    if country in {"it", "italy", "italia"}:
        return True

    if group in {"italy", "italia"}:
        return True

    if any(marker in combined for marker in ITALIAN_MARKERS):
        return True

    if re.search(r"\b(rai|mediaset|sky|canale|italia|tv8|cielo|sicilia)\b", combined):
        if re.search(r"\b\d+\b", combined) or re.search(r"\b(ch|tv|hd|it)\b", combined):
            return True

    return False


def is_blocked_name(name):
    value = normalized_name(name)

    if any(p in value for p in BLOCKED_PATTERNS):
        return True

    if "radio" in value:
        return True

    if "youtube" in value:
        return True

    if "twitch" in value:
        return True

    return False


def is_bad_stream(info, stream):
    text = (info + " " + stream).lower()

    if "[geo-blocked]" in text:
        return True
    if "[not 24/7]" in text:
        return True
    if "geo blocked" in text:
        return True
    if "youtube.com" in stream.lower():
        return True
    if "youtu.be" in stream.lower():
        return True
    if "twitch.tv" in stream.lower():
        return True
    return False


# ============================================================
# ORDINE CANALI
# ============================================================

def channel_sort_key(entry):
    name = entry["name"]
    chno = get_chno(entry["info"])
    name_key = normalized_name(name)

    if chno is not None:
        return (0, chno, name_key)

    return (1, 999999, name_key)


# ============================================================
# DOWNLOAD PLAYLIST
# ============================================================

print()
print("==============================================")
print("DOWNLOAD PLAYLIST FREE-TV")
print("==============================================")

raw_playlist = download(SOURCE)
text = raw_playlist.decode("utf-8", errors="replace")
entries = parse_m3u(text)

print(f"Entry ricevute: {len(entries)}")

# ============================================================
# FILTRO ITALIANO + ESCLUSIONE
# ============================================================

italian = []

for entry in entries:
    info = entry["info"]
    stream = entry["stream"]

    if not is_italian(info):
        continue

    if is_bad_stream(info, stream):
        continue

    name = get_channel_name(info)
    if not name:
        continue

    if is_blocked_name(name):
        continue

    entry["name"] = name
    italian.append(entry)

print(f"Canali italiani iniziali: {len(italian)}")

# ============================================================
# DEDUPLICAZIONE
# ============================================================

unique = []
seen_ids = set()
seen_names = set()

for entry in italian:
    info = entry["info"]
    tvg_id = get_attr(info, "tvg-id")
    name_key = normalized_name(entry["name"])

    if tvg_id:
        tvg_id_key = tvg_id.lower()
        if tvg_id_key in seen_ids:
            continue
        seen_ids.add(tvg_id_key)
    else:
        if name_key in seen_names:
            continue
        seen_names.add(name_key)

    unique.append(entry)

print(f"Canali dopo deduplicazione: {len(unique)}")

# ============================================================
# VALIDAZIONE STREAM
# ============================================================

verified = []
removed = 0

for entry in unique:
    if stream_is_alive(entry["stream"]):
        verified.append(entry)
    else:
        removed += 1
        print(f"RThe image shows a dark, modern TV-guide / IPTV interface on a tablet-like screen.

What’s visible:
- A left sidebar with channel numbers and names, including entries like “Rai 1”, “La7”, “Real Time”, “QVC”, “Food Network”, and later “Canale 10”, “Deejay TV”, “R101 TV”, “Radio 105 TVimosso: {entry['name']} -> {entry['stream'][:120]}")

unique = verified
print(f"Canali dopo validazione stream: {len(unique)} (rimossi {removed})")

# ============================================================
# ORDINAMENTO
# ============================================================

unique.sort(key=channel_sort_key)

# ============================================================
# DOWNLOAD EPG ITALIA
# ============================================================

print()
print("==============================================")
print("DOWNLOAD EPG ITALIA")
print”, “Telecolor”.
- A search bar at the top with “playlist_italia.gae” and a small “Real Time” tag.
- A central program grid showing broadcast times and titles, such as:
  - “Tg Regione”
  - “("==============================================")

try:
    epg_gz = download(EPG_SOURCE)
    epg_xml = gzip.decompress(epg_gz).decode("utf-8", errors="replace")
    EPG_OUTPUT.write_text(epg_xml, encoding="utf-8")

    print(f"EPG creato: {EPG_OUTPUT}")
    print(f"Dimensione EPG: {len(epg_xml):,} caratteri")
Tagada, tutto quanto fa…”
  - “Casa a prima vista”
  - “Summer Camp”
- A big time indicator on the right showing “14:15”.
- A blurred background with a soft, off-white / beige image beneath the UI, giving the feeling of a live TVexcept Exception as e:
    print(f"ERRORE EPG: {e}")
    raise

# ============================================================
# OUTPUT PLAYLIST
# ============================================================

output = [f'#EXTM3U x-tvg-url="{EPG_URL}"']

for entry in unique:
    output.append(entry["info"])
    for extra in entry["extras"]:
        output.append(extra)
    output.append(entry["stream"])

OUTPUT.write_text("\n".join(output) + "\n", encoding="utf-8")

# ============================================================
# REPORT
# ============================================================

print()
print("==============================================")
print("PLAYLIST CREATA")
print("==============================================")

print(f"Totale: {len(unique)}")
print(f"File playlist: {OUTPUT}")
print(f"File EPG: {EPG_OUTPUT}")
print("==============================================")

for entry in unique[:30]:
    chno = get_chno(entry["info"])
    if chno is not None:
        print(f"{chno:g}  {entry['name']}")
    else:
        print(f"-  {entry['name']}")
