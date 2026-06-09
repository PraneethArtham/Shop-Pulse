"""
backend/services/nlp_search.py  — v3  (ML-driven, not dict-driven)

Architecture: 3-layer ML pipeline
  Layer 1: sklearn TF-IDF + cosine similarity for entity extraction
            (brand/category matching against reference corpus)
  Layer 2: sklearn LinearSVC for intent classification
            (trained on synthetic examples in-process, no download)
  Layer 3: Regex for structured extraction (price, model numbers)
           + TF-IDF re-ranker on results

This replaces pure dictionary lookups with actual ML models that:
  - Handle spelling variants automatically ("smsung" → Samsung)
  - Generalise to unseen brands/products via character n-grams
  - Classify intent from semantic patterns, not keyword lists
  - Re-rank results using cosine similarity to the query
"""

import re
import logging
import threading
import math
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.svm import LinearSVC
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import LabelEncoder

logger = logging.getLogger("shoppulse.nlp")


# ──────────────────────────────────────────────────────────────────────────────
# REFERENCE CORPORA  (training data for the ML models)
# ──────────────────────────────────────────────────────────────────────────────

# Brand corpus: (canonical_name, aliases...)
BRAND_CORPUS = [
    ("boAt",       "boat bo@t boat earphones boat airdopes boat rockerz"),
    ("Samsung",    "samsung samung samsun galaxy samsung mobile"),
    ("Apple",      "apple iphone macbook ipad airpods apple watch"),
    ("OnePlus",    "oneplus one plus oneplus nord"),
    ("Realme",     "realme real me realme narzo"),
    ("Xiaomi",     "xiaomi mi redmi poco xiaomi phone"),
    ("Redmi",      "redmi redmi note"),
    ("Oppo",       "oppo oppo reno"),
    ("Vivo",       "vivo vivo phone"),
    ("Motorola",   "motorola moto moto g"),
    ("Nokia",      "nokia nokia phone"),
    ("Sony",       "sony sony headphone sony bravia"),
    ("LG",         "lg lg tv lg ac"),
    ("Philips",    "philips philips trimmer"),
    ("Panasonic",  "panasonic panasonic tv"),
    ("JBL",        "jbl jbl speaker jbl earphone"),
    ("Bose",       "bose bose headphone bose speaker"),
    ("Sennheiser", "sennheiser sennheiser headphone"),
    ("Dell",       "dell dell laptop dell xps"),
    ("HP",         "hp hp laptop hp pavilion hewlett packard"),
    ("Lenovo",     "lenovo lenovo laptop lenovo thinkpad"),
    ("Asus",       "asus asus laptop asus rog asus zenbook"),
    ("Acer",       "acer acer laptop acer aspire"),
    ("MSI",        "msi msi gaming"),
    ("Microsoft",  "microsoft surface microsoft laptop"),
    ("Noise",      "noise noise smartwatch noise colorfit"),
    ("Voltas",     "voltas voltas ac voltas air conditioner"),
    ("Daikin",     "daikin daikin ac daikin split ac"),
    ("Hitachi",    "hitachi hitachi ac"),
    ("Carrier",    "carrier carrier ac"),
    ("Lloyd",      "lloyd lloyd ac lloyd split"),
    ("Haier",      "haier haier ac haier fridge"),
    ("Blue Star",  "blue star bluestar blue star ac"),
    ("Whirlpool",  "whirlpool whirlpool fridge whirlpool washing machine"),
    ("Godrej",     "godrej godrej fridge godrej ac"),
    ("Havells",    "havells havells fan havells geyser"),
    ("Bajaj",      "bajaj bajaj fan bajaj mixer"),
    ("Prestige",   "prestige prestige cooker prestige mixer"),
    ("Butterfly",  "butterfly butterfly mixer"),
    ("Bosch",      "bosch bosch washing machine bosch mixer"),
    ("Cadbury",    "cadbury cadburys dairy milk cadbury chocolate cadbury 5star"),
    ("Nestle",     "nestle nestlé kitkat munch milkybar"),
    ("Amul",       "amul amul butter amul milk amul cheese amul ghee"),
    ("Britannia",  "britannia good day marie gold britannia bread britannia cake"),
    ("Parle",      "parle parle g monaco parle biscuit"),
    ("Maggi",      "maggi maggi noodles 2 minute noodles"),
    ("Haldiram's", "haldirams haldiram bhujia namkeen"),
    ("Patanjali",  "patanjali patanjali atta patanjali ghee"),
    ("MTR",        "mtr mtr foods mtr masala"),
    ("Tata",       "tata tata salt tata tea tata sampann"),
    ("Dove",       "dove dove shampoo dove soap dove body wash"),
    ("Nivea",      "nivea nivea cream nivea moisturizer"),
    ("Himalaya",   "himalaya himalaya face wash himalaya shampoo"),
    ("Mamaearth",  "mamaearth mama earth mamaearth face wash"),
    ("Lakmé",      "lakme lakme lipstick lakme foundation"),
    ("L'Oréal",    "loreal l'oreal loreal shampoo"),
    ("Dettol",     "dettol dettol soap dettol handwash"),
    ("Puma",       "puma puma shoes puma sneaker"),
    ("Nike",       "nike nike shoes air max air force"),
    ("Adidas",     "adidas adidas shoes ultraboost"),
]

