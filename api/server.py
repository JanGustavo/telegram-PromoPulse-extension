import asyncio
import json
import os
import re
import unicodedata
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from bs4 import BeautifulSoup
from fastapi import FastAPI, HTTPException, Query
from telethon import TelegramClient, events
from telethon.errors import SessionPasswordNeededError
from telethon.errors.rpcerrorlist import (
    PhoneCodeInvalidError,
    PhoneNumberInvalidError,
    SendCodeUnavailableError,
)

from api import db
from api.models import (
    AlertsResponse,
    FilterPreviewResponse,
    GroupsResponse,
    LoginRequest,
    OfferRequest,
    OfferTestResponse,
    PhoneRequest,
    PriceHistoryResponse,
    StartWatchRequest,
    StartWatchResponse,
    StopWatchResponse,
    WatchConfigRequest,
    WatchConfigResponse,
    WatchStatusResponse,
)

# ===========================================================================
# 1. CONFIGURAÇÕES E CONSTANTES
# ===========================================================================


def _load_env_file(base_dir: Path) -> None:
    env_path = base_dir / ".env"
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


BASE_DIR = Path(__file__).resolve().parent.parent
_load_env_file(BASE_DIR)

api_id = os.getenv("API_ID") or os.getenv("TELEGRAM_API_ID")
api_hash = os.getenv("API_HASH") or os.getenv("TELEGRAM_API_HASH")

if not api_id or not api_hash:
    raise RuntimeError(
        "Credenciais do Telegram nao configuradas.\n"
        "1. Verifique se o arquivo .env existe com API_ID e API_HASH\n"
        "2. Ou use TELEGRAM_API_ID e TELEGRAM_API_HASH (https://my.telegram.org/apps)\n"
        "3. Reinicie a API"
    )

try:
    api_id = int(api_id)
except (TypeError, ValueError) as error:
    raise RuntimeError("API_ID deve ser um numero inteiro valido.") from error

# ---- Filtro de Qualidade de Grupos ----
GROUP_QUALITY_BLOCKLIST: list[re.Pattern] = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"\b(v|grupo|group|canal|sala|room|chat)\s*\d{1,3}$",
        r"_(q|p|m|a|ww|qq)\d{1,3}$",
        r"-canal\s+oficial",
        r"canal\s+oficial",
        r"\boficial_",
        r"^[a-z0-9]{4,6}\s+(brasil|oficial|club)",
        r"\b(kk76|p933|688xt|kkn)\b",
        r"^[A-Z]{2,4}\d{1,3}$",
        r"\bquant(um)?\b",
        r"\bsignal(s)?\b",
        r"\bexchange\b",
        r"\bforecast\b",
        r"\bwealth\s+learning\b",
        r"\bhall\s+(planning|analysis)\b",
        r"\bresultados\s+reais\b",
        r"\bcrypt(o|omoeda)s?\b",
        r"\bbitcoin\b",
        r"\btoken\b",
        r"\bairdrop\b",
        r"\bforex\b",
        r"\binvestimento(s)?\b",
        r"\bganho(s)?\b",
        r"\brenda\s*(extra|passiva)\b",
        r"\bsorte\d*\b",
        r"\bvip\s+expert\b",
        r"\bcassino\b",
        r"\bapostas?\b",
        r"\bbetting\b",
        r"\bsorteio\b",
        r"\brateio\b",
        r"\bfilmes?\s+(in\s+drive|drive)\b",
        r"\bin\s+drive\b",
        r"\bmestre\s+dos\s+cursos\b",
        r"\bcatálogo\b",
        r"^\d{1,3}\s+gruh$",
        r"^\d{2,4}$",
        r"https?://",
        r"t\.me/",
        r"\bsteam\b",
        r"\bgiveaway\b",
        r"\bhack(er|ing|ado)?\b",
        r"\binvas[aã]o\b",
        r"\bcybersecurity\b",
        r"\bciberseguran[cç]a\b",
        r"\bbounty\b",
        r"\bhackersec\b",
        r"\bacademy\b",
        r"\bai\s+strategy\b",
        r"18\s*\+",
        r"\badult\b",
        r"\bxxx\b",
        r"\bnude(s)?\b",
        r"\bspam\b",
        r"\bpropaganda\b",
        r"\bpublicidade\b",
        r"\bgrátis\b",
        r"\bfree\s*money\b",
        r"[\u0600-\u06FF\u0750-\u077F]{3,}",
        r"[\u0400-\u04FF]{4,}",
        r"[\u4E00-\u9FFF]{2,}",
    ]
]

# ---- Configuração de Monitoramento ----
WATCH_CONFIG = {
    "active_levels": ["broad"],
    "broad_categories": ["celulares"],
    "mid_categories": [],
    "specific_models": [],
    "mid_brands": [],
    "broad_keywords": [],
    "price_max": None,
    "min_score": 2,
    "require_offer_match": True,
    "relaxed_mode": False,
}

