import gzip
import re
import urllib.request
import urllib.error
from pathlib import Path

OUTPUT = Path("playlist_italia.m3u8")
EPG_OUTPUT = Path("epg_italia.xml")
SOURCE = "https://raw.githubusercontent.com/Free-TV/IPTV/master/playlist.m3u8"
EPG_SOURCE = "https://epgshare01.online/epgshare01/epg_ripper_IT1.xml.gz"
EPG_URL = "https://raw.githubusercontent.com/gaebia/iptv-italia/main/epg_italia.xml"
HEADERS = {"User-Agent": "Mozilla/5.0 IPTV-Italia-Updater"}


def download(url, timeout=25):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return response.read()


def parse_m3u(text):
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    entries, i = [], 0
    while i < len(lines):
        if not lines[i].startswith("#EXTINF"):
            i += 1
            continue
        info, extras, j = lines[i], [], i + 1
        while j < len(lines) and lines[j].startswith("#"):
            if lines[j].startswith("#EXTVLCOPT"):
                extras.append(lines[j])
            j += 1
        if j < len(lines) and lines[j].startswith(("http://", "https://")):
            entries.append({"info": info, "extras": extras, "stream": lines[j]})
        i = j + 1
    return entries


def normalize_text(value):
    value = (value or "").lower().replace("&", " and ")
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9\s]+", " ", value)).strip()


def get_attr(info, name):
    m = re.search(rf'{re.escape(name)}="([^"]*)"', info, re.I)
    return m.group(1).strip() if m else ""


def get_channel_name(info):
    return info.split(",", 1)[1].strip() if "," in info else ""


def normalized_name(name):
    return re.sub(r"\s+", " ", (name or "").lower().strip())


def is_radio(name):
    n = normalized_name(name)
    if "radio italia tv" in n or "radio kiss kiss tv" in n or "r101 tv" in n:
        return False
    return "radio" in n


def is_cartoon(name):
    n = normalized_name(name)
    markers = ("boing", "cartoonito", "cartoon", "disney", "nickelodeon", "baby tv", "k2", "frisbee", "rai gulp", "rai yoyo", "rai yo yo")
    return n == "super" or any(m in n for m in markers)


def is_sicilian(name, info=""):
    t = normalize_text(name + " " + info + " " + get_attr(info, "group-title"))
    markers = ("sicilia", "siciliana", "siciliano", "palermo", "catania", "messina", "siracusa", "trapani", "ragusa", "enna", "caltanissetta", "agrigento", "taormina", "etna", "canicatti", "marsala", "mazara", "modica", "acireale", "gela", "milazzo", "cefalu", "bagheria", "termini imerese")
    return any(m in t for m in markers)


def is_local_or_regional(name):
    n = normalize_text(name)
    markers = ("sicilia", "locale", "locali", "regione", "regionale", "campania", "lazio", "veneto", "emilia", "piemonte", "liguria", "toscana", "sardegna", "calabria", "puglia", "marche", "umbria", "basilicata", "friuli", "trentino", "aosta")
    return any(m in n for m in markers)


def is_italian(info, name):
    country = normalize_text(get_attr(info, "tvg-country"))
    group = normalize_text(get_attr(info, "group-title"))
    # Se la fonte dichiara un paese non italiano, non fidarsi del solo nome (es. TV8 Mongolia).
    if country and country not in {"it", "italy", "italia"}:
        return False
    if country in {"it", "italy", "italia"} or group in {"italy", "italia"}:
        return True
    n = normalize_text(name)
    markers = ("rai", "mediaset", "italia", "canale", "la7", "tv8", "nove", "sicilia", "lazio", "campania", "veneto", "emilia", "piemonte", "liguria", "toscana", "sardegna", "calabria", "puglia", "marche", "umbria", "basilicata", "friuli", "trentino", "aosta", "sportitalia", "deejay", "rtl", "giallo", "focus", "tgcom", "tg24", "dmax", "qvc", "real time", "food network", "telecolor", "gambero")
    return any(m in n for m in markers)