# Category corpus: (category_name, representative_terms)
CATEGORY_CORPUS = [
    ("Mobiles",      "phone mobile smartphone iphone android samsung galaxy oneplus realme 5g 4g sim call s24 s23 note iphone15 pro max ultra 5g mobile phone near me availability"),
    ("Laptops",      "laptop notebook computer ultrabook chromebook macbook thinkpad vivobook gaming laptop"),
    ("Electronics",  "headphone earphone earbuds tws neckband bluetooth speaker trimmer shaver smartwatch wearable tablet camera keyboard mouse charger powerbank router projector soundbar airdopes"),
    ("Appliances",   "air conditioner ac split ac window ac inverter ac refrigerator fridge washing machine washer water purifier purifier geyser water heater ceiling fan air purifier dishwasher air conditioning cooling room cooling ton tonnage 1.5 ton 2 ton split unit"),
    ("Grocery",      "rice dal atta flour oil ghee sugar salt masala spice tea coffee biscuit chocolate snack noodles pasta bread milk butter cheese curd yogurt chips juice drink protein dairy milk 5 star cadbury kitkat maggi cereal breakfast packaged food candy sweet"),
    ("PersonalCare", "shampoo conditioner face wash facewash moisturiser moisturizer sunscreen serum toner lipstick foundation perfume deodorant deo soap body wash toothpaste toothbrush hair oil lotion cleanser"),
    ("Kitchen",      "mixer grinder blender pressure cooker cooker oven microwave toaster kettle juicer induction"),
    ("Footwear",     "shoe sneaker boot sandal slipper chappal running shoe sports shoe"),
    ("Clothing",     "shirt tshirt t-shirt jeans kurta saree jacket hoodie trouser dress legging ethnic wear"),
    ("Sports",       "cricket football yoga gym fitness dumbbell treadmill cycle bicycle"),
]