# ---- Estado Global ----
monitoring_active = False
monitoring_task = None
phone_number = None
phone_code_hash = None
active_group_ids = set()
processed_msg_ids = set()

# ===========================================================================
# 2. REGRAS DE CATEGORIAS E OFERTAS
# ===========================================================================

CATEGORY_RULES = {
    "celulares": {
        "strong_keywords": [
            r"\bcelular(es)?\b",
            r"\bsmartphone(s)?\b",
            r"\biphone\b",
            r"\bgalaxy\b",
            r"\bpoco\b",
            r"\bredmi\b",
        ],
        "ambiguous_brands": [r"\bsamsung\b", r"\bmotorola\b", r"\bxiaomi\b", r"\blg\b", r"\basus\b", r"\bapple\b"],
        "context_modifiers": [r"\b[a-z]\d{2,3}\b", r"\bedge\b", r"\bnote\b", r"\bpro\b", r"\bultra\b"],
        "exclude": [
            r"\btab\b",
            r"\btablet\b",
            r"\bwatch\b",
            r"\bbook\b",
            r"\bfone\b",
            r"\bbuds\b",
            r"\bmacbook\b",
            r"\btv\b",
            r"\bcapa(s)?\b",
            r"\bcase(s)?\b",
            r"\bpel[ií]cula(s)?\b",
        ],
    },
    "tvs": {
        "strong_keywords": [r"\btv(s)?\b", r"\bsmart\s?tv\b", r"\bsmartv\b", r"\btelevis[aã]o\b"],
        "ambiguous_brands": [r"\bsamsung\b", r"\blg\b", r"\bphilips\b", r"\btcl\b", r"\baoc\b"],
        "context_modifiers": [r"\b\d{2}\s?(polegadas|pol|\"|'')\b", r"\b4k\b", r"\b8k\b", r"\boled\b", r"\bqled\b"],
        "exclude": [r"\bmonitor\b", r"\bcelular\b", r"\bsmartphone\b"],
    },
    "audio": {
        "strong_keywords": [r"\bfone(s)?\b", r"\bheadset\b", r"\bearbuds\b", r"\bairpods\b"],
        "ambiguous_brands": [r"\bjbl\b", r"\bsony\b", r"\bedifier\b", r"\bapple\b", r"\bsamsung\b"],
        "context_modifiers": [r"\bbluetooth\b", r"\bsem\s*fio\b", r"\banc\b", r"\bnoise\s*cancelling\b"],
        "exclude": [r"\bcaixa\s*vazia\b", r"\bcapa\b", r"\bcase\b"],
    },
    "higiene": {
        "strong_keywords": [
            r"\bshampoo\b",
            r"\bdesodorante\b",
            r"\bpast[aã]o\b",
            r"\bgillette\b",
            r"\bsabonete\b",
            r"\bfralda\b",
            r"\bpampers\b",
        ],
        "ambiguous_brands": [r"\bdove\b", r"\bl[oó]re[aá]l\b", r"\bnivea\b", r"\brexona\b"],
        "context_modifiers": [r"\bml\b", r"\bunidades\b", r"\bkit\b", r"\bpack\b"],
        "exclude": [],
    },
    "informatica": {
        "strong_keywords": [
            r"\bnotebook(s)?\b",
            r"\blaptop(s)?\b",
            r"\bmacbook\b",
            r"\bpc\s+gamer\b",
            r"\bplaca\s+de\s+v[ií]deo\b",
            r"\brtx\b",
            r"\brx\b",
        ],
        "ambiguous_brands": [r"\bdell\b", r"\blenovo\b", r"\bacer\b", r"\bavell\b", r"\basus\b"],
        "context_modifiers": [r"\bram\b", r"\bgb\b", r"\btb\b", r"\bintel\b", r"\bryzen\b"],
        "exclude": [r"\bcabo\b", r"\badaptador\b"],
    },
    "casa": {
        "strong_keywords": [
            r"\bair\s?fryer\b",
            r"\bmicro-ondas\b",
            r"\bgeladeira\b",
            r"\bliquidificador\b",
            r"\baspirador\b",
        ],
        "ambiguous_brands": [r"\bmondial\b", r"\belectrolux\b", r"\bphilco\b", r"\boster\b"],
        "context_modifiers": [r"\blitros\b", r"\bw\b", r"\bwatts\b", r"\bvolts\b", r"\b110v\b", r"\b220v\b"],
        "exclude": [r"\bpe[çc]a\b", r"\bconserto\b"],
    },
    "moda": {
        "strong_keywords": [r"\bcamiseta(s)?\b", r"\bmeia(s)?\b", r"\bcueca(s)?\b", r"\bt[eê]nis\b", r"\bmochila\b"],
        "ambiguous_brands": [r"\bnike\b", r"\badidas\b", r"\bpuma\b", r"\bhering\b", r"\blupo\b"],
        "context_modifiers": [r"\bkit\b", r"\bpack\b", r"\balgod[aã]o\b", r"\btamanho\b"],
        "exclude": [],
    },
    "games": {
        "strong_keywords": [
            r"\bps5\b",
            r"\bplaystation\b",
            r"\bxbox\b",
            r"\bnintendo\b",
            r"\bswitch\b",
            r"\bdualshock\b",
            r"\bdualsense\b",
        ],
        "ambiguous_brands": [r"\bsony\b", r"\bmicrosoft\b", r"\basus\b"],
        "context_modifiers": [r"\bgamer\b", r"\bconsole\b", r"\bjoystick\b", r"\bcontrole\b"],
        "exclude": [r"\bcapa\b", r"\bcase\b", r"\badesivo\b"],
    },
    "esportes": {
        "strong_keywords": [r"\btenis\b", r"\bfootball\b", r"\bsoccer\b", r"\bBasketball\b", r"\bbaseball\b"],
        "ambiguous_brands": [
            r"\bnike\b",
            r"\badidas\b",
            r"\bpuma\b",
            r"\bunder armour\b",
            r"\basics\b",
            r"\bmizuno\b",
            r"\bpenalty\b",
        ],
        "context_modifiers": [r"\bkit\b", r"\bpack\b", r"\btamanho\b"],
        "exclude": [],
    },
}