# Numerazione nazionale conforme alla lista dell'utente.
CHANNEL_NUMBERS = {
    "rai 1": 1, "rai 2": 2, "rai 3": 3,
    "rete 4": 4, "rete4": 4, "rete 4 hd": 4, "rete 4 fhd": 4,
    "canale 5": 5, "canale5": 5, "canale 5 hd": 5, "canale 5 fhd": 5,
    "italia 1": 6, "italia1": 6, "la7": 7, "tv8": 8, "tv8 hd": 8, "nove": 9,
    "20 mediaset": 20, "20 mediaset hd": 20, "rai 4": 21, "iris": 22, "rai 5": 23,
    "rai movie": 24, "rai premium": 25, "cielo": 26, "paramount network": 27,
    "tv 2000": 28, "tv2000": 28, "la7d": 29, "la5": 30, "real time": 31,
    "qvc": 32, "food network": 33, "cine 34": 34, "cine34": 34, "focus": 35,
    "rtl 102 5 tv": 36, "rtl 102 5": 36, "hse 24": 37, "giallo": 38, "top crime": 39,
    "rai news": 48, "rai news 24": 48, "sky tg24": 50, "mediaset tgcom24": 51,
    "tgcom24": 51, "dmax": 52, "rai storia": 54, "mediaset extra": 55,
    "motor trend": 56, "rai sport hd": 57, "rai sport+ hd": 57, "rai sport": 58,
    "sportitalia": 60, "sportitalia plus": 60, "super tennis": 64, "supertennis": 64,
    "canale 65": 65, "italia 2": 66, "deejay tv": 69, "radio italia tv": 70,
    "svizzera italiana 82": 82, "canale italia 83": 83, "canale italia 84": 84,
    "test hevc main10": 100, "mtv": 108, "retecapri": 122, "rete capri": 122,
    "italia channel": 123, "arte italia 124": 124, "arte italia": 124,
    "arte italia 125": 125, "gold tv italia": 128, "la4 italia": 129, "channel 24": 130,
    "retetalia": 131, "lineagem": 132, "juwelo": 133, "italia 134": 134,
    "italia 135": 135, "italia 136": 136, "hse donna": 137, "air italia": 138,
    "deluxe 139": 139, "linea italia": 140, "italia 141": 141, "italia 142": 142,
    "italia 143": 143, "orler tv": 144, "padre pio tv": 145, "rai scuola": 146,
    "fire tv": 147, "italia 148 telesia tv": 148, "telesia tv": 148, "capri casino": 149,
    "italia 150": 150, "mondo calcio": 152, "tv 153": 153, "italia 154": 154,
    "italia 155": 155, "italia 156": 156, "italia 159": 159, "italia 160": 160,
    "cantando ballando": 161, "canale 162": 162, "donna shopping": 163,
    "shopping italia": 164, "canale 165": 165, "mediatext it": 166,
    "r101 tv": 167, "tele moda": 168, "italia tv 3": 170, "odeon 24": 177,
    "italia tv 2": 179, "tg norba 24": 180, "radio kiss kiss tv": 158,
}

# Ordine prioritario delle locali siciliane nello slot 10-19.
SICILIAN_ORDER = (
    "antenna sicilia", "canale 74 sicilia", "onda tv sicilia", "prima tv sicilia",
    "sicilia 24 tv", "sicilia tv", "telecolor sicilia", "tgs telegiornale di sicilia",
    "video regione sicilia", "teleone", "tele jato", "trm",
)


def channel_number(name):
    n = normalize_text(name)
    if n in CHANNEL_NUMBERS:
        return CHANNEL_NUMBERS[n]
    # Normalizza varianti HD/FHD senza cambiare il numero del canale.
    for suffix in (" hd", " fhd", " 4k"):
        if n.endswith(suffix) and n[:-len(suffix)].strip() in CHANNEL_NUMBERS:
            return CHANNEL_NUMBERS[n[:-len(suffix)].strip()]
    return None