# Intent training data: (text, intent_label)
INTENT_TRAINING = [
    # find_cheapest
    ("cheapest headphone", "find_cheapest"),
    ("lowest price ac", "find_cheapest"),
    ("best price samsung", "find_cheapest"),
    ("most affordable laptop", "find_cheapest"),
    ("budget earphone", "find_cheapest"),
    ("cheap mobile under 10000", "find_cheapest"),
    ("where to buy cheapest iphone", "find_cheapest"),
    ("lowest cost refrigerator", "find_cheapest"),
    # compare
    ("compare samsung vs oneplus", "compare"),
    ("samsung s24 versus iphone 15", "compare"),
    ("which is better jbl or sony", "compare"),
    ("difference between voltas and daikin ac", "compare"),
    ("boat vs jbl earphones", "compare"),
    ("iphone 15 vs samsung s24 comparison", "compare"),
    # check_availability
    ("is iphone available near me", "check_availability"),
    ("samsung in stock", "check_availability"),
    ("local store for ac", "check_availability"),
    ("where to buy nearby", "check_availability"),
    ("ac available in hyderabad", "check_availability"),
    # review_check
    ("is sony headphone worth buying", "review_check"),
    ("boat airdopes review", "review_check"),
    ("is samsung galaxy good", "review_check"),
    ("rating of oneplus 12", "review_check"),
    ("feedback on voltas ac", "review_check"),
    # compare — add more Samsung/OnePlus patterns
    ("samsung vs oneplus which better", "compare"),
    ("iphone vs samsung which to buy", "compare"),
    # check_availability — mobile
    ("samsung available hyderabad", "check_availability"),
    ("oneplus 12 in stock near me", "check_availability"),
    # search — add more product patterns
    ("voltas split ac 1.5 ton", "search"),
    ("5 star chocolate cadbury", "search"),
    ("air conditioner 1.5 ton inverter", "search"),
    ("s24 samsung mobile", "search"),
    # search (default)
    ("boat airdopes 141", "search"),
    ("samsung galaxy s24", "search"),
    ("trimmer under 500", "search"),
    ("air conditioner 1.5 ton", "search"),
    ("amul butter", "search"),
    ("face wash for oily skin", "search"),
    ("sony wh 1000xm5", "search"),
    ("macbook air m2", "search"),
    ("dairy milk chocolate", "search"),
    ("voltas 1.5 ton inverter ac", "search"),
]


# ──────────────────────────────────────────────────────────────────────────────
# ML MODEL TRAINING  (runs once at import time, < 100ms)
# ──────────────────────────────────────────────────────────────────────────────

class _IntentClassifier:
    """
    LinearSVC trained on synthetic examples to classify search intent.
    Character n-grams make it robust to spelling variants.
    Training is fully in-process — no files, no downloads.
    """
    def __init__(self):
        self._pipe   = Pipeline([
            ("tfidf", TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 4), sublinear_tf=True)),
            ("clf",   LinearSVC(max_iter=2000, C=1.0)),
        ])
        self._ready = False
        self._train()

    def _train(self):
        texts  = [t for t, _ in INTENT_TRAINING]
        labels = [l for _, l in INTENT_TRAINING]
        self._pipe.fit(texts, labels)
        self._ready = True
        logger.info(f"IntentClassifier trained on {len(texts)} examples, "
                    f"classes={self._pipe.classes_.tolist()}")

    def predict(self, text: str) -> str:
        if not self._ready:
            return "search"
        try:
            return self._pipe.predict([text.lower()])[0]
        except Exception:
            return "search"

    def predict_proba(self, text: str) -> dict:
        """Return probability-like decision scores for each class."""
        if not self._ready:
            return {"search": 1.0}
        try:
            scores = self._pipe.decision_function([text.lower()])[0]
            classes = self._pipe.classes_
            # Softmax for interpretable scores
            exp_s = np.exp(scores - scores.max())
            probs = exp_s / exp_s.sum()
            return {c: round(float(p), 3) for c, p in zip(classes, probs)}
        except Exception:
            return {"search": 1.0}