OFFER_PATTERNS: dict[str, list[re.Pattern]] = {
    "price": [
        re.compile(p, re.IGNORECASE)
        for p in [
            r"r\$\s*[\d\.]+",
            r"por\s+apenas\s+r\$",
            r"de\s+r\$[\d\.,]+\s+por\s+r\$",
            r"(preço|valor|custa|custando|saindo|sai)\s+(a\s+)?r\$",
            r"parcel(a|ado|amento)\s+em\s+\d+x",
            r"\d+x\s+(sem\s+juros|s\.j\.)",
            r"\b\d{3,5}\b",
            r"\b\d{3,5}\s*reais\b",
            r"\bfa[cç]o\s+r\$?\s*\d+",
        ]
    ],
    "discount": [
        re.compile(p, re.IGNORECASE)
        for p in [
            r"\d+%\s*off",
            r"cupom",
            r"desconto",
            r"promo[çc][ãa]o",
            r"oferta",
            r"queima",
            r"liquida",
            r"menor\s+pre[çc]o",
            r"baixou",
        ]
    ],
    "link": [
        re.compile(p, re.IGNORECASE)
        for p in [
            r"https?://",
            r"amzn\.to",
            r"magalu\.at",
            r"mercadolivre\.com",
            r"shopee\.com",
            r"t\.me/",
        ]
    ],
}

# ===========================================================================
# 3. HELPERS E FUNÇÕES UTILITÁRIAS
# ===========================================================================


def _remove_accents(text: str) -> str:
    return unicodedata.normalize("NFKD", text).encode("ASCII", "ignore").decode("utf-8")


def _is_spam_name(title: str) -> bool:
    if " " in title.strip():
        return False
    clean = re.sub(r"[^a-zA-Z]", "", title)
    if not clean:
        return False
    if len(clean) < 4:
        return True
    t = clean.lower()
    vowels = sum(1 for c in t if c in "aeiou")
    ratio = vowels / len(t)
    if ratio < 0.30:
        return True
    if re.search(r"(.{2,4})\1", t):
        return True
    if re.search(r"[^aeiou]{4,}", t):
        return True
    if len(t) >= 7 and ratio < 0.45 and re.search(r"[^aeiou]{3,}", t):
        return True
    return False


def group_passes_quality_filter(title: str) -> bool:
    for pattern in GROUP_QUALITY_BLOCKLIST:
        if pattern.search(title):
            return False
    if _is_spam_name(title):
        return False
    return True


def _validate_category(text: str, category: str) -> bool:
    rules = CATEGORY_RULES.get(category)
    if not rules:
        return False
    t_clean = _remove_accents(text.lower())
    for exc in rules.get("exclude", []):
        if re.search(exc, t_clean):
            return False
    for kw in rules.get("strong_keywords", []):
        if re.search(kw, t_clean):
            return True
    for b in rules.get("ambiguous_brands", []):
        if re.search(b, t_clean):
            for mod in rules.get("context_modifiers", []):
                if re.search(mod, t_clean):
                    return True
    return False


