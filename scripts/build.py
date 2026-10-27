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


def download(url, timeout=25):
    """Scarica un URL con User-Agent e timeout esplicito."""
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return response.read()


def stream_is_alive(url):
    """Verifica un flusso con richieste brevi. Non usata nella build:
    evitare un controllo lento di ogni singolo canale.
    """
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

    for req in attempts:
        try:
            with urllib.request.urlopen(req, timeout=10) as response:
                code = getattr(response, "status", 200)
                if 200 <= code < 400:
                    return True
        except urllib.error.HTTPError:
            continue
        except Exception:
            continue

    return False


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
        return int(float(value))
    except ValueError:
        return None


def normalized_name(name):
    value = name.lower().strip()
    for s in ["ⓖ", "Ⓖ", "Ⓢ", "Ⓣ", "Ⓨ"]:
        value = value.replace(s, "")
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def is_local_or_regional(name):
    n = normalized_name(name)
    markers = (
        "sicilia", "locale", "locali", "regione", "regionale",
        "campania", "lazio", "veneto", "emilia", "piemonte",
        "liguria", "toscana", "sardegna", "calabria", "puglia",
        "marche", "umbria", "basilicata", "friuli", "trentino",
        "aosta"
    )
    return any(m in n for m in markers)


def is_radio(name):
    # Esclude le radio audio, ma conserva i canali televisivi musicali.
    n = normalized_name(name)
    if "radio italia tv" in n or "radio kiss kiss tv" in n:
        return False
    return "radio" in n


def is_cartoon(name):
    n = normalized_name(name)
    markers = (
        "boing", "cartoonito", "cartoon", "disney", "nickelodeon",
        "baby tv", "k2", "frisbee", "super!",
        "rai gulp", "rai yoyo", "rai yo yo"
    )
    return n == "super" or any(normalized_name(m) in n for m in markers)


def is_italian(info, name):
    n = normalized_name(name)
    country = normalize_text(get_attr(info, "tvg-country"))
    group = normalize_text(get_attr(info, "group-title"))

    if country in {"it", "italy", "italia"}:
        return True
    if group in {"italy", "italia"}:
        return True

    markers = (
        "rai", "mediaset", "italia", "canale", "la7", "tv8", "nove",
        "sicilia", "lazio", "campania", "veneto", "emilia", "piemonte",
        "liguria", "toscana", "sardegna", "calabria", "puglia", "marche",
        "umbria", "basilicata", "friuli", "trentino", "aosta", "sportitalia",
        "deejay", "rtl", "giallo", "focus", "tgcom", "tg24", "dmax",
        "qvc", "real time", "food network", "telecolor", "gambero"
    )
    return any(m in n for m in markers)


def is_bad_stream(info, stream):
    s = (info + " " + stream).lower()
    bad = (
        "[geo-blocked]", "[not 24/7]", "geo blocked",
        "youtube.com", "youtu.be", "twitch.tv"
    )
    return any(x in s for x in bad)


CHANNEL_NUMBERS = {
    "rai 1": 1, "rai 2": 2, "rai 3": 3, "rete 4": 4, "rete 4 hd": 4,
    "rete4": 4, "canale 5": 5, "canale 5 hd": 5, "canale5": 5,
    "italia 1": 6, "italia1": 6, "la7": 7, "tv8": 8, "nove": 9,
    "20 mediaset": 20, "rai 4": 21, "iris": 22, "rai 5": 23,
    "rai movie": 24, "rai premium": 25, "cielo": 26,
    "paramount network": 27, "tv 2000": 28, "tv2000": 28, "la7d": 29,
    "la5": 30, "real time": 31, "qvc": 32, "food network": 33,
    "cine 34": 34, "cine34": 34, "focus": 35, "rtl 102 5 tv": 36,
    "rtl 102 5": 36, "hse 24": 37, "giallo": 38, "top crime": 39,
    "rai news": 48, "rai news 24": 48, "sky tg24": 50,
    "mediaset tgcom24": 51, "tgcom24": 51, "dmax": 52,
    "italia 53": 53, "rai storia": 54, "mediaset extra": 55,
    "motor trend": 56, "rai sport hd": 57, "rai sport": 58,
    "motor trend italia": 59, "sportitalia": 60, "sportitalia plus": 60,
    "life 120 channel": 61, "donna sport tv": 62, "zelig sport": 63,
    "super tennis": 64, "supertennis": 64, "canale 65": 65,
    "italia 2": 66, "vh1": 67, "ibox it": 68, "deejay tv": 69,
    "radio italia tv": 70, "radio kiss kiss tv": 158, "svizzera italiana 82": 82,
    "canale italia 83": 83, "canale italia 84": 84,
    "test hevc main10": 100, "mtv": 108, "retecapri": 122,
    "rete capri": 122, "italia channel": 123, "arte italia 124": 124,
    "arte italia": 124, "arte italia 125": 125, "gold tv italia": 128,
    "la4 italia": 129, "channel 24": 130, "retetalia": 131,
    "lineagem": 132, "juwelo": 133, "italia 134": 134, "italia 135": 135,
    "italia 136": 136, "hse donna": 137, "air italia": 138,
    "deluxe 139": 139, "linea italia": 140, "italia 141": 141,
    "italia 142": 142, "italia 143": 143, "orler tv": 144,
    "padre pio tv": 145, "rai scuola": 146, "fire tv": 147,
    "italia 148 telesia tv": 148, "telesia tv": 148, "capri casino": 149,
    "italia 150": 150, "mondo calcio": 152, "tv 153": 153,
    "italia 154": 154, "italia 156": 156, "italia 159": 159,
    "italia 160": 160, "cantando ballando": 161, "canale 162": 162,
    "donna shopping": 163, "shopping italia": 164, "canale 165": 165,
    "mediatext it": 166, "ri01 tv": 167, "tele moda": 168,
    "italia tv 3": 170, "odeon 24": 177, "italia tv 2": 179,
    "tg norba 24": 180,
}