class _EntityExtractor:
    """
    TF-IDF similarity-based entity extraction.
    Matches query tokens against brand/category corpora using
    character n-gram cosine similarity — handles typos, abbreviations,
    partial names automatically.
    """
    def __init__(self):
        self._lock   = threading.Lock()
        self._brand_names: list[str]   = []
        self._brand_texts: list[str]   = []
        self._cat_names:   list[str]   = []
        self._cat_texts:   list[str]   = []
        self._brand_vect = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 4), sublinear_tf=True)
        self._cat_vect   = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 4), sublinear_tf=True)
        self._brand_mat  = None
        self._cat_mat    = None
        self._train()

    def _train(self):
        with self._lock:
            self._brand_names = [b[0] for b in BRAND_CORPUS]
            self._brand_texts = [b[1] for b in BRAND_CORPUS]
            self._cat_names   = [c[0] for c in CATEGORY_CORPUS]
            self._cat_texts   = [c[1] for c in CATEGORY_CORPUS]
            self._brand_mat   = self._brand_vect.fit_transform(self._brand_texts)
            self._cat_mat     = self._cat_vect.fit_transform(self._cat_texts)
            logger.info(f"EntityExtractor: {len(self._brand_names)} brands, "
                        f"{len(self._cat_names)} categories indexed")

    def match_brand(self, query: str, threshold: float = 0.15) -> Optional[tuple[str, float]]:
        """Return (brand_name, score) or None."""
        try:
            q_vec = self._brand_vect.transform([query.lower()])
            sims  = cosine_similarity(q_vec, self._brand_mat)[0]
            idx   = int(sims.argmax())
            score = float(sims[idx])
            if score >= threshold:
                return (self._brand_names[idx], score)
        except Exception:
            pass
        return None

    def match_category(self, query: str, threshold: float = 0.12) -> Optional[tuple[str, float]]:
        """Return (category_name, score) or None."""
        try:
            q_vec = self._cat_vect.transform([query.lower()])
            sims  = cosine_similarity(q_vec, self._cat_mat)[0]
            idx   = int(sims.argmax())
            score = float(sims[idx])
            if score >= threshold:
                return (self._cat_names[idx], score)
        except Exception:
            pass
        return None

    def top_categories(self, query: str, top_k: int = 3) -> list[tuple[str, float]]:
        """Return top-k (category, score) pairs."""
        try:
            q_vec = self._cat_vect.transform([query.lower()])
            sims  = cosine_similarity(q_vec, self._cat_mat)[0]
            ranked = sorted(enumerate(sims), key=lambda x: x[1], reverse=True)
            return [(self._cat_names[i], float(s)) for i, s in ranked[:top_k] if s > 0.05]
        except Exception:
            return []


class _ResultRanker:
    """
    TF-IDF ranker for re-ranking DB results by query relevance.
    Fits dynamically on each result set — no persistent state needed.
    Character n-grams handle partial matches and misspellings.
    """
    def rank(self, query: str, products: list[dict], top_k: int = 50) -> list[dict]:
        if not products or not query.strip():
            return products
        names = [p.get("product_name", "") or "" for p in products]
        if not any(names):
            return products
        try:
            vect  = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 4),
                                     sublinear_tf=True, min_df=1)
            mat   = vect.fit_transform(names)
            q_vec = vect.transform([query.lower()])
            sims  = cosine_similarity(q_vec, mat)[0]
            ranked = sorted(zip(products, sims), key=lambda x: x[1], reverse=True)
            return [p for p, _ in ranked[:top_k]]
        except Exception:
            return products


# Instantiate singletons at module load (fast — < 200ms)
_intent_clf  = _IntentClassifier()
_entity_ext  = _EntityExtractor()
_result_rnk  = _ResultRanker()
logger.info("ShopPulse NLP engine ready (LinearSVC intent + TF-IDF entity extraction)")


# ──────────────────────────────────────────────────────────────────────────────
# STRUCTURED EXTRACTION HELPERS  (regex — fast, deterministic)
# ──────────────────────────────────────────────────────────────────────────────