def _offer_score(text: str) -> tuple[int, list[str]]:
    score = 0
    matched_categories = []
    t_clean = _remove_accents(text.lower())
    for cat in CATEGORY_RULES.keys():
        if _validate_category(text, cat):
            score += 2
            matched_categories.append(cat)
    for p_list in OFFER_PATTERNS.values():
        for p in p_list:
            if p.search(t_clean):
                score += 1
                break
    return score, matched_categories


def _extract_price(text: str) -> float | None:
    prices = []
    matches = re.findall(r"r\$\s*([\d\.]+,\d{2}|[\d\.,]+)", text, re.IGNORECASE)
    for m in matches:
        try:
            if "," in m and "." in m:
                clean = m.replace(".", "").replace(",", ".")
            elif "," in m:
                clean = m.replace(",", ".")
            else:
                if "." in m and len(m.split(".")[-1]) == 3:
                    clean = m.replace(".", "")
                else:
                    clean = m
            prices.append(float(clean))
        except ValueError:
            continue
    if not prices:
        matches = re.findall(r"\b(\d{1,3}(?:\.\d{3})*(?:,\d{2})?)\b", text)
        for m in matches:
            try:
                prices.append(float(m.replace(".", "").replace(",", ".")))
            except ValueError:
                continue
    return min(prices) if prices else None


def _extract_payment_condition(text: str) -> str:
    match = re.search(r"\b (pix| no pix|  a vista |em\s*\d+x\s*sem juros)\b", text, re.IGNORECASE)
    return match.group(1).strip() if match else ""


def _clean_product_name(text: str) -> str:
    text = re.sub(r"[^\w\s,.-]", "", text).strip()
    triggers = [
        r"NGM MERECE COMER MARMITA FRIA",
        r"VOCE NAO CANSA DE TREINAR FOFO",
        r"MEU NUTRI DISSE PRA EU ADICIONAR MAIS FRUTAS",
        r"CERVEJA DE QUEM TRABALHA NO SABADO",
        r"PERFEITA PRA VC ENCHER DE AGUA E OVO",
        r"JA TOMOU SUA CREATINA HUJE",
        r"CHEGA DE PANELA NA GELADEIRA",
        r"SO JARDINEIRO GOSTA DE MATO ALTO",
        r"QUAL SUA DESCULPA PRA FICAR SEM CUECA",
        r"PROIBIDO ESQUENTAR PAO NO MICROONDAS",
        r"PRA ENCHER DE GORO",
        r"PRO DIA A DIA ESSE E ABSURDO",
        r"QUERIA COMPRAR ESSE MAS JA TA RESERVADO",
        r"MULHERES CHEIROSAS USAM ESSE",
        r"JA PODE PARAR DE SENTAR NO CHAO",
        r"CAPAZ DA TUA COLUNA TE ABRACAR",
        r"AMAZON SOLTOU CUPOM",
        r"PRA VC NAO VIRAR UM NAPOLITANO NO SOL",
        r"PODE APOSENTAR SUAS MEIAS FURADAS",
        r"NA FARMACIA ISSO CUSTA UM RIM",
        r"SEU NOVO UNIFORME PRA TREINAR",
        r"AGORA SO FALTA A PASSAGEM",
        r"GARANTO QUE UM DESSE E MUITO UTIL NA COZINHA",
        r"QUEM GOSTA DE FIO E ELETRICISTA",
        r"TA NA HORA DE TIRAR O MONITOR DO CHAO",
        r"ISSO AQUI E UMA MAO NA RODA",
    ]
    text_no_accents = _remove_accents(text)
    for trigger in triggers:
        if trigger in text_no_accents.upper():
            text = re.sub(re.escape(trigger), "", text_no_accents, flags=re.IGNORECASE).strip()
            break
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    return lines[0] if lines else "Produto não identificado"


def _matches_specific_model(text: str, model_name: str) -> bool:
    t_clean = _remove_accents(text.lower())
    model_clean = _remove_accents(model_name.lower())
    words = model_clean.split()
    if not words:
        return False
    return all(w in t_clean for w in words)


def _matches_level_broad(text: str) -> bool:
    active_cats = WATCH_CONFIG.get("broad_categories", [])
    if not active_cats:
        return False
    for cat in active_cats:
        if _validate_category(text, cat):
            return True
    extra_kws = WATCH_CONFIG.get("broad_keywords", [])
    for kw in extra_kws:
        kw_clean = _remove_accents(kw.lower())
        t_clean = _remove_accents(text.lower())
        if re.search(rf"\b{re.escape(kw_clean)}\b", t_clean):
            return True
    return False


