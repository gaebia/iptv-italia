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
# HELPERS
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
        return int(float(value))
    except ValueError:
        return None


def normalized_name(name):
    value = name.lower().strip()
    for s in ["ⓖ", "Ⓖ", "Ⓢ", "Ⓣ", "Ⓨ"]:
        value = value.replace(s, "")
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def get_fallback_chno(name, info):
    n = normalized_name(name)

    # canali locali / siciliani / regionali
    if any(k in n for k in ("sicilia", "locale", "regione", "regionale", "locali", "nazionale", "tv")):
        # lascia i locali in 10-19
        if "sicilia" in n or "locale" in n or "regione" in n:
            return 10 + (abs(hash(n)) % 10)

    # se è un canale italiano mainstream ma senza numero
    if any(k in n for k in ("rai", "mediaset", "italia", "rete 4", "canale 5", "la7", "tv8", "nove")):
        return 999

    return 9999


def stream_is_alive(url):
    if not url:
        return False
    url = url.strip()
    if not url.startswith(("http://", "https://")):
        return False

    attempts = [
        urllib.request.Request(url, headers=HEADERS, method="HEAD"),
        urllib.request.Request(url, headers={**HEADERS, "Range": "bytes=0-0"}, method="GET")
    ]

    for req in attempts:
        try:
            with urllib.request.urlopen(req, timeout=15) as response:
                code = getattr(response, "status", 200)
                if 200 <= code < 400:
                    return True
        except urllib.error.HTTPError:
            continue
        except Exception:
            continue

    return False


# ============================================================
# PARSE M3U
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
# FILTERS
# ============================================================

def is_radio(name):
    n = normalized_name(name)
    return "radio" in n or n.startswith("radio ")


def is_cartoon(name):
    n = normalized_name(name)
    markers = (
        "boing", "cartoonito", "cartoon", "disney", "nickelodeon",
        "baby tv", "k2", "frisbee", "super!", "super"
    )
    return any(m in n for m in markers)


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
        "[geo-blocked]", "[not 24/7]", "geo blocked", "youtube.com",
        "youtu.be", "twitch.tv"
    )
    return any(x in s for x in bad)


def normalize_channel_line(info, name, chno):
    # prende l'EXTINF originale e inserisce il numero se mancante
    # se già c'è, lo lascia
    existing = info
    if chno is not None:
        if 'tvg-chno=' not in existing.lower():
            # forma compatta
            # #EXTINF:-1 tvg-id="..." tvg-name="..." tvg-country="IT" group-title="Italy",Nome
            # lo trasformiamo con tvg-chno
            base = existing.replace(",", ",", 1)
            # inseriamo subito dopo tvg-name
            pos = existing.find('tvg-name=')
            if pos != -1:
                end = existing.find('",', pos)
                if end != -1:
                    prefix = existing[:end + 2]
                    suffix = existing[end + 2:]
                    return f'{prefix} tvg-chno="{chno}"{suffix}'
    return existing


# ============================================================
# SORT
# ============================================================

def channel_sort_key(entry):
    info = entry["info"]
    name = entry["name"]
    chno = get_chno(info)
    if chno is None:
        chno = get_fallback_chno(name, info)
    return (0, chno, normalized_name(name))


# ============================================================
# MAIN
# ============================================================

print("==============================================")
print("DOWNLOAD PLAYLIST")
print("==============================================")

raw = download(SOURCE)
text = raw.decode("utf-8", errors="replace")
entries = parse_m3u(text)

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
        # lascia solo canali italiani o regionali siciliani
        if not is_local_or_regional(name):
            continue

    entry["name"] = name
    filtered.append(entry)

print(f"Totale dopo primo filtro: {len(filtered)}")

# dedupe
seen = set()
unique = []
for entry in filtered:
    key = normalized_name(entry["name"])
    if key in seen:
        continue
    seen.add(key)
    unique.append(entry)

print(f"Totale dopo dedupe: {len(unique)}")

# stream valid check
checked = []
for entry in unique:
    if stream_is_alive(entry["stream"]):
        checked.append(entry)
    else:
        pass

unique = checked
print(f"Totale dopo check stream: {len(unique)}")

# numerazione / ordine
for entry in unique:
    info = entry["info"]
    name = entry["name"]
    chno = get_chno(info)
    if chno is None:
        chno = get_fallback_chno(name, info)
        if chno is not None:
            entry["fallback_chno"] = chno
        else:
            entry["fallback_chno"] = 9999
    else:
        entry["fallback_chno"] = chno

unique.sort(key=channel_sort_key)

# write playlist
output_lines = ['#EXTM3U x-tvg-url="https://raw.githubusercontent.com/gaebia/iptv-italia/main/epg_italia.xml"']

for entry in unique:
    info = entry["info"]
    name = entry["name"]
    chno = get_chno(info)
    if chno is None:
        chno = entry.get("fallback_chno", 9999)
    new_info = normalize_channel_line(info, name, chno)
    output_lines.append(new_info)
    for extra in entry.get("extras", []):
        output_lines.append(extra)
    output_lines.append(entry["stream"])

OUTPUT.write_text("\n".join(output_lines) + "\n", encoding="utf-8")

# EPG fallback
try:
    epg_gz = download(EPG_SOURCE)
    epg_xml = gzip.decompress(epg_gz).decode("utf-8", errors="replace")
    EPG_OUTPUT.write_text(epg_xml, encoding="utf-8")
    print("EPG OK")
except Exception:
    EPG_OUTPUT.write_text("<tv></tv>", encoding="utf-8")
    print("EPG fallback vuoto")

print()
print("==============================================")
print("PLAYLIST COMPLETA")
print("==============================================")
print(f"Canali finali: {len(unique)}")
print(f"File playlist: {OUTPUT}")
print(f"File EPG: {EPG_OUTPUT}")
print("==============================================")

for entry in unique[:30]:
    chno = get_chno(entry["info"])
    if chno is None:
        chno = entry.get("fallback_chno", 9999)
    print(f"{chno}  {entry['name']}")