def _extract_price_range(text: str) -> tuple[Optional[float], Optional[float]]:
    pmin = pmax = None
    m = re.search(r'₹?\s*(\d[\d,]*)\s*(?:to|-)\s*₹?\s*(\d[\d,]*)', text)
    if m:
        a = float(m.group(1).replace(',', ''))
        b = float(m.group(2).replace(',', ''))
        return min(a, b), max(a, b)
    m = re.search(r'(?:under|below|less\s+than|upto|up\s+to|within|budget|max)\s*₹?\s*(\d[\d,]*)', text)
    if m: pmax = float(m.group(1).replace(',', ''))
    m = re.search(r'(?:above|over|more\s+than|from|starting|min)\s*₹?\s*(\d[\d,]*)', text)
    if m: pmin = float(m.group(1).replace(',', ''))
    if pmax is None and pmin is None:
        m = re.search(r'₹\s*(\d[\d,]{2,})', text)
        if m: pmax = float(m.group(1).replace(',', ''))
    return pmin, pmax


def _remove_price_text(text: str) -> str:
    text = re.sub(r'(?:under|below|less\s+than|upto|up\s+to|within|budget|above|over|more\s+than|from|starting\s+from|max|min)\s*₹?\s*\d[\d,]*', '', text)
    text = re.sub(r'₹?\s*\d[\d,]*\s*(?:to|-)\s*₹?\s*\d[\d,]*', '', text)
    text = re.sub(r'₹\s*\d[\d,]*', '', text)
    return re.sub(r'\s+', ' ', text).strip()


def _extract_model_number(text: str) -> Optional[str]:
    """Extract model codes like WH-1000XM5, BT3302, 141, S24."""
    tokens = text.split()
    for t in tokens:
        # Alphanumeric with both letters + digits, length ≥ 2
        if re.search(r'[a-zA-Z]', t) and re.search(r'\d', t) and len(t) >= 2:
            # Exclude common words like "5G", "4G", "M2"
            if t.upper() not in ('5G', '4G', 'LTE', 'M1', 'M2', 'M3', 'AI'):
                return t.upper()
        # Pure numeric model (e.g. "141", "1000")
        if re.match(r'^\d{3,4}$', t):
            return t
    return None


ATTRIBUTE_KEYWORDS = {
    "wireless":    ["wireless", "bluetooth", "bt"],
    "wired":       ["wired", "3.5mm", "with wire"],
    "waterproof":  ["waterproof", "water resistant", "ipx", "ip67", "ip68"],
    "fast_charge": ["fast charge", "fast charging", "quick charge", "turbo", "supervooc"],
    "5g":          ["5g"],
    "noise_cancel":["anc", "noise cancelling", "noise cancellation", "active noise"],
    "gaming":      ["gaming", "gamer", "rgb"],
    "inverter":    ["inverter"],
    "5_star":      ["5 star", "five star"],
    "1.5_ton":     ["1.5 ton", "1.5ton"],
    "2_ton":       ["2 ton", "2ton"],
    "organic":     ["organic", "natural", "chemical free"],
}

SYNONYM_MAP = {
    "earphone": ["earbuds", "tws"], "earbuds": ["earphone", "tws"],
    "headphone": ["headphones"], "mobile": ["smartphone", "phone"],
    "laptop": ["notebook"], "trimmer": ["beard trimmer", "shaver"],
    "powerbank": ["power bank"], "ac": ["air conditioner", "split ac"],
    "air conditioner": ["ac", "split ac"], "fridge": ["refrigerator"],
    "refrigerator": ["fridge"], "chocolate": ["dairy milk"],
}

STOP_WORDS = {
    'a','an','the','for','with','in','on','at','of','and','or','is','are',
    'best','top','new','latest','buy','get','find','show','me','want','need',
    'looking','search','price','cheap','quality','india','online','purchase',
}


# ──────────────────────────────────────────────────────────────────────────────
# PARSED QUERY DATACLASS
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class ParsedQuery:
    raw:              str
    normalised:       str
    intent:           str             = "search"
    intent_scores:    dict            = field(default_factory=dict)
    brand:            Optional[str]   = None
    brand_confidence: float           = 0.0
    model_number:     Optional[str]   = None
    category:         Optional[str]   = None
    cat_confidence:   float           = 0.0
    price_max:        Optional[float] = None
    price_min:        Optional[float] = None
    attributes:       list[str]       = field(default_factory=list)
    core_terms:       list[str]       = field(default_factory=list)
    search_terms:     list[str]       = field(default_factory=list)
    synonyms_added:   list[str]       = field(default_factory=list)
    top_categories:   list           = field(default_factory=list)