def _matches_level_mid(text: str) -> bool:
    active_cats = WATCH_CONFIG.get("mid_categories", [])
    active_brands = WATCH_CONFIG.get("mid_brands", [])
    if not active_cats or not active_brands:
        return False

    cat_matched = any(_validate_category(text, cat) for cat in active_cats)
    if not cat_matched:
        return False

    t_clean = _remove_accents(text.lower())
    brand_matched = any(_remove_accents(b.lower()) in t_clean for b in active_brands)
    return brand_matched


def _matches_level(text: str, level: str) -> bool:
    if level == "broad":
        return _matches_level_broad(text)
    elif level == "mid":
        return _matches_level_mid(text)
    elif level == "specific":
        for entry in WATCH_CONFIG.get("specific_models", []):
            if ":" in entry:
                model_name = entry.split(":", 1)[0].strip()
            else:
                model_name = entry.strip()
            if model_name and _matches_specific_model(text, model_name):
                return True
        return False
    return False


def should_alert(text: str) -> tuple[bool, dict]:
    price_max = WATCH_CONFIG.get("price_max")
    active_levels = WATCH_CONFIG.get("active_levels", ["broad"])

    level_match = False
    matched_specific_limit = None

    for lvl in active_levels:
        if lvl == "broad" and _matches_level_broad(text):
            level_match = True
        elif lvl == "mid" and _matches_level_mid(text):
            level_match = True
        elif lvl == "specific":
            for entry in WATCH_CONFIG.get("specific_models", []):
                if ":" in entry:
                    parts = entry.split(":", 1)
                    model_name = parts[0].strip()
                    try:
                        limit = float(parts[1].strip())
                    except ValueError:
                        limit = None
                else:
                    model_name = entry.strip()
                    limit = None

                if model_name and _matches_specific_model(text, model_name):
                    level_match = True
                    matched_specific_limit = limit
                    if limit is not None:
                        break

    if not level_match:
        return False, {}

    score, categories = _offer_score(text)
    min_score = WATCH_CONFIG.get("min_score", 2)
    relaxed = WATCH_CONFIG.get("relaxed_mode", False)
    require_offer_match = WATCH_CONFIG.get("require_offer_match", True)
    if require_offer_match:
        if relaxed:
            if score < 1:
                return False, {}
        else:
            if score < min_score:
                return False, {}

    extracted_price = _extract_price(text)

    effective_limit = price_max
    if matched_specific_limit is not None:
        effective_limit = matched_specific_limit

    if effective_limit and extracted_price and extracted_price > effective_limit:
        return False, {}

    return True, {
        "offer_score": score,
        "offer_categories": categories,
        "extracted_price": extracted_price,
        "payment_condition": _extract_payment_condition(text),
    }


# ===========================================================================
# 4. LÓGICA DO TELEGRAM (CLIENTE E MONITORAMENTO)
# ===========================================================================

SESSIONS_DIR = BASE_DIR / "sessions"
SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
SESSION_PATH = SESSIONS_DIR / "users"


def create_client() -> TelegramClient:
    return TelegramClient(
        str(SESSION_PATH),
        api_id,
        api_hash,
        connection_retries=None,
        auto_reconnect=True,
    )


client = create_client()
client_lock = asyncio.Lock()