def ordered_local_index(name):
    n = normalized_name(name)
    if n in CHANNEL_NUMBERS:
        return CHANNEL_NUMBERS[n]
    aliases = {
        "rtl 102 5 tv": 36, "rtl 102 5": 36, "rete 4 fhd": 4,
        "canale 5 fhd": 5, "20 mediaset hd": 20,
        "rai sport hd": 57, "mediaset tgcom 24": 51,
        "ibox it": 68, "italia tv3": 170, "italia tv2": 179,
    }
    if n in aliases:
        return aliases[n]
    for suffix in (" hd", " fhd", " 4k"):
        if n.endswith(suffix) and n[:-len(suffix)].strip() in CHANNEL_NUMBERS:
            return CHANNEL_NUMBERS[n[:-len(suffix)].strip()]
    return 9999


def channel_sort_key(entry):
    return (entry.get("_sort", 9999), normalized_name(entry["name"]))


print("==============================================")
print("DOWNLOAD PLAYLIST")
print("==============================================")

raw = download(SOURCE, timeout=25)
text = raw.decode("utf-8", errors="replace")
entries = parse_m3u(text)
print(f"Entry ricevute: {len(entries)}")

filtered = []

for entry in entries:
    info = entry["info"]
    stream = entry["stream"]
    name = get_channel_name(info)

    if not name:
        continue

    if is_radio(name):
        continue

    if is_cartoon(name):
        continue

    if is_bad_stream(info, stream):
        continue

    if not is_italian(info, name):
        if not is_local_or_regional(name):
            continue

    entry["name"] = name
    original_chno = get_chno(info)
    number = ordered_local_index(name)
    if number == 9999 and is_local_or_regional(name):
        # Mantieni gli slot locali indicati nella lista (10-19 e 101-105)
        # se la sorgente li possiede; altrimenti li colloca dopo i nazionali.
        number = original_chno if original_chno in list(range(10, 20)) + list(range(101, 106)) else 10
    entry["_sort"] = number
    filtered.append(entry)

print(f"Dopo filtro: {len(filtered)}")

unique = []
seen = set()
for entry in filtered:
    key = normalized_name(entry["name"])
    if key in seen:
        continue
    seen.add(key)
    unique.append(entry)

print(f"Dopo dedupe: {len(unique)}")

# Ordina secondo la numerazione della foto. I locali/regionali non numerati
# vengono in fondo, dopo i canali nazionali.
unique.sort(key=lambda e: (e.get("_sort", 9999), normalized_name(e["name"])))

# Non controlliamo ogni singolo URL: molti server IPTV non rispondono
# alle richieste HEAD e questo può rallentare o bloccare l'aggiornamento.
print(f"Canali selezionati: {len(unique)}")

print()
print("==============================================")
print("DOWNLOAD EPG")
print("==============================================")

try:
    epg_data = download(EPG_SOURCE, timeout=15)
    epg_xml = gzip.decompress(epg_data).decode("utf-8", errors="replace")
    if not epg_xml.lstrip().startswith("<?xml") and "<tv" not in epg_xml[:500]:
        raise ValueError("Il file scaricato non sembra un XMLTV valido")
    EPG_OUTPUT.write_text(epg_xml, encoding="utf-8")
    print("EPG scaricato correttamente")
except Exception as e:
    print(f"EPG non disponibile: {e}")
    EPG_OUTPUT.write_text('<?xml version="1.0" encoding="UTF-8"?>\n<tv></tv>\n', encoding="utf-8")
    print("EPG vuoto scritto, workflow continua")

output_lines = [f'#EXTM3U x-tvg-url="{EPG_URL}"']

for entry in unique:
    info = entry["info"]
    name = entry["name"]
    chno = entry.get("_sort", ordered_local_index(name))
    if chno == 9999:
        chno = get_chno(info) or 9999
    # Sovrascrive tvg-chno esistente: la numerazione deve seguire la foto.
    if re.search(r'(?i)\btvg-chno="[^"]*"', info):
        info = re.sub(r'(?i)\btvg-chno="[^"]*"', f'tvg-chno="{chno}"', info, count=1)
    else:
        comma = info.find(",")
        if comma != -1:
            info = info[:comma] + f' tvg-chno="{chno}"' + info[comma:]

    output_lines.append(info)
    for extra in entry.get("extras", []):
        output_lines.append(extra)
    output_lines.append(entry["stream"])

OUTPUT.write_text("\n".join(output_lines) + "\n", encoding="utf-8")

print()
print("==============================================")
print("PLAYLIST CREATA")
print("==============================================")
print(f"Canali finali: {len(unique)}")
print(f"Playlist: {OUTPUT}")
print(f"EPG: {EPG_OUTPUT}")
print("==============================================")
print("PRIMI CANALI:")

for entry in unique[:20]:
    chno = get_chno(entry["info"])
    if chno is None:
        chno = ordered_local_index(entry["name"])
    print(f"{chno}  {entry['name']}")