# ──────────────────────────────────────────────────────────────────────────────
# MAIN PARSE FUNCTION
# ──────────────────────────────────────────────────────────────────────────────

def parse_query(raw_query: str) -> ParsedQuery:
    """
    ML-driven query parser.

    Layer 1 — LinearSVC intent classification
    Layer 2 — TF-IDF cosine similarity for brand + category
    Layer 3 — Regex for price range, model number, attributes
    Layer 4 — Search term generation with synonym expansion
    """
    normalised = re.sub(r'\s+', ' ', raw_query.lower().strip())
    pq = ParsedQuery(raw=raw_query, normalised=normalised)

    # ── Layer 1: Intent classification ────────────────────────
    pq.intent        = _intent_clf.predict(normalised)
    pq.intent_scores = _intent_clf.predict_proba(normalised)

    # ── Layer 2a: Brand extraction via TF-IDF similarity ──────
    # For queries with multiple brands (compare intent), find the first-mentioned brand
    # by trying prefix windows of the query (left-to-right bias)
    brand_result = None
    words = normalised.split()
    for window in range(1, len(words) + 1):
        prefix = ' '.join(words[:window])
        result = _entity_ext.match_brand(prefix, threshold=0.20)
        if result:
            brand_result = result
            break
    if not brand_result:
        brand_result = _entity_ext.match_brand(normalised, threshold=0.15)
    if brand_result:
        pq.brand, pq.brand_confidence = brand_result

    # ── Layer 2b: Category extraction via TF-IDF similarity ───
    # Remove brand from text before category matching to reduce noise
    text_for_cat = normalised
    if pq.brand:
        text_for_cat = text_for_cat.replace(pq.brand.lower(), '').strip()

    cat_result = _entity_ext.match_category(text_for_cat, threshold=0.12)
    if cat_result:
        pq.category, pq.cat_confidence = cat_result
    pq.top_categories = _entity_ext.top_categories(text_for_cat, top_k=3)

    # ── Layer 3a: Price range ─────────────────────────────────
    pq.price_min, pq.price_max = _extract_price_range(normalised)
    text_no_price = _remove_price_text(normalised)

    # ── Layer 3b: Model number ────────────────────────────────
    # Remove brand name before looking for model
    text_for_model = text_no_price
    if pq.brand:
        text_for_model = re.sub(re.escape(pq.brand.lower()), '', text_for_model).strip()
    pq.model_number = _extract_model_number(text_for_model)

    # ── Layer 3c: Attributes ──────────────────────────────────
    for attr, keywords in ATTRIBUTE_KEYWORDS.items():
        if any(kw in text_no_price for kw in keywords):
            pq.attributes.append(attr)

    # ── Layer 4: Core terms and search string generation ──────
    noise = STOP_WORDS | {kw for kws in ATTRIBUTE_KEYWORDS.values() for kw in kws}
    price_words = {'under','below','above','over','upto','budget','within','from','between','to','max','min'}
    skip_next = 0
    core = []
    tokens = text_no_price.split()
    for i, tok in enumerate(tokens):
        if i < skip_next: continue
        if tok in noise or tok in price_words: continue
        if re.match(r'^\d[\d,]*$', tok) and float(tok.replace(',','')) > 99:
            skip_next = i + 2
            continue
        core.append(tok)
    pq.core_terms = core

    # Build search terms (most specific → broadest)
    search: list[str] = []

    if pq.brand and pq.model_number:
        nouns = [t for t in core if t not in (pq.brand.lower(), pq.model_number.lower()) and len(t) > 2]
        if nouns:
            search.append(f"{pq.brand} {nouns[0]} {pq.model_number}")
        search.append(f"{pq.brand} {pq.model_number}")

    if pq.brand:
        nouns = [t for t in core if t != pq.brand.lower() and t != (pq.model_number or '').lower()]
        if nouns:
            search.append(f"{pq.brand} {' '.join(nouns[:2])}")
        search.append(pq.brand)

    product_terms = [t for t in core if t != (pq.brand or '').lower()]
    if product_terms:
        search.append(' '.join(product_terms[:4]))
        if len(product_terms) > 1:
            search.append(product_terms[0])

    # Raw query as final fallback
    if raw_query.lower() not in [s.lower() for s in search]:
        search.append(raw_query)

    # Synonym expansion
    for term in product_terms[:2]:
        if term in SYNONYM_MAP:
            for syn in SYNONYM_MAP[term]:
                cand = f"{pq.brand} {syn}" if pq.brand else syn
                if cand.lower() not in [s.lower() for s in search]:
                    search.append(cand)
                    pq.synonyms_added.append(syn)

    # Deduplicate
    seen: set[str] = set()
    final: list[str] = []
    for s in search:
        s = s.strip()
        if s and s.lower() not in seen and len(s) >= 2:
            seen.add(s.lower())
            final.append(s)

    pq.search_terms = final if final else [raw_query]

    logger.info(
        f"NLP: '{raw_query}' → intent={pq.intent}({pq.intent_scores.get(pq.intent,0):.2f}) "
        f"brand={pq.brand}({pq.brand_confidence:.2f}) "
        f"cat={pq.category}({pq.cat_confidence:.2f}) "
        f"model={pq.model_number} price=[{pq.price_min},{pq.price_max}] "
        f"terms={pq.search_terms[:2]}"
    )
    return pq