async def enrich_alert_in_background(alert_id: int, original_url: str):
    lower_url = original_url.lower()
    # Filtra apenas links de e-commerce conhecidos
    is_ecommerce = any(
        domain in lower_url
        for domain in [
            "amazon.",
            "amzn.to",
            "magazineluiza.",
            "magalu.at",
            "mgl.li",
            "mercadolivre.",
            "mlb.link",
            "shopee.",
            "shope.ee",
        ]
    )
    if not is_ecommerce:
        return

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    try:
        async with httpx.AsyncClient(follow_redirects=True, headers=headers, timeout=15.0) as client:
            res = await client.get(original_url)
            if res.status_code != 200:
                return

            final_url = str(res.url)
            soup = BeautifulSoup(res.text, "html.parser")

            # 1. Extração do título real do produto
            title = None
            og_title = soup.find("meta", property="og:title") or soup.find("meta", name="twitter:title")
            if og_title:
                title = og_title.get("content")
            if not title:
                title_tag = soup.find("title")
                if title_tag:
                    title = title_tag.text.strip()

            # Limpa marcas extras comuns do título
            if title:
                title = title.split(" | ")[0].split(" - ")[0].strip()

            # 2. Extração do preço
            price = None
            og_price = (
                soup.find("meta", property="product:price:amount")
                or soup.find("meta", property="product:sale_price:amount")
                or soup.find("meta", itemprop="price")
            )
            if og_price:
                try:
                    price = float(og_price.get("content").replace(",", "."))
                except ValueError:
                    pass

            if not price:
                import json

                for script in soup.find_all("script", type="application/ld+json"):
                    try:
                        ld = json.loads(script.string)
                        if isinstance(ld, list):
                            ld = ld[0]
                        offers = ld.get("offers")
                        if offers:
                            if isinstance(offers, list):
                                offers = offers[0]
                            p = offers.get("price") or offers.get("lowPrice")
                            if p:
                                price = float(str(p).replace(",", "."))
                                break
                    except Exception:
                        continue

            # Fallback para Amazon
            if "amazon.com" in final_url.lower() and not price:
                price_whole = soup.find("span", class_="a-price-whole")
                price_fraction = soup.find("span", class_="a-price-fraction")
                if price_whole:
                    try:
                        p_str = price_whole.text.strip().replace(".", "").replace(",", "")
                        if price_fraction:
                            p_str += "." + price_fraction.text.strip()
                        price = float(p_str)
                    except ValueError:
                        pass

            # 3. Extração e download da imagem real do produto
            image_url = None
            og_image = soup.find("meta", property="og:image") or soup.find("meta", name="twitter:image")
            if og_image:
                img_src = og_image.get("content")
                if img_src:
                    media_dir = SESSIONS_DIR / "media"
                    media_dir.mkdir(parents=True, exist_ok=True)
                    try:
                        img_res = await client.get(img_src, timeout=10.0)
                        if img_res.status_code == 200:
                            img_name = f"{alert_id}_scraped.jpg"
                            (media_dir / img_name).write_bytes(img_res.content)
                            image_url = img_name
                    except Exception as e:
                        print(f"Erro ao baixar imagem de {img_src}: {e}")

            # Atualiza os detalhes no banco de dados SQLite
            clean_title = _clean_product_name(title) if title else None
            db.update_alert_details(
                alert_id=alert_id, clean_title=clean_title, extracted_price=price, image_url=image_url
            )
            print(
                f"Alerta {alert_id} enriquecido com sucesso do link: {final_url} (Preço: {price}, Título: {clean_title})"
            )

    except Exception as e:
        print(f"Erro ao enriquecer alerta {alert_id} a partir do link: {e}")


# QA: HANDLER ÚNICO E GLOBAL - Registrado uma única vez no startup
@client.on(events.NewMessage())
async def global_message_handler(event):
    global processed_msg_ids
    if not monitoring_active:
        return
    chat_id = event.chat_id
    msg_id = event.message.id
    if msg_id in processed_msg_ids:
        return
    self_monitor = WATCH_CONFIG.get("self_monitor", False)
    is_self = event.is_private and event.sender_id == (await client.get_me()).id
    if not (chat_id in active_group_ids or (self_monitor and is_self)):
        return
    text = event.message.message or ""
    ok, meta = should_alert(text)
    if ok:
        processed_msg_ids.add(msg_id)
        if len(processed_msg_ids) > 1000:
            processed_msg_ids.remove(next(iter(processed_msg_ids)))
        chat = await event.get_chat()
        username = getattr(chat, "username", None)
        if username:
            msg_link = f"https://t.me/{username}/{msg_id}"
        elif str(chat_id).startswith("-100"):
            msg_link = f"https://t.me/c/{str(chat_id)[4:]}/{msg_id}"
        else:
            msg_link = None

        # Tenta baixar a foto do produto/mensagem ou da visualização da web (se disponível)
        image_url = None
        media_dir = SESSIONS_DIR / "media"
        media_dir.mkdir(parents=True, exist_ok=True)
        try:
            download_path = None
            if event.message.photo:
                download_path = await event.message.download_media(file=media_dir / f"{msg_id}.jpg")
            elif hasattr(event.message, "media") and event.message.media:
                from telethon.tl.types import MessageMediaWebPage, WebPage

                if isinstance(event.message.media, MessageMediaWebPage) and isinstance(
                    event.message.media.webpage, WebPage
                ):
                    wp = event.message.media.webpage
                    if wp.photo:
                        download_path = await client.download_media(wp.photo, file=media_dir / f"{msg_id}.jpg")
            if download_path:
                image_url = f"{msg_id}.jpg"
        except Exception as media_err:
            print(f"Erro ao salvar mídia do alerta: {media_err}")

        alert_item = {
            "group_id": chat_id,
            "group_title": getattr(chat, "title", "Saved Messages"),
            "username": username if not is_self else None,
            "message": text[:500],
            "message_id": msg_id,
            "offer_score": meta.get("offer_score"),
            "offer_categories": meta.get("offer_categories"),
            "extracted_price": meta.get("extracted_price"),
            "link": msg_link,
            "clean_title": _clean_product_name(text),
            "image_url": image_url,
        }
        alert_id = db.save_alert(alert_item)
        print(f"ALERTA: {chat_id} - {getattr(chat, 'title', 'Saved Messages')} - {text[:100]}...")

        # Encontra links para enriquecimento do alerta em background
        urls = re.findall(r"(https?://\S+)", text)
        if urls:
            asyncio.create_task(enrich_alert_in_background(alert_id, urls[0]))


