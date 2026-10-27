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
        except urllib.error.HTTPError as exc:
            if exc.code in {403, 404, 410, 451, 500, 502, 503, 504}:
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
# ATTRIBUTI / NORMALIZZAZIONE
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
# FILTRI ITALIANI
# ============================================================

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

    italian_markers = (
        "italy", "italia", "rai", "mediaset", "sky", "tv8", "cielo",
        "canale", "dmax", "sportitalia", "deejay", "rtl", "giallo",
        "focus", "tgcom", "tg24", "top crime", "rai news", "rai sport",
        "italia 1", "italia 2", "tv 2000", "sicilia", "lazio", "campania",
        "veneto", "emilia", "liguria", "piemonte", "toscana", "umbria",
        "marche", "basilicata", "calabria", "puglia", "friuli", "trentino",
        "sardegna", "valle d aosta", "aosta", "regione", "regionale",
        "sole 24 ore", "7 gold", "telecolor", "canale 10", "canale 21",
        "canale 5", "rete 4", "la7", "nove", "real time", "qvc",
        "food network", "gambero rosso", "senato", "camera dei deputati"
    )

    if any(marker in combined for marker in italian_markers):
        return True

    if re.search(r"\b(rai|mediaset|sky|canale|italia|tv8|cielo|sicilia|lazio|campania|veneto|emilia|liguria|piemonte|toscana)\b", combined):
        if re.search(r"\b\d+\b", combined) or re.search(r"\b(ch|tv|hd|it)\b", combined):
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
# ESCLUSIONE RADIO / CARTONI / STRANIERI
# ============================================================

BLOCKLIST = {
    "boing", "cartoonito", "cartoon", "disney", "nickelodeon",
    "baby tv", "k2", "frisbee", "super!", "super", "rai yoyo", "rai gulp",
    "radio", "radio italia", "radio 105", "r101", "radio monte carlo",
    "deejay radio", "kiss kiss", "m2o", "news radio"
}


def is_blocked_name(name):
    value = normalized_name(name)

    if "radio" in value:
        return True

    if any(token in value for token in BLOCKLIST):
        return True

    if any(token in value for token in ("boing", "cartoonito", "disney", "nickelodeon", "baby tv", "k2", "frisbee")):
        return True

    return False


def is_allowed_channel(info, name):
    value = normalized_name(name)

    if is_blocked_name(name):
        return False

    if any(token in value for token in (
        "rai", "mediaset", "sky", "italia", "sicilia", "la7", "tv8",
        "nove", "rete 4", "canale 5", "real time", "qvc", "food network",
        "dmax", "sportitalia", "tgcom", "tg24", "giallo", "focus",
        "senato", "camera dei deputati", "gambero", "deejay", "rtl",
        "lazio", "campania", "veneto", "emilia", "liguria", "piemonte",
        "toscana", "umbria", "marche", "puglia", "calabria", "sardegna",
        "basilicata", "friuli", "trentino", "aosta", "7 gold", "sole 24 ore",
        "telecolor", "canale 10", "canale 21"
    )):
        return True

    if get_chno(info) is not None and is_italian(info):
        return True

    return False


# ============================================================
# ORDINE CANALI
# ============================================================

NATIONAL_CHANNELS = {
    "rai 1", "rai 2", "rai 3", "rai 4", "rai 5",
    "rai movie", "rai premium", "rai sport", "rai news 24",
    "rai storia", "rai scuola", "rai italia",
    "rete 4", "canale 5", "italia 1", "italia 2",
    "la7", "tv8", "nove", "20", "20 mediaset",
    "iris", "cielo", "real time", "qvc", "food network", "dmax",
    "focus", "giallo", "top crime", "deejay tv", "r101 tv", "radio 105 tv",
    "tgcom24", "tgcom 24", "sky tg24", "sportitalia", "senato tv",
    "camera dei deputati", "gambero rosso", "hgtv", "home & garden tv",
    "sole 24 ore", "7 gold", "telecolor"
}


def channel_sort_key(entry):
    name = entry["name"]
    chno = get_chno(entry["info"])
    name_key = normalized_name(name)

    if name_key in NATIONAL_CHANNELS and chno is not None:
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
# FILTRO ITALIANO + TOLLERANZA
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

    if not is_allowed_channel(info, name):
        continue

    entry["name"] = name
    italian.append(entry)

print(f"Canali italiani: {len(italian)}")


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
        id_key = tvg_id.lower()
        if id_key in seen_ids:
            continue
        seen_ids.add(id_key)
    else:
        if name_key in seen_names:
            continue
        seen_names.add(name_key)

    unique.append(entry)

print(f"Canali dopo deduplicazione: {len(unique)}")


# ============================================================
# STREAM MORTI
# ============================================================

verified = []
removed = 0

for entry in unique:
    if stream_is_alive(entry["stream"]):
        verified.append(entry)
    else:
        removed += 1

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
print("==============================================")

try:
    epg_gz = download(EPG_SOURCE)
    epg_xml = gzip.decompress(epg_gz).decode("utf-8", errors="replace")
    EPG_OUTPUT.write_text(epg_xml, encoding="utf-8")
    print(f"EPG creato: {EPG_OUTPUT}")
    print(f"Dimensione EPG: {len(epg_xml):,} caratteri")
except Exception as e:
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
# REPORT FINALE
# ============================================================

print()
print("==============================================")
print("PLAYLIST CREATA")
print("==============================================")

print(f"Totale:              {len(unique)}")
print(f"File playlist:        {OUTPUT}")
print(f"File EPG:             {EPG_OUTPUT}")
print("==============================================")

print()
print("PRIMI CANALI:")

for entry in unique[:25]:
    chno = get_chno(entry["info"])
    if chno is not None:
        print(f"{chno:g}  {entry['name']}")
    else:
        print(f"-  {entry['name']}")