# ──────────────────────────────────────────────────────────────────────────────
# POST-RETRIEVAL PROCESSING
# ──────────────────────────────────────────────────────────────────────────────

def filter_by_price(products: list[dict], pq: ParsedQuery) -> list[dict]:
    if pq.price_min is None and pq.price_max is None:
        return products
    out = []
    for p in products:
        price = p.get('min_price') or p.get('price')
        if price is None:
            out.append(p)
            continue
        if pq.price_max and price > pq.price_max:
            continue
        if pq.price_min and price < pq.price_min:
            continue
        out.append(p)
    return out


def rank_results(products: list[dict], pq: ParsedQuery) -> list[dict]:
    """
    Two-stage ranking:
      Stage 1: Rule-based score (brand match, model match, category, price)
      Stage 2: TF-IDF cosine similarity re-rank on top candidates
    """
    if not products:
        return products

    def rule_score(p: dict) -> float:
        s    = 0.0
        name = (p.get('product_name') or '').lower()
        bnd  = (p.get('brand') or '').lower()
        if pq.brand and pq.brand.lower() in (bnd + ' ' + name): s += 40
        if pq.model_number and pq.model_number.lower() in name:  s += 35
        if pq.category and p.get('category') == pq.category:    s += 20
        for term in pq.core_terms[:3]:
            if term in name: s += 8
        if pq.price_max:
            price = p.get('min_price') or p.get('price') or 0
            if 0 < price <= pq.price_max:
                s += (price / pq.price_max) * 10
        s += min(p.get('platform_count', 0) * 3, 12)
        return s

    stage1 = sorted(products, key=rule_score, reverse=True)

    # TF-IDF re-rank on top candidates
    q_for_tfidf = ' '.join(filter(None, [pq.brand, pq.model_number] + pq.core_terms[:4]))
    reranked    = _result_rnk.rank(q_for_tfidf, stage1[:30], top_k=30)

    reranked_ids = {p.get('master_product_id') for p in reranked}
    tail = [p for p in stage1[30:] if p.get('master_product_id') not in reranked_ids]
    return reranked + tail