async def ensure_client_connected() -> None:
    global client
    async with client_lock:
        if client.is_connected():
            return
        try:
            await client.connect()
        except ValueError as error:
            if "cannot be reused after logging out" not in str(error):
                raise
            client = create_client()
            client.add_event_handler(global_message_handler, events.NewMessage())
            await client.connect()
        if not client.is_connected():
            raise HTTPException(status_code=503, detail="Nao conectado ao Telegram.")


async def _run_monitoring(group_ids: list[int]) -> None:
    global active_group_ids, monitoring_active
    active_group_ids = set(group_ids)
    print(f"Telethon: Iniciando monitoramento para {len(group_ids)} grupos...")
    while monitoring_active:
        try:
            await ensure_client_connected()
            await client.run_until_disconnected()
        except asyncio.CancelledError:
            print("Telethon: Monitoramento cancelado pelo usuario.")
            break
        except Exception as error:
            print(f"Telethon: Desconexao ou erro no loop de escuta: {error}. Reconectando em 5 segundos...")
            await asyncio.sleep(5)


# ===========================================================================
# 5. ROTAS DA API (FASTAPI)
# ===========================================================================


@asynccontextmanager
async def lifespan(app: FastAPI):
    global WATCH_CONFIG, monitoring_active, active_group_ids, monitoring_task
    # Inicializa banco de dados e carrega configuracoes
    db.init_db()
    WATCH_CONFIG = db.load_config(WATCH_CONFIG)

    # Conecta o cliente do Telegram se possivel
    try:
        await ensure_client_connected()
    except Exception as e:
        print(f"Erro ao conectar cliente Telegram no startup: {e}")

    # Restaura o estado anterior do monitoramento se estava ativo e logado
    is_active, saved_groups = db.load_monitoring_state()
    if is_active and await client.is_user_authorized():
        print(f"Telethon: Restaurando monitoramento automatico para os grupos: {saved_groups}")
        monitoring_active = True
        monitoring_task = asyncio.create_task(_run_monitoring(saved_groups))

    yield


tags_metadata = [
    {
        "name": "Autenticação",
        "description": "Endpoints para login e gerenciamento de sessão com a API do Telegram.",
    },
    {
        "name": "Grupos",
        "description": "Gerenciamento e listagem de grupos/canais disponíveis para monitoramento.",
    },
    {
        "name": "Monitoramento (Radar)",
        "description": "Controle do scanner em tempo real e parametrização dos filtros de ofertas.",
    },
    {
        "name": "Alertas",
        "description": "Histórico de ofertas capturadas e filtros de consulta.",
    },
    {
        "name": "Utilitários e Testes",
        "description": "Verificação de integridade da API e testes rápidos do motor de regras.",
    },
]

from fastapi.staticfiles import StaticFiles

app = FastAPI(
    title="PromoPulse API",
    description="API de monitoramento em tempo real de ofertas do Telegram com filtros inteligentes.",
    version="1.4.0",
    openapi_tags=tags_metadata,
    lifespan=lifespan,
    root_path="/apis/promopulse",
)

# Garantir que a pasta de mídias de alertas exista e montá-la na API
(SESSIONS_DIR / "media").mkdir(parents=True, exist_ok=True)
app.mount("/media", StaticFiles(directory=str(SESSIONS_DIR / "media")), name="media")


@app.get("/", tags=["Utilitários e Testes"], summary="Verificação rápida da API")
async def root():
    return {"status": "ok"}


