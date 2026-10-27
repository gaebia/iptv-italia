# ============================================================
# WHITELIST ESATTA: CANALI AMMESSI
# ============================================================

EXACT_ALLOWED = {
    # Rai
    "rai 1",
    "rai 2",
    "rai 3",
    "rai 4",
    "rai 5",
    "rai movie",
    "rai premium",
    "rai sport",
    "rai sport 1",
    "rai sport 2",
    "rai news 24",
    "rai storia",
    "rai scuola",
    "rai gulp",
    "rai yoyo",
    "rai italia",
    "rai 1 hd",
    "rai 2 hd",
    "rai 3 hd",
    "rai 4 hd",
    "rai 5 hd",

    # Mediaset / principali
    "rete 4",
    "canale 5",
    "italia 1",
    "italia 2",
    "20",
    "20 mediaset",
    "iris",
    "tv8",
    "nove",
    "la7",
    "la7d",
    "la7 cinema",
    "dmax",
    "focus",
    "real time",
    "giallo",
    "top crime",
    "qvc",
    "food network",
    "rtl 102.5",
    "discovery channel",
    "sportitalia",
    "sportitalia plus",
    "sportitalia solocalcio",
    "supertennis",
    "tgcom24",
    "tgcom 24",
    "sky tg24",
    "deejay tv",
    "r101 tv",
    "radio 105 tv",
    "gambero rosso",
    "hgtv",
    "home & garden tv",
    "senato tv",
    "camera dei deputati",

    # Sky / nazionali
    "sky tg24",
    "sky sport 24",
    "sky sport arena",
    "sky sport football",
    "sky sport series",
    "sky cinema uno",
    "sky cinema due",
    "sky cinema family",

    # Sicilia
    "telecolor",
    "sicilia mia",
    "sicilia television",
    "canale 10",
    "canale 15",
    "canale 21",
    "san marino rete televisiva",
    "telesud",
    "tv sicilia",
    "sun tv",
    "sicilia tv",
    "telepace sicilia",

    # Extra richiesti
    "sole 24 ore",
    "7 gold",
    "7 gold hd",
}

BLOCKLIST = {
    "boing",
    "cartoonito",
    "cartoon",
    "disney",
    "nickelodeon",
    "baby tv",
    "k2",
    "frisbee",
    "super!",
    "radio",
    "radio italia",
    "radio 105",
    "r101",
    "radio monte carlo",
    "deejay radio",
    "kiss kiss",
    "m2o",
    "rai yoyo",
    "rai gulp",
}

def is_allowed_channel(name):
    value = normalized_name(name)

    if value in BLOCKLIST:
        return False

    if value in EXACT_ALLOWED:
        return True

    return False