def sort_key(entry):
    return (entry["_sort"], normalize_text(entry["name"]))


print("DOWNLOAD PLAYLIST")
entries = parse_m3u(download(SOURCE).decode("utf-8", errors="replace"))
print(f"Entry ricevute: {len(entries)}")
filtered = []
for e in entries:
    info, stream = e["info"], e["stream"]
    name = get_channel_name(info)
    if not name or is_radio(name) or is_cartoon(name):
        continue
    bad = ("[geo-blocked]", "[not 24/7]", "geo blocked", "youtube.com", "youtu.be", "twitch.tv")
    if any(x in (info + " " + stream).lower() for x in bad):
        continue
    if not is_italian(info, name) and not is_local_or_regional(name):
        continue
    e["name"] = name
    num = channel_number(name)
    e["_number"] = num
    e["_sicilian"] = is_sicilian(name, info)
    e["_regional"] = num is None and is_local_or_regional(name)
    filtered.append(e)

# Deduplica per nome normalizzato, preservando il primo URL della fonte.
unique, seen = [], set()
for e in filtered:
    key = normalize_text(e["name"])
    if key not in seen:
        seen.add(key)
        unique.append(e)

# Assegna i numeri 10-19 esclusivamente alle locali siciliane riconosciute.
sicilian = [e for e in unique if e["_regional"] and e["_sicilian"]]
other_regional = [e for e in unique if e["_regional"] and not e["_sicilian"]]
def sicily_key(e):
    n = normalize_text(e["name"])
    for i, label in enumerate(SICILIAN_ORDER):
        if label in n:
            return (i, n)
    return (len(SICILIAN_ORDER), n)

for i, e in enumerate(sorted(sicilian, key=sicily_key)):
    e["_sort"] = 10 + i if i < 10 else 181 + i - 10
for i, e in enumerate(sorted(other_regional, key=lambda x: normalize_text(x["name"]))):
    e["_sort"] = 191 + i
for e in unique:
    if not e["_regional"]:
        e["_sort"] = e["_number"] if e["_number"] is not None else 9999
unique.sort(key=sort_key)
print(f"Canali selezionati: {len(unique)}")

print("DOWNLOAD EPG")
try:
    data = download(EPG_SOURCE, timeout=15)
    xml = gzip.decompress(data).decode("utf-8", errors="replace")
    if "<tv" not in xml[:1000]:
        raise ValueError("XMLTV non valido")
    EPG_OUTPUT.write_text(xml, encoding="utf-8")
    print("EPG scaricato correttamente")
except Exception as exc:
    print(f"EPG non disponibile: {exc}")
    # Non sostituire un EPG valido già presente con un file vuoto in caso di errore temporaneo.
    if not EPG_OUTPUT.exists() or EPG_OUTPUT.stat().st_size == 0:
        EPG_OUTPUT.write_text('<?xml version="1.0" encoding="UTF-8"?>\n<tv></tv>\n', encoding="utf-8")

out = [f'#EXTM3U x-tvg-url="{EPG_URL}"']
for e in unique:
    info = e["info"]
    num = e["_sort"]
    if re.search(r'(?i)\btvg-chno="[^"]*"', info):
        info = re.sub(r'(?i)\btvg-chno="[^"]*"', f'tvg-chno="{num}"', info, count=1)
    else:
        comma = info.find(",")
        if comma >= 0:
            info = info[:comma] + f' tvg-chno="{num}"' + info[comma:]
    out.append(info)
    out.extend(e.get("extras", []))
    out.append(e["stream"])
OUTPUT.write_text("\n".join(out) + "\n", encoding="utf-8")
print(f"Playlist creata: {OUTPUT} ({len(unique)} canali)")
print(f"EPG: {EPG_OUTPUT}")
for e in unique[:20]:
    print(f'{e["_sort"]}  {e["name"]}')