@app.post("/send.code", tags=["Autenticação"], summary="Solicitar código de verificação")
async def send_code(data: PhoneRequest):
    global phone_number, phone_code_hash
    phone = (data.phone_number or "").strip()
    if not phone:
        raise HTTPException(status_code=400, detail="Telefone obrigatorio.")
    phone_number = phone
    await ensure_client_connected()
    try:
        result = await client.send_code_request(phone_number)
        phone_code_hash = result.phone_code_hash
        return {"status": "code sent"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/login", tags=["Autenticação"], summary="Realizar login com código")
async def login(data: LoginRequest):
    global phone_code_hash
    if not data.code:
        raise HTTPException(status_code=400, detail="Codigo obrigatorio.")
    await ensure_client_connected()
    try:
        await client.sign_in(phone=phone_number, code=data.code, phone_code_hash=phone_code_hash)
        phone_code_hash = None
        return {"status": "logged"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/logout", tags=["Autenticação"], summary="Terminar a sessão ativa")
async def logout():
    await ensure_client_connected()
    await client.log_out()
    return {"status": "logged out"}


@app.get("/me", tags=["Autenticação"], summary="Obter status da sessão atual")
async def get_me():
    await ensure_client_connected()
    if not await client.is_user_authorized():
        return {"logged": False}
    me = await client.get_me()
    return {"logged": True, "first_name": me.first_name, "username": me.username}


@app.get("/groups", response_model=GroupsResponse, tags=["Grupos"], summary="Listar grupos e canais do Telegram")
async def get_groups():
    await ensure_client_connected()
    if not await client.is_user_authorized():
        return {"groups": []}
    dialogs = await client.get_dialogs()
    groups = []
    for d in dialogs:
        if not (d.is_group or d.is_channel):
            continue
        passed = group_passes_quality_filter(d.title or "")
        groups.append(
            {
                "id": d.id,
                "title": d.title,
                "username": getattr(d.entity, "username", None),
                "link": f"https://t.me/{d.entity.username}" if getattr(d.entity, "username", None) else None,
                "auto_filtered": not passed,
            }
        )
    return {"groups": groups}


@app.post(
    "/watch/config",
    response_model=WatchConfigResponse,
    tags=["Monitoramento (Radar)"],
    summary="Configurar filtros do Radar",
)
async def set_watch_config(data: WatchConfigRequest):
    for k, v in data.dict().items():
        WATCH_CONFIG[k] = v
    db.save_config(WATCH_CONFIG)
    return {"status": "ok", "config": WATCH_CONFIG}


@app.get(
    "/watch/status", response_model=WatchStatusResponse, tags=["Monitoramento (Radar)"], summary="Obter status do Radar"
)
async def watch_status():
    return {"active": monitoring_active, "config": WATCH_CONFIG, "alerts_count": db.get_alerts_count()}


@app.post(
    "/watch/start",
    response_model=StartWatchResponse,
    tags=["Monitoramento (Radar)"],
    summary="Iniciar monitoramento em tempo real",
)
async def start_watch(data: StartWatchRequest):
    global monitoring_active, monitoring_task
    await ensure_client_connected()
    if monitoring_active:
        return {"status": "already running", "groups": 0, "config": WATCH_CONFIG}
    monitoring_active = True
    db.save_monitoring_state(True, data.group_ids)
    monitoring_task = asyncio.create_task(_run_monitoring(data.group_ids))
    return {"status": "monitoring started", "groups": len(data.group_ids), "config": WATCH_CONFIG}


@app.post(
    "/watch/stop",
    response_model=StopWatchResponse,
    tags=["Monitoramento (Radar)"],
    summary="Parar monitoramento em tempo real",
)
async def stop_watch():
    global monitoring_active, monitoring_task
    monitoring_active = False
    db.save_monitoring_state(False, list(active_group_ids))
    if monitoring_task:
        monitoring_task.cancel()
    return {"status": "monitoring stopped"}


@app.get("/alerts", response_model=AlertsResponse, tags=["Alertas"], summary="Obter alertas filtrados")
async def get_alerts(
    limit: int = Query(50, description="Número máximo de alertas a retornar"),
    min_price: float | None = Query(None, description="Preço mínimo para filtro"),
    max_price: float | None = Query(None, description="Preço máximo para filtro"),
    category: str | None = Query(None, description="Categoria específica para filtro"),
    q: str | None = Query(None, description="Termo de pesquisa para busca textual no título ou mensagem"),
):
    alerts = db.get_alerts(limit=limit, min_price=min_price, max_price=max_price, category=category, q=q)
    return {"alerts": alerts}


@app.delete("/alerts", tags=["Alertas"], summary="Limpar histórico de alertas")
async def clear_alerts():
    db.clear_alerts()

    return {"status": "cleared"}


@app.get(
    "/alerts/{message_id}/price-history",
    response_model=PriceHistoryResponse,
    tags=["Alertas"],
    summary="Obter histórico de preços de um alerta por message_id",
)
async def get_price_history(message_id: int):
    history = db.get_price_history_by_msg_id(message_id)
    return {"history": history}


@app.post(
    "/offers/test",
    response_model=OfferTestResponse,
    tags=["Utilitários e Testes"],
    summary="Testar regras em uma mensagem",
)
async def test_offer(data: OfferRequest):
    ok, meta = should_alert(data.text)
    score, categories = _offer_score(data.text)
    return {
        "would_alert": ok,
        "offer_score": score,
        "offer_categories": categories,
        "extracted_price": _extract_price(data.text),
        "level_match": any(_matches_level(data.text, lvl) for lvl in WATCH_CONFIG.get("active_levels", ["broad"])),
        "current_level": ", ".join(WATCH_CONFIG.get("active_levels", ["broad"])),
    }


@app.head("/health", tags=["Utilitários e Testes"], summary="Checagem de integridade")
async def health_check():
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
