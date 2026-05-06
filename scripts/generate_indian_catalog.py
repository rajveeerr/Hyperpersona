"""Generate ~500 Indian-market products + categories for the storefront.

Why a generator (vs hand-authored JSON):
  500 hand-curated products would be ~50KB of repetitive copy-paste. A
  generator keeps the category metadata in one place — brands, image
  pools, price ranges, variant axes — and combines them into believable
  rows. Output is deterministic per (CATEGORY × seed) so re-runs produce
  the same slugs (idempotent for `make seed-products`).

Output:
  server/src/data/products.seed.json       (~500 rows, replaces existing)
  server/src/data/categories.seed.json     (~40 rows, replaces existing)

The 13 legacy products are preserved verbatim at the front of the
products list because customer events / cart / wishlist rows still
reference them.

Verticals reused: apparel, electronics, general, furniture
  (extending the enum requires a code change in
   server/src/schemas/catalog.py + a server redeploy — out of scope.)

Currency: prices are integer rupees. The frontend formatter
  (apps/web/src/shared/lib/format.ts) is updated separately to render ₹.
"""

from __future__ import annotations

import hashlib
import json
import os
import random
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SEED_DIR = REPO_ROOT / "server" / "src" / "data"

# Deterministic so re-running the generator yields the same slugs/SKUs.
RNG = random.Random(20260507)

# Verified Unsplash photo pools (HEAD-checked, no 404s) — see scripts/image_pools.py.
sys.path.insert(0, str(REPO_ROOT))
from scripts.image_pools import IMAGE_POOLS, verify_pools  # noqa: E402

# Cache verification across runs so we don't HEAD ~250 URLs every time.
_CACHE = Path("/tmp/verified_pools.json")
if os.getenv("REVERIFY_IMAGES") == "1" or not _CACHE.exists():
    VERIFIED_POOLS = verify_pools(IMAGE_POOLS)
    _CACHE.write_text(json.dumps(VERIFIED_POOLS))
else:
    VERIFIED_POOLS = json.loads(_CACHE.read_text())
    print(f"using cached image verification from {_CACHE} (set REVERIFY_IMAGES=1 to re-check)")


# --- 1. Category metadata --------------------------------------------------
#
# Each entry drives a batch of products:
#   count        — how many products to spawn in this category
#   vertical     — must be one of {apparel, electronics, general, furniture}
#   department   — free-form bucket used by the FE PDP and event payloads
#   price_range  — (low, high) in integer ₹
#   bases        — list of "base product names". Each base spawns variants
#                  by brand × adjective.
#   adjectives   — qualifiers prepended to the base name (e.g. "Slim Fit")
#   brands       — pool to draw from
#   colors       — variant axis (id+label generated)
#   sizes        — variant axis; empty list → no sizeOptions on PDP
#   storage      — variant axis for electronics; empty list → none
#   tags         — appended to every product in this category
#   ptags        — personalizationTags appended to every product
#   features     — pool of 1-line features; each product samples 3-5
#   specs        — pool of "Label: Value" specifications; each samples 4-6
#   images       — Unsplash photo IDs; products rotate through these
#   hero         — landing-page hero photo for the category
#   description  — category page copy

CATEGORIES: dict[str, dict] = {
    # -------- Existing (preserved as-is for backward-compat) -------------
    # The 5 legacy categories (trail-running, city-commute, studio-recovery,
    # home-living, tech-desk) are appended from the legacy seed file later;
    # we don't regenerate them.

    # ============ MEN'S FASHION ============
    "mens-shirts": {
        "count": 26,
        "name": "Men's Shirts",
        "description": "Formal, casual, linen, and printed shirts for every occasion.",
        "vertical": "apparel",
        "department": "Mens",
        "price_range": (799, 3499),
        "bases": ["Cotton Shirt", "Linen Shirt", "Oxford Shirt", "Poplin Shirt", "Chambray Shirt", "Twill Shirt", "Flannel Shirt", "Mandarin Collar Shirt"],
        "adjectives": ["Slim Fit", "Regular Fit", "Tailored", "Classic", "Modern", "Heritage", "Premium", "Essential"],
        "brands": ["Allen Solly", "Peter England", "Louis Philippe", "Van Heusen", "Arrow", "Park Avenue", "John Players", "Raymond", "Blackberrys"],
        "colors": ["white", "sky-blue", "navy", "black", "olive", "lavender", "pink", "charcoal", "sand"],
        "sizes": ["S", "M", "L", "XL", "XXL"],
        "storage": [],
        "tags": ["mens", "shirt", "office", "casual"],
        "ptags": ["mens-fashion", "formal-wear", "smart-casual"],
        "features": ["Cuffed sleeves", "Spread collar", "Curved hem", "Single chest pocket", "Mother-of-pearl buttons", "Tailored taper", "Breathable weave", "Wrinkle-resistant finish"],
        "specs": ["Material: 100% cotton", "Care: Machine wash cold", "Fit: Slim", "Pattern: Solid", "Sleeve: Full sleeve", "Collar: Spread", "Closure: Button", "Origin: Made in India"],
        "images": ["photo-1602810318383-e386cc2a3ccf", "photo-1620012253295-c15cc3e65df4", "photo-1603252109303-2751441dd157", "photo-1598033129183-c4f50c736f10", "photo-1596755094514-f87e34085b2c", "photo-1564859228273-274232fdb516"],
        "hero": "photo-1602810318383-e386cc2a3ccf",
    },
    "mens-tshirts": {
        "count": 22,
        "name": "Men's T-Shirts",
        "description": "Crewneck, polo, and graphic tees for everyday rotation.",
        "vertical": "apparel",
        "department": "Mens",
        "price_range": (399, 1799),
        "bases": ["Crewneck Tee", "V-Neck Tee", "Polo Shirt", "Henley Tee", "Graphic Tee", "Striped Tee", "Pocket Tee", "Long Sleeve Tee"],
        "adjectives": ["Cotton", "Premium", "Combed Cotton", "Organic", "Performance", "Vintage", "Essential", "Studio"],
        "brands": ["Jockey", "FCUK", "Levi's", "United Colors of Benetton", "H&M", "Puma", "Adidas", "Marks & Spencer", "Wrogn"],
        "colors": ["white", "black", "navy", "olive", "burgundy", "grey-melange", "mustard", "forest", "rust"],
        "sizes": ["S", "M", "L", "XL", "XXL"],
        "storage": [],
        "tags": ["mens", "tshirt", "casual", "everyday"],
        "ptags": ["mens-fashion", "casual-wear", "summer-essential"],
        "features": ["Soft hand-feel", "Reinforced shoulder seams", "Pre-shrunk", "Tagless neck label", "Breathable cotton", "Ribbed crew", "Side-seam fit", "Easy care"],
        "specs": ["Material: 100% cotton", "GSM: 180", "Care: Machine wash", "Fit: Regular", "Neckline: Crew", "Sleeve: Half", "Pattern: Solid", "Wash: Pre-washed"],
        "images": ["photo-1521572163474-6864f9cf17ab", "photo-1583743814966-8936f5b7be1a", "photo-1576566588028-4147f3842f27", "photo-1503341504253-dff4815485f1", "photo-1622445275576-721325763afe"],
        "hero": "photo-1521572163474-6864f9cf17ab",
    },
    "mens-jeans": {
        "count": 18,
        "name": "Men's Jeans",
        "description": "Slim, straight, and relaxed denim cut for daily wear.",
        "vertical": "apparel",
        "department": "Mens",
        "price_range": (1299, 4999),
        "bases": ["Slim Jeans", "Straight Jeans", "Relaxed Jeans", "Skinny Jeans", "Tapered Jeans", "Bootcut Jeans"],
        "adjectives": ["Stretch", "Distressed", "Vintage Wash", "Dark Wash", "Light Wash", "Black", "Indigo", "Selvedge"],
        "brands": ["Levi's", "Wrangler", "Lee", "Pepe Jeans", "Diesel", "Spykar", "Killer", "Numero Uno"],
        "colors": ["dark-indigo", "mid-blue", "black", "stone-wash", "vintage-blue", "raw-denim"],
        "sizes": ["28", "30", "32", "34", "36", "38", "40"],
        "storage": [],
        "tags": ["mens", "jeans", "denim", "casual"],
        "ptags": ["mens-fashion", "denim", "everyday"],
        "features": ["5-pocket styling", "Stretch denim", "Reinforced rivets", "Mid-rise", "Whiskering details", "Branded leather patch", "YKK zip fly", "Belt loops"],
        "specs": ["Material: 98% cotton, 2% elastane", "Wash: Dark indigo", "Fit: Slim", "Rise: Mid", "Closure: Zip fly + button", "Pockets: 5", "Care: Machine wash inside out"],
        "images": ["photo-1542272604-787c3835535d", "photo-1604176354204-9268737828e4", "photo-1582418702059-97ebd0ac0a9d", "photo-1473966968600-fa801b869a1a"],
        "hero": "photo-1542272604-787c3835535d",
    },
    "mens-trousers": {
        "count": 14,
        "name": "Men's Trousers",
        "description": "Formal trousers, chinos, and joggers.",
        "vertical": "apparel",
        "department": "Mens",
        "price_range": (999, 3999),
        "bases": ["Chino Trouser", "Formal Trouser", "Cotton Trouser", "Wool Blend Trouser", "Cargo Trouser", "Linen Trouser"],
        "adjectives": ["Slim Fit", "Regular Fit", "Tapered", "Cropped", "Premium", "Casual", "Office"],
        "brands": ["Louis Philippe", "Allen Solly", "Van Heusen", "Park Avenue", "Peter England", "Raymond", "Arrow"],
        "colors": ["beige", "khaki", "navy", "black", "olive", "stone", "charcoal"],
        "sizes": ["28", "30", "32", "34", "36", "38"],
        "storage": [],
        "tags": ["mens", "trouser", "office", "formal"],
        "ptags": ["mens-fashion", "office-wear"],
        "features": ["Flat-front design", "Side-entry pockets", "Welt back pocket", "Hidden zip fly", "Crease-free finish", "Wool-blend warmth"],
        "specs": ["Material: Cotton blend", "Fit: Slim", "Closure: Zip + hook", "Pockets: 4", "Care: Dry clean recommended"],
        "images": ["photo-1473966968600-fa801b869a1a", "photo-1594633312681-425c7b97ccd1", "photo-1593030103066-0093718efeb9"],
        "hero": "photo-1594633312681-425c7b97ccd1",
    },
    "mens-jackets": {
        "count": 12,
        "name": "Men's Jackets & Coats",
        "description": "Bombers, blazers, parkas, and lightweight outerwear.",
        "vertical": "apparel",
        "department": "Mens",
        "price_range": (1999, 8999),
        "bases": ["Bomber Jacket", "Blazer", "Parka", "Puffer Jacket", "Denim Jacket", "Trench Coat", "Quilted Jacket"],
        "adjectives": ["Tailored", "Insulated", "Hooded", "Lightweight", "Heritage", "Modern Cut"],
        "brands": ["Tommy Hilfiger", "U.S. Polo Assn.", "Allen Solly", "Wrogn", "Roadster", "Levi's", "Wildcraft"],
        "colors": ["olive", "black", "navy", "tan", "grey", "brown"],
        "sizes": ["S", "M", "L", "XL", "XXL"],
        "storage": [],
        "tags": ["mens", "jacket", "outerwear", "winter"],
        "ptags": ["mens-fashion", "winter-wear", "premium"],
        "features": ["Ribbed cuffs", "Two-way zip", "Chest pocket", "Insulated body", "Water-repellent shell", "Detachable hood"],
        "specs": ["Material: Polyester shell, polyfill insulation", "Closure: Zip", "Care: Machine wash gentle", "Lining: Quilted"],
        "images": ["photo-1551028719-00167b16eac5", "photo-1591047139829-d91aecb6caea", "photo-1559563458-527698bf5295"],
        "hero": "photo-1551028719-00167b16eac5",
    },
    "mens-ethnic": {
        "count": 18,
        "name": "Men's Ethnic Wear",
        "description": "Kurtas, kurta-pyjama sets, sherwanis, and Nehru jackets.",
        "vertical": "apparel",
        "department": "Mens",
        "price_range": (1199, 12999),
        "bases": ["Cotton Kurta", "Linen Kurta", "Silk Kurta", "Kurta Pyjama Set", "Sherwani", "Nehru Jacket", "Bandhgala Suit", "Pathani Suit"],
        "adjectives": ["Embroidered", "Hand-block Printed", "Festive", "Wedding", "Classic", "Traditional", "Designer"],
        "brands": ["Manyavar", "FabIndia", "Tasva", "Twamev", "Soch", "Aurelia", "BIBA Mens"],
        "colors": ["white", "ivory", "maroon", "gold", "saffron", "navy", "cream", "pista", "rust"],
        "sizes": ["38", "40", "42", "44", "46"],
        "storage": [],
        "tags": ["mens", "ethnic", "kurta", "wedding", "festive"],
        "ptags": ["mens-fashion", "ethnic-wear", "festive", "wedding"],
        "features": ["Hand-embroidered placket", "Side slits", "Mandarin collar", "Pure silk panel", "Brocade detailing", "Hand-block print"],
        "specs": ["Material: Pure cotton", "Length: Knee-length", "Closure: Button placket", "Care: Dry clean only", "Occasion: Festive"],
        "images": ["photo-1595777457583-95e059d581b8", "photo-1583391733956-3750e0ff4e8b", "photo-1622519407650-3df9883f76a5"],
        "hero": "photo-1595777457583-95e059d581b8",
    },
    "mens-shoes-formal": {
        "count": 14,
        "name": "Men's Formal Shoes",
        "description": "Oxfords, Derbys, monks, and loafers for office and formal wear.",
        "vertical": "apparel",
        "department": "Mens",
        "price_range": (1799, 7999),
        "bases": ["Oxford", "Derby", "Monk Strap", "Brogue", "Penny Loafer", "Tassel Loafer"],
        "adjectives": ["Leather", "Patent Leather", "Suede", "Premium", "Hand-stitched", "Italian"],
        "brands": ["Bata", "Hush Puppies", "Clarks", "Red Tape", "Bond Street", "Louis Philippe"],
        "colors": ["black", "tan", "brown", "burgundy", "oxblood"],
        "sizes": ["6", "7", "8", "9", "10", "11"],
        "storage": [],
        "tags": ["mens", "shoes", "formal", "leather"],
        "ptags": ["mens-fashion", "formal-wear", "office-wear"],
        "features": ["Genuine leather upper", "Cushioned insole", "Anti-slip sole", "Hand-stitched welt", "Closed lacing", "Goodyear welted"],
        "specs": ["Upper: Genuine leather", "Sole: TPR", "Closure: Lace-up", "Lining: Soft fabric", "Care: Polish regularly"],
        "images": ["photo-1614252369475-531eba835eb1", "photo-1582897085656-c636d006a246", "photo-1533867617858-e7b97e060509"],
        "hero": "photo-1614252369475-531eba835eb1",
    },
    "mens-shoes-casual": {
        "count": 16,
        "name": "Men's Casual Shoes",
        "description": "Sneakers, slip-ons, espadrilles, and boat shoes.",
        "vertical": "apparel",
        "department": "Mens",
        "price_range": (999, 6999),
        "bases": ["Low-Top Sneaker", "High-Top Sneaker", "Slip-On", "Boat Shoe", "Espadrille", "Canvas Sneaker", "Chukka Boot"],
        "adjectives": ["Classic", "Retro", "Suede", "Mesh", "Trail", "Court", "Lifestyle"],
        "brands": ["Adidas", "Nike", "Puma", "Reebok", "Asian", "Sparx", "Skechers", "Vans"],
        "colors": ["white", "black", "grey", "navy", "olive", "tan"],
        "sizes": ["6", "7", "8", "9", "10", "11", "12"],
        "storage": [],
        "tags": ["mens", "shoes", "casual", "sneakers"],
        "ptags": ["mens-fashion", "casual-wear", "everyday"],
        "features": ["Padded collar", "Cushioned EVA midsole", "Rubber outsole", "Breathable mesh upper", "Memory-foam footbed", "Lace-up closure"],
        "specs": ["Upper: Synthetic", "Sole: Rubber", "Closure: Lace-up", "Care: Wipe with damp cloth"],
        "images": ["photo-1542291026-7eec264c27ff", "photo-1600185365483-26d7a4cc7519", "photo-1606107557195-0e29a4b5b4aa", "photo-1595950653106-6c9ebd614d3a"],
        "hero": "photo-1542291026-7eec264c27ff",
    },
    "mens-shoes-sports": {
        "count": 14,
        "name": "Men's Sports Shoes",
        "description": "Running, training, court, and trail performance shoes.",
        "vertical": "apparel",
        "department": "Mens",
        "price_range": (1499, 9999),
        "bases": ["Running Shoe", "Training Shoe", "Trail Shoe", "Walking Shoe", "Court Shoe", "Cross-Training Shoe"],
        "adjectives": ["Lightweight", "Cushioned", "Performance", "Pro", "Energy", "Glide", "Boost"],
        "brands": ["Nike", "Adidas", "Puma", "ASICS", "New Balance", "Reebok", "Skechers", "Decathlon"],
        "colors": ["black", "white", "blue", "red", "grey", "neon-green"],
        "sizes": ["6", "7", "8", "9", "10", "11", "12"],
        "storage": [],
        "tags": ["mens", "shoes", "sports", "running"],
        "ptags": ["mens-fashion", "fitness", "performance"],
        "features": ["EVA midsole cushioning", "Mesh upper", "Reflective accents", "Removable insole", "Heel pull tab", "Forefoot flex grooves"],
        "specs": ["Upper: Engineered mesh", "Midsole: EVA foam", "Outsole: Carbon rubber", "Drop: 8mm", "Weight: 280g (UK 9)"],
        "images": ["photo-1542291026-7eec264c27ff", "photo-1539185441755-769473a23570", "photo-1608231387042-66d1773070a5", "photo-1556906781-9a412961c28c"],
        "hero": "photo-1539185441755-769473a23570",
    },
    "mens-accessories": {
        "count": 10,
        "name": "Men's Accessories",
        "description": "Belts, wallets, ties, and pocket squares.",
        "vertical": "general",
        "department": "Mens",
        "price_range": (399, 2999),
        "bases": ["Leather Belt", "Bifold Wallet", "Card Holder", "Silk Tie", "Pocket Square", "Cufflinks Set"],
        "adjectives": ["Classic", "Reversible", "Slim", "Premium", "Hand-stitched"],
        "brands": ["Tommy Hilfiger", "Hidesign", "Woodland", "Wildhorn", "Allen Solly"],
        "colors": ["black", "tan", "brown"],
        "sizes": [],
        "storage": [],
        "tags": ["mens", "accessory"],
        "ptags": ["mens-fashion", "premium"],
        "features": ["Genuine leather", "Multiple card slots", "RFID-blocking lining", "Hand-stitched edges"],
        "specs": ["Material: Genuine leather", "Care: Wipe clean"],
        "images": ["photo-1553062407-98eeb64c6a62", "photo-1627123424574-724758594e93"],
        "hero": "photo-1553062407-98eeb64c6a62",
    },

    # ============ WOMEN'S FASHION ============
    "womens-saree": {
        "count": 28,
        "name": "Sarees",
        "description": "Silk, cotton, georgette, and designer sarees for every occasion.",
        "vertical": "apparel",
        "department": "Womens",
        "price_range": (1299, 24999),
        "bases": ["Banarasi Silk Saree", "Kanjivaram Saree", "Cotton Saree", "Chiffon Saree", "Georgette Saree", "Linen Saree", "Designer Saree", "Tussar Silk Saree", "Chanderi Saree"],
        "adjectives": ["Hand-woven", "Embroidered", "Block-printed", "Zari", "Bridal", "Traditional", "Festive", "Designer"],
        "brands": ["Sabyasachi Inspired", "Tarini By Tanika", "Kalki Fashion", "Soch", "BIBA", "Manyavar Mohey", "Karagiri"],
        "colors": ["maroon", "red", "gold", "pink", "navy", "emerald", "cream", "purple", "rust", "teal"],
        "sizes": ["Free Size"],
        "storage": [],
        "tags": ["womens", "saree", "ethnic", "festive", "wedding"],
        "ptags": ["womens-fashion", "ethnic-wear", "wedding", "festive"],
        "features": ["Pure silk weave", "Zari border", "Hand-tassels at pallu", "Includes blouse piece (0.8m)", "Bridal-grade zari", "Hand-block print"],
        "specs": ["Material: Pure silk", "Length: 5.5m saree + 0.8m blouse", "Care: Dry clean only", "Border: 4-inch zari", "Origin: Varanasi, India"],
        "images": ["photo-1610030469983-98e550d6193c", "photo-1583391733956-3750e0ff4e8b", "photo-1602810318660-d2a7df73fd31", "photo-1624819072019-1adc7c41fbed"],
        "hero": "photo-1610030469983-98e550d6193c",
    },
    "womens-kurti": {
        "count": 24,
        "name": "Kurtis & Tunics",
        "description": "Anarkali, A-line, straight-cut, and printed kurtis.",
        "vertical": "apparel",
        "department": "Womens",
        "price_range": (599, 4999),
        "bases": ["Anarkali Kurti", "A-line Kurti", "Straight Kurti", "Asymmetric Kurti", "High-Low Kurti", "Embroidered Kurta", "Block-Print Kurta", "Cotton Kurti"],
        "adjectives": ["Embroidered", "Printed", "Festive", "Casual", "Office", "Designer", "Hand-block"],
        "brands": ["BIBA", "Aurelia", "W for Woman", "Soch", "Global Desi", "FabIndia", "Anouk", "Libas"],
        "colors": ["maroon", "navy", "mustard", "rust", "teal", "white", "pista", "indigo", "black"],
        "sizes": ["XS", "S", "M", "L", "XL", "XXL"],
        "storage": [],
        "tags": ["womens", "kurti", "kurta", "ethnic", "everyday"],
        "ptags": ["womens-fashion", "ethnic-wear", "everyday"],
        "features": ["Hand-block printed", "Three-quarter sleeves", "Side slits", "Round neckline", "Concealed side zip", "Ankle length"],
        "specs": ["Material: 100% cotton", "Length: Knee-length", "Care: Hand wash cold", "Pattern: Block print", "Sleeve: 3/4 sleeve"],
        "images": ["photo-1621072156002-e2fccdc0b176", "photo-1583391733956-3750e0ff4e8b", "photo-1610030469983-98e550d6193c"],
        "hero": "photo-1621072156002-e2fccdc0b176",
    },
    "womens-lehenga": {
        "count": 14,
        "name": "Lehengas",
        "description": "Bridal, festive, and ready-to-wear lehengas.",
        "vertical": "apparel",
        "department": "Womens",
        "price_range": (3499, 49999),
        "bases": ["Bridal Lehenga", "Festive Lehenga", "Crop-Top Lehenga", "A-line Lehenga", "Mermaid Lehenga", "Ghagra Choli"],
        "adjectives": ["Heavy-Embroidered", "Sequined", "Mirror-Work", "Bandhej", "Designer", "Wedding"],
        "brands": ["Sabyasachi Inspired", "Kalki Fashion", "BIBA", "Manyavar Mohey", "Karagiri"],
        "colors": ["red", "pink", "green", "wine", "ivory", "peach", "royal-blue"],
        "sizes": ["XS", "S", "M", "L", "XL"],
        "storage": [],
        "tags": ["womens", "lehenga", "ethnic", "wedding", "bridal"],
        "ptags": ["womens-fashion", "ethnic-wear", "wedding", "bridal"],
        "features": ["Hand-embroidered zardosi", "Net dupatta with sequins", "Padded blouse", "Concealed back zip"],
        "specs": ["Material: Net + raw silk", "Includes: Lehenga + Choli + Dupatta", "Care: Dry clean only", "Closure: Hook + Zip"],
        "images": ["photo-1610030469983-98e550d6193c", "photo-1583391733956-3750e0ff4e8b"],
        "hero": "photo-1610030469983-98e550d6193c",
    },
    "womens-dresses": {
        "count": 18,
        "name": "Women's Dresses",
        "description": "Maxi, midi, bodycon, and shift dresses for casual to formal.",
        "vertical": "apparel",
        "department": "Womens",
        "price_range": (799, 4999),
        "bases": ["Maxi Dress", "Midi Dress", "Bodycon Dress", "Shift Dress", "Wrap Dress", "Skater Dress", "Slip Dress"],
        "adjectives": ["Floral", "Solid", "Pleated", "Boho", "Office", "Cocktail", "Summer"],
        "brands": ["Vero Moda", "ONLY", "Forever 21", "H&M", "Marks & Spencer", "MANGO", "Zara", "AND", "Allen Solly Womens"],
        "colors": ["black", "navy", "red", "white", "olive", "blush", "mustard", "burgundy"],
        "sizes": ["XS", "S", "M", "L", "XL"],
        "storage": [],
        "tags": ["womens", "dress", "western"],
        "ptags": ["womens-fashion", "western-wear"],
        "features": ["Concealed back zip", "Lined bodice", "Smocked back", "Tiered hem", "Belted waist", "Side pockets"],
        "specs": ["Material: Polyester blend", "Length: Knee-length", "Care: Hand wash", "Lining: Polyester"],
        "images": ["photo-1539008835657-9e8e9680c956", "photo-1496217590455-aa63a8350eea", "photo-1572804013309-59a88b7e92f1"],
        "hero": "photo-1539008835657-9e8e9680c956",
    },
    "womens-tops": {
        "count": 16,
        "name": "Women's Tops",
        "description": "Blouses, tees, tunics, and crop tops.",
        "vertical": "apparel",
        "department": "Womens",
        "price_range": (399, 2999),
        "bases": ["Crop Top", "Blouse", "Tunic", "Peplum Top", "Off-Shoulder Top", "Cami Top", "Henley Top"],
        "adjectives": ["Floral", "Solid", "Striped", "Lace", "Ruffled", "Casual", "Smart"],
        "brands": ["Vero Moda", "ONLY", "FCUK", "Marks & Spencer", "AND", "Forever 21", "H&M"],
        "colors": ["white", "black", "pink", "olive", "mustard", "rust", "navy"],
        "sizes": ["XS", "S", "M", "L", "XL"],
        "storage": [],
        "tags": ["womens", "top", "casual"],
        "ptags": ["womens-fashion", "western-wear"],
        "features": ["Cropped hem", "Boat neckline", "Half-sleeve", "Smocked back", "Self-tie front"],
        "specs": ["Material: Cotton blend", "Length: Cropped", "Care: Hand wash"],
        "images": ["photo-1564257577-0d1b7b0c5a35", "photo-1551803091-e20673f15770", "photo-1583744946564-b52ac1c389c8"],
        "hero": "photo-1564257577-0d1b7b0c5a35",
    },
    "womens-jeans-pants": {
        "count": 14,
        "name": "Women's Jeans & Pants",
        "description": "Skinny, bootcut, palazzo, and culottes.",
        "vertical": "apparel",
        "department": "Womens",
        "price_range": (899, 3999),
        "bases": ["Skinny Jeans", "Bootcut Jeans", "Mom Jeans", "Wide-Leg Jeans", "Palazzo Pant", "Culottes", "Cigarette Pant"],
        "adjectives": ["High-Waist", "Mid-Rise", "Distressed", "Stretch", "Vintage Wash"],
        "brands": ["Levi's Womens", "Pepe Jeans", "ONLY", "Vero Moda", "AND", "FCUK"],
        "colors": ["dark-indigo", "mid-blue", "black", "white", "stone-wash"],
        "sizes": ["26", "28", "30", "32", "34"],
        "storage": [],
        "tags": ["womens", "jeans", "denim", "casual"],
        "ptags": ["womens-fashion", "denim"],
        "features": ["Mid-rise", "5-pocket styling", "Stretch denim", "Whiskering details", "Frayed hem"],
        "specs": ["Material: 98% cotton, 2% elastane", "Rise: Mid", "Closure: Zip + button"],
        "images": ["photo-1541099649105-f69ad21f3246", "photo-1582418702059-97ebd0ac0a9d"],
        "hero": "photo-1541099649105-f69ad21f3246",
    },
    "womens-heels": {
        "count": 14,
        "name": "Women's Heels",
        "description": "Stilettos, block heels, kitten heels, and wedges.",
        "vertical": "apparel",
        "department": "Womens",
        "price_range": (899, 5999),
        "bases": ["Stiletto Heel", "Block Heel", "Kitten Heel", "Wedge", "Pump", "Strappy Heel", "Platform Heel"],
        "adjectives": ["Patent", "Suede", "Embellished", "Classic", "Office"],
        "brands": ["Bata", "Catwalk", "Steve Madden", "Carlton London", "Mochi", "Inc.5"],
        "colors": ["black", "nude", "red", "gold", "silver", "champagne"],
        "sizes": ["3", "4", "5", "6", "7", "8"],
        "storage": [],
        "tags": ["womens", "shoes", "heels"],
        "ptags": ["womens-fashion", "formal-wear", "occasion"],
        "features": ["Pointed toe", "Cushioned insole", "Anti-skid sole", "Padded straps", "Adjustable buckle"],
        "specs": ["Heel height: 3 inches", "Upper: PU leather", "Sole: TPR"],
        "images": ["photo-1543163521-1bf539c55dd2", "photo-1606107557195-0e29a4b5b4aa"],
        "hero": "photo-1543163521-1bf539c55dd2",
    },
    "womens-flats": {
        "count": 12,
        "name": "Women's Flats",
        "description": "Ballerinas, mules, slip-ons, and loafers.",
        "vertical": "apparel",
        "department": "Womens",
        "price_range": (499, 3999),
        "bases": ["Ballerina", "Mule", "Slip-On", "Loafer", "Espadrille Flat", "Pointed Flat"],
        "adjectives": ["Bow-detail", "Embellished", "Embroidered", "Classic", "Comfort"],
        "brands": ["Bata", "Mochi", "Catwalk", "Inc.5", "Aldo"],
        "colors": ["black", "tan", "rose", "gold", "silver", "white"],
        "sizes": ["3", "4", "5", "6", "7", "8"],
        "storage": [],
        "tags": ["womens", "shoes", "flat", "everyday"],
        "ptags": ["womens-fashion", "casual-wear"],
        "features": ["Cushioned footbed", "Memory foam insole", "Anti-slip outsole", "Bow detail"],
        "specs": ["Upper: Faux leather", "Sole: TPR", "Heel: Flat"],
        "images": ["photo-1543163521-1bf539c55dd2", "photo-1581101767113-1677fc2b0c8e"],
        "hero": "photo-1581101767113-1677fc2b0c8e",
    },
    "womens-sandals": {
        "count": 12,
        "name": "Women's Sandals",
        "description": "Flat sandals, slides, and ethnic juttis.",
        "vertical": "apparel",
        "department": "Womens",
        "price_range": (399, 2999),
        "bases": ["Flat Sandal", "Slide Sandal", "Jutti", "Mojari", "Strappy Sandal", "Kolhapuri"],
        "adjectives": ["Ethnic", "Embroidered", "Beaded", "Casual", "Beach"],
        "brands": ["Mochi", "Bata", "Soch", "FabIndia", "Inc.5"],
        "colors": ["gold", "silver", "tan", "red", "navy", "ivory"],
        "sizes": ["3", "4", "5", "6", "7", "8"],
        "storage": [],
        "tags": ["womens", "sandal", "ethnic"],
        "ptags": ["womens-fashion", "ethnic-wear", "casual"],
        "features": ["Hand-embroidered upper", "Cushioned footbed", "Anti-slip sole", "Closed back"],
        "specs": ["Upper: Velvet + zari", "Sole: TPR"],
        "images": ["photo-1605408499391-6368c628ef42", "photo-1543163521-1bf539c55dd2"],
        "hero": "photo-1605408499391-6368c628ef42",
    },
    "womens-handbags": {
        "count": 14,
        "name": "Women's Handbags",
        "description": "Totes, slings, clutches, and shoulder bags.",
        "vertical": "general",
        "department": "Womens",
        "price_range": (799, 6999),
        "bases": ["Tote Bag", "Sling Bag", "Clutch", "Shoulder Bag", "Crossbody Bag", "Backpack Purse", "Hobo Bag"],
        "adjectives": ["Quilted", "Structured", "Embellished", "Classic", "Mini", "Oversized"],
        "brands": ["Hidesign", "Caprese", "Lavie", "Baggit", "Da Milano", "Charles & Keith"],
        "colors": ["black", "tan", "red", "blush", "olive", "white", "navy"],
        "sizes": [],
        "storage": [],
        "tags": ["womens", "handbag", "accessory"],
        "ptags": ["womens-fashion", "premium"],
        "features": ["Faux-leather body", "Multiple internal pockets", "Magnetic closure", "Detachable shoulder strap", "Gold-tone hardware"],
        "specs": ["Material: Vegan leather", "Closure: Zip", "Pockets: 3 internal", "Strap: Detachable"],
        "images": ["photo-1584917865442-de89df76afd3", "photo-1548036328-c9fa89d128fa", "photo-1590874103328-eac38a683ce7"],
        "hero": "photo-1584917865442-de89df76afd3",
    },

    # ============ KIDS ============
    "kids-clothing": {
        "count": 18,
        "name": "Kids' Clothing",
        "description": "Tees, dresses, sets, and ethnic wear for boys and girls.",
        "vertical": "apparel",
        "department": "Kids",
        "price_range": (299, 1999),
        "bases": ["Graphic Tee", "Cotton Frock", "Boys' Shirt", "Girls' Dress", "Kurta Set", "Track Set", "Romper", "Jumpsuit"],
        "adjectives": ["Soft", "Organic", "Cartoon-Print", "Stripey", "Festive", "Everyday"],
        "brands": ["Mothercare", "FirstCry", "Hopscotch", "MiniKlub", "United Colors of Benetton Kids", "H&M Kids"],
        "colors": ["pink", "blue", "yellow", "white", "green", "red"],
        "sizes": ["2-3Y", "4-5Y", "6-7Y", "8-9Y", "10-11Y"],
        "storage": [],
        "tags": ["kids", "clothing"],
        "ptags": ["kids-fashion", "everyday"],
        "features": ["100% organic cotton", "Tagless neck", "Snap closures", "Reinforced seams"],
        "specs": ["Material: 100% cotton", "Care: Machine wash gentle"],
        "images": ["photo-1622290291468-a28f7a7dc6a8", "photo-1503944583220-79d8926ad5e2", "photo-1503944583220-79d8926ad5e2"],
        "hero": "photo-1622290291468-a28f7a7dc6a8",
    },
    "kids-footwear": {
        "count": 10,
        "name": "Kids' Footwear",
        "description": "School shoes, sneakers, sandals, and party shoes.",
        "vertical": "apparel",
        "department": "Kids",
        "price_range": (399, 2499),
        "bases": ["School Shoe", "Velcro Sneaker", "Light-Up Sneaker", "Sandal", "Mary Jane", "Casual Shoe"],
        "adjectives": ["Soft-sole", "Lightweight", "Anti-skid"],
        "brands": ["Bata Kids", "Liberty Kids", "Action", "Sparx Kids", "Adidas Kids"],
        "colors": ["white", "black", "pink", "blue", "red"],
        "sizes": ["1", "2", "3", "4", "5", "6"],
        "storage": [],
        "tags": ["kids", "footwear"],
        "ptags": ["kids-fashion", "school"],
        "features": ["Anti-skid sole", "Velcro closure", "Padded collar", "Light-up heel"],
        "specs": ["Upper: Synthetic", "Sole: Rubber"],
        "images": ["photo-1505740106531-4243f3831c78", "photo-1581101767113-1677fc2b0c8e"],
        "hero": "photo-1505740106531-4243f3831c78",
    },

    # ============ JEWELLERY ============
    "jewellery-earrings": {
        "count": 18,
        "name": "Earrings",
        "description": "Studs, jhumkas, hoops, and chandbalis in gold-plated and silver.",
        "vertical": "general",
        "department": "Jewellery",
        "price_range": (299, 14999),
        "bases": ["Stud Earrings", "Jhumka Earrings", "Hoop Earrings", "Chandbali Earrings", "Drop Earrings", "Ear Cuff", "Tassel Earrings"],
        "adjectives": ["Pearl", "Kundan", "Polki", "Oxidised Silver", "Gold-Plated", "Diamond-Cut", "Temple"],
        "brands": ["Tanishq", "Mia by Tanishq", "CaratLane", "Pipa Bella", "Voylla", "Zaveri Pearls", "Anouk Jewellery"],
        "colors": ["gold", "rose-gold", "silver", "oxidised", "ivory"],
        "sizes": [],
        "storage": [],
        "tags": ["jewellery", "earrings", "ethnic", "festive"],
        "ptags": ["jewellery", "ethnic-wear", "festive"],
        "features": ["22kt gold plating", "Hypoallergenic posts", "Lightweight design", "Pearl drops", "Hand-set Kundan stones"],
        "specs": ["Plating: 22kt gold", "Material: Brass alloy", "Closure: Push-back", "Weight: 8g per pair"],
        "images": ["photo-1535632787350-4e68ef0ac584", "photo-1611591437281-460bfbe1220a", "photo-1605100804763-247f67b3557e"],
        "hero": "photo-1535632787350-4e68ef0ac584",
    },
    "jewellery-necklaces": {
        "count": 14,
        "name": "Necklaces",
        "description": "Pendants, chokers, ranihaars, and statement necklaces.",
        "vertical": "general",
        "department": "Jewellery",
        "price_range": (599, 24999),
        "bases": ["Pendant Necklace", "Choker", "Ranihaar", "Layered Necklace", "Pearl Necklace", "Long Chain Necklace"],
        "adjectives": ["Kundan", "Polki", "Pearl", "Diamond", "Temple"],
        "brands": ["Tanishq", "Mia by Tanishq", "CaratLane", "Pipa Bella", "Sukkhi", "Zaveri Pearls"],
        "colors": ["gold", "rose-gold", "silver", "oxidised"],
        "sizes": [],
        "storage": [],
        "tags": ["jewellery", "necklace", "ethnic", "festive"],
        "ptags": ["jewellery", "ethnic-wear", "festive"],
        "features": ["Hand-set stones", "Adjustable chain", "Hypoallergenic plating", "Lobster clasp"],
        "specs": ["Plating: 18kt gold", "Material: Brass alloy", "Length: Adjustable 16-22 inch"],
        "images": ["photo-1599643477877-530eb83abc8e", "photo-1611591437281-460bfbe1220a"],
        "hero": "photo-1599643477877-530eb83abc8e",
    },
    "jewellery-rings": {
        "count": 12,
        "name": "Rings",
        "description": "Solitaires, cocktail rings, bands, and engagement rings.",
        "vertical": "general",
        "department": "Jewellery",
        "price_range": (499, 39999),
        "bases": ["Solitaire Ring", "Cocktail Ring", "Band Ring", "Stackable Ring", "Engagement Ring"],
        "adjectives": ["Diamond", "Gold", "Rose Gold", "Platinum", "Statement"],
        "brands": ["Tanishq", "CaratLane", "Mia by Tanishq", "Pipa Bella", "Voylla"],
        "colors": ["gold", "rose-gold", "silver", "platinum"],
        "sizes": ["6", "7", "8", "9", "10", "11", "12", "13"],
        "storage": [],
        "tags": ["jewellery", "ring"],
        "ptags": ["jewellery", "premium"],
        "features": ["BIS-hallmarked", "Lab-grown diamond accent", "Comfort fit", "Rhodium polish"],
        "specs": ["Material: 14kt gold", "Diamond: 0.10ct, VS-clarity"],
        "images": ["photo-1605100804763-247f67b3557e", "photo-1535632787350-4e68ef0ac584"],
        "hero": "photo-1605100804763-247f67b3557e",
    },
    "jewellery-bangles": {
        "count": 12,
        "name": "Bangles & Bracelets",
        "description": "Kada, traditional bangles, charm bracelets, and cuffs.",
        "vertical": "general",
        "department": "Jewellery",
        "price_range": (399, 9999),
        "bases": ["Gold-Plated Bangles", "Kada", "Charm Bracelet", "Cuff Bracelet", "Polki Bangle Set"],
        "adjectives": ["Set of 4", "Set of 6", "Polki", "Kundan", "Ethnic"],
        "brands": ["Tanishq", "Voylla", "Pipa Bella", "Sukkhi", "Zaveri Pearls"],
        "colors": ["gold", "rose-gold", "silver"],
        "sizes": ["2.4", "2.6", "2.8"],
        "storage": [],
        "tags": ["jewellery", "bangle", "ethnic"],
        "ptags": ["jewellery", "ethnic-wear"],
        "features": ["Hand-set stones", "Light-weight construction", "Hypoallergenic plating"],
        "specs": ["Plating: 18kt gold", "Set of: 4 bangles"],
        "images": ["photo-1611591437281-460bfbe1220a", "photo-1599643477877-530eb83abc8e"],
        "hero": "photo-1611591437281-460bfbe1220a",
    },

    # ============ BEAUTY ============
    "beauty-skincare": {
        "count": 18,
        "name": "Skincare",
        "description": "Moisturisers, serums, sunscreens, and cleansers.",
        "vertical": "general",
        "department": "Beauty",
        "price_range": (199, 2999),
        "bases": ["Moisturiser", "Vitamin C Serum", "Niacinamide Serum", "Hyaluronic Acid Serum", "Sunscreen SPF 50", "Face Wash", "Toner", "Night Cream", "Eye Cream", "Face Mist"],
        "adjectives": ["Glow-Boosting", "Hydrating", "Brightening", "Anti-Aging", "Oil-Free", "Mineral"],
        "brands": ["Minimalist", "The Derma Co", "Plum", "Forest Essentials", "Mamaearth", "Lakmé", "Biotique"],
        "colors": ["clear"],
        "sizes": ["30ml", "50ml", "100ml", "200ml"],
        "storage": [],
        "tags": ["beauty", "skincare"],
        "ptags": ["beauty", "skincare", "self-care"],
        "features": ["Dermatologically tested", "Free of parabens & sulphates", "Vegan formula", "Cruelty-free"],
        "specs": ["Volume: 30ml", "Skin type: All", "Origin: India", "Shelf life: 24 months"],
        "images": ["photo-1556228720-195a672e8a03", "photo-1620916566398-39f1143ab7be", "photo-1612817288484-6f916006741a"],
        "hero": "photo-1556228720-195a672e8a03",
    },
    "beauty-makeup": {
        "count": 18,
        "name": "Makeup",
        "description": "Lipsticks, foundations, kajal, and palettes.",
        "vertical": "general",
        "department": "Beauty",
        "price_range": (149, 2499),
        "bases": ["Matte Lipstick", "Liquid Lipstick", "Foundation", "Compact Powder", "Kajal", "Eyeliner", "Mascara", "Eyeshadow Palette", "Blush", "Highlighter"],
        "adjectives": ["Long-lasting", "Waterproof", "Matte", "Glossy", "Hydrating"],
        "brands": ["Lakmé", "Maybelline", "Sugar Cosmetics", "Nykaa", "MAC", "Colorbar", "Faces Canada"],
        "colors": ["red", "nude", "pink", "berry", "coral", "mauve", "brown"],
        "sizes": [],
        "storage": [],
        "tags": ["beauty", "makeup"],
        "ptags": ["beauty", "makeup"],
        "features": ["12-hour wear", "Smudge-proof", "Lightweight feel", "Vitamin E enriched"],
        "specs": ["Finish: Matte", "Net weight: 3.5g"],
        "images": ["photo-1586495777744-4413f21062fa", "photo-1631214504543-30c47b13ab09", "photo-1522335789203-aaa306b9f4b1"],
        "hero": "photo-1586495777744-4413f21062fa",
    },
    "beauty-haircare": {
        "count": 12,
        "name": "Haircare",
        "description": "Shampoos, conditioners, oils, and treatments.",
        "vertical": "general",
        "department": "Beauty",
        "price_range": (149, 1999),
        "bases": ["Shampoo", "Conditioner", "Hair Oil", "Hair Mask", "Leave-In Serum", "Heat Protectant", "Dry Shampoo"],
        "adjectives": ["Argan", "Coconut", "Onion", "Keratin", "Anti-Hair Fall", "Nourishing"],
        "brands": ["WOW Skin Science", "L'Oréal Paris", "Mamaearth", "Bblunt", "Schwarzkopf", "Kérastase"],
        "colors": ["clear"],
        "sizes": ["100ml", "200ml", "400ml"],
        "storage": [],
        "tags": ["beauty", "haircare"],
        "ptags": ["beauty", "haircare"],
        "features": ["Sulfate-free", "Paraben-free", "Coconut-based"],
        "specs": ["Volume: 200ml", "Hair type: All"],
        "images": ["photo-1605497788044-5a32c7078486", "photo-1556228720-195a672e8a03"],
        "hero": "photo-1605497788044-5a32c7078486",
    },
    "beauty-fragrance": {
        "count": 10,
        "name": "Fragrances",
        "description": "Perfumes, deodorants, and body mists.",
        "vertical": "general",
        "department": "Beauty",
        "price_range": (299, 4999),
        "bases": ["Eau de Parfum", "Eau de Toilette", "Body Mist", "Deodorant", "Roll-On"],
        "adjectives": ["Floral", "Woody", "Citrus", "Oriental", "Fresh"],
        "brands": ["Bvlgari", "Calvin Klein", "Davidoff", "Engage", "Wild Stone", "Fogg", "Bella Vita"],
        "colors": ["clear"],
        "sizes": ["50ml", "100ml", "150ml"],
        "storage": [],
        "tags": ["beauty", "fragrance", "perfume"],
        "ptags": ["beauty", "self-care"],
        "features": ["Long-lasting fragrance", "Alcohol-free", "Travel-friendly"],
        "specs": ["Volume: 100ml", "Fragrance family: Floral"],
        "images": ["photo-1594035910387-fea47794261f", "photo-1541643600914-78b084683601"],
        "hero": "photo-1594035910387-fea47794261f",
    },

    # ============ WATCHES ============
    "watches": {
        "count": 18,
        "name": "Watches",
        "description": "Analog, digital, and chronograph watches.",
        "vertical": "general",
        "department": "Watches",
        "price_range": (799, 24999),
        "bases": ["Analog Watch", "Chronograph Watch", "Digital Watch", "Skeleton Watch", "Multifunction Watch", "Dress Watch"],
        "adjectives": ["Stainless Steel", "Leather Strap", "Gold-Tone", "Silver-Tone", "Sport"],
        "brands": ["Fastrack", "Titan", "Casio", "Fossil", "Timex", "Sonata", "Daniel Wellington", "Tommy Hilfiger Watches"],
        "colors": ["silver", "gold", "rose-gold", "black", "navy", "tan"],
        "sizes": [],
        "storage": [],
        "tags": ["watch", "accessory"],
        "ptags": ["accessory", "premium"],
        "features": ["Water-resistant 50m", "Quartz movement", "Mineral glass", "Stainless steel case", "Date window"],
        "specs": ["Movement: Quartz", "Case: 42mm stainless steel", "Strap: Genuine leather", "Water resistance: 5 ATM"],
        "images": ["photo-1523275335684-37898b6baf30", "photo-1622434641406-a158123450f9", "photo-1524805444758-089113d48a6d"],
        "hero": "photo-1523275335684-37898b6baf30",
    },

    # ============ ELECTRONICS ============
    "electronics-mobile": {
        "count": 18,
        "name": "Mobile Phones",
        "description": "Smartphones across budget to premium tiers.",
        "vertical": "electronics",
        "department": "Electronics",
        "price_range": (8999, 149999),
        "bases": ["Smartphone", "5G Smartphone", "Pro Smartphone", "Lite Smartphone", "Camera Smartphone"],
        "adjectives": ["Pro", "Plus", "Ultra", "Max", "Lite", "5G"],
        "brands": ["Samsung", "Apple", "OnePlus", "Xiaomi", "Realme", "Vivo", "OPPO", "Nothing", "Motorola"],
        "colors": ["midnight-black", "graphite", "silver", "blue", "green", "purple", "rose-gold"],
        "sizes": [],
        "storage": ["64GB", "128GB", "256GB", "512GB", "1TB"],
        "tags": ["electronics", "mobile", "smartphone"],
        "ptags": ["electronics", "tech", "premium"],
        "features": ["AMOLED display", "Triple camera setup", "5G connectivity", "Fast charging", "Stereo speakers", "IP68 rated"],
        "specs": ["Display: 6.5\" AMOLED", "Battery: 5000mAh", "RAM: 8GB", "Camera: 50MP triple", "OS: Android 14"],
        "images": ["photo-1511707171634-5f897ff02aa9", "photo-1592899677977-9c10ca588bbd", "photo-1567581935884-3349723552ca"],
        "hero": "photo-1511707171634-5f897ff02aa9",
    },
    "electronics-laptop": {
        "count": 14,
        "name": "Laptops",
        "description": "Ultrabooks, gaming laptops, and 2-in-1s.",
        "vertical": "electronics",
        "department": "Electronics",
        "price_range": (32999, 199999),
        "bases": ["Ultrabook", "Gaming Laptop", "Business Laptop", "2-in-1 Laptop", "Workstation"],
        "adjectives": ["Pro", "Air", "Slim", "Performance", "Studio"],
        "brands": ["Apple", "Dell", "HP", "Lenovo", "ASUS", "Acer", "MSI"],
        "colors": ["space-grey", "silver", "black", "white"],
        "sizes": [],
        "storage": ["256GB SSD", "512GB SSD", "1TB SSD", "2TB SSD"],
        "tags": ["electronics", "laptop", "computer"],
        "ptags": ["electronics", "tech", "premium", "work-from-home"],
        "features": ["Backlit keyboard", "Fingerprint reader", "Thunderbolt 4 ports", "Wi-Fi 6E", "All-day battery"],
        "specs": ["Display: 14\" IPS", "CPU: Intel Core i7", "RAM: 16GB", "Storage: 512GB SSD", "Weight: 1.4kg"],
        "images": ["photo-1496181133206-80ce9b88a853", "photo-1517336714731-489689fd1ca8", "photo-1593642632559-0c6d3fc62b89"],
        "hero": "photo-1496181133206-80ce9b88a853",
    },
    "electronics-audio": {
        "count": 18,
        "name": "Audio",
        "description": "Headphones, earbuds, speakers, and soundbars.",
        "vertical": "electronics",
        "department": "Electronics",
        "price_range": (799, 49999),
        "bases": ["Wireless Headphones", "ANC Headphones", "True Wireless Earbuds", "Bluetooth Speaker", "Soundbar", "Gaming Headset", "In-Ear Headphones"],
        "adjectives": ["Pro", "Studio", "Sport", "Lite", "Bass-Boost"],
        "brands": ["Sony", "Bose", "JBL", "boAt", "Apple", "Sennheiser", "Marshall", "Anker Soundcore", "OnePlus Audio"],
        "colors": ["black", "white", "blue", "red", "rose-gold"],
        "sizes": [],
        "storage": [],
        "tags": ["electronics", "audio", "headphones"],
        "ptags": ["electronics", "tech", "music"],
        "features": ["Active Noise Cancellation", "30-hour battery", "Bluetooth 5.3", "Touch controls", "Hi-Res audio certified"],
        "specs": ["Driver: 40mm dynamic", "Bluetooth: 5.3", "Battery: 30h", "Charging: USB-C", "Codec: AAC, aptX"],
        "images": ["photo-1505740420928-5e560c06d30e", "photo-1546435770-a3e426bf472b", "photo-1583394838336-acd977736f90"],
        "hero": "photo-1505740420928-5e560c06d30e",
    },
    "electronics-smartwatch": {
        "count": 12,
        "name": "Smartwatches",
        "description": "Fitness trackers, smartwatches, and hybrid watches.",
        "vertical": "electronics",
        "department": "Electronics",
        "price_range": (1999, 49999),
        "bases": ["Smartwatch", "Fitness Tracker", "Hybrid Watch", "GPS Watch", "Sport Watch"],
        "adjectives": ["Pro", "Active", "Sport", "Ultra"],
        "brands": ["Apple", "Samsung Galaxy Watch", "Fitbit", "Garmin", "Noise", "Boat", "Fastrack"],
        "colors": ["black", "silver", "rose-gold", "gold"],
        "sizes": [],
        "storage": [],
        "tags": ["electronics", "smartwatch", "fitness"],
        "ptags": ["electronics", "tech", "fitness"],
        "features": ["Heart-rate monitor", "SpO2 tracker", "GPS", "AMOLED display", "5 ATM water resistance", "100+ workout modes"],
        "specs": ["Display: 1.43\" AMOLED", "Battery: 7 days typical", "Compatibility: iOS + Android", "GPS: Built-in"],
        "images": ["photo-1508685096489-7aacd43bd3b1", "photo-1579586337278-3befd40fd17a"],
        "hero": "photo-1508685096489-7aacd43bd3b1",
    },
    "electronics-tv": {
        "count": 10,
        "name": "TVs & Displays",
        "description": "Smart TVs, OLED, and 4K displays.",
        "vertical": "electronics",
        "department": "Electronics",
        "price_range": (15999, 249999),
        "bases": ["43\" Smart TV", "55\" 4K TV", "65\" OLED TV", "32\" HD TV", "75\" QLED TV"],
        "adjectives": ["4K Ultra HD", "OLED", "QLED", "Smart"],
        "brands": ["Samsung", "Sony Bravia", "LG", "Mi", "OnePlus TV", "TCL"],
        "colors": ["black"],
        "sizes": [],
        "storage": [],
        "tags": ["electronics", "tv", "display"],
        "ptags": ["electronics", "home-entertainment"],
        "features": ["4K UHD", "HDR10+", "Dolby Vision", "Built-in Chromecast", "Voice remote", "Wall-mountable"],
        "specs": ["Resolution: 3840x2160", "Refresh rate: 60Hz", "HDMI: 3 ports", "OS: Google TV"],
        "images": ["photo-1593359677879-a4bb92f829d1", "photo-1601944179066-29b8f7e29c3d"],
        "hero": "photo-1593359677879-a4bb92f829d1",
    },
    "electronics-camera": {
        "count": 8,
        "name": "Cameras",
        "description": "Mirrorless, DSLR, and compact cameras.",
        "vertical": "electronics",
        "department": "Electronics",
        "price_range": (8999, 149999),
        "bases": ["Mirrorless Camera", "DSLR", "Compact Camera", "Action Camera", "Instant Camera"],
        "adjectives": ["Pro", "Vlog", "Travel"],
        "brands": ["Canon", "Sony", "Nikon", "Fujifilm", "GoPro"],
        "colors": ["black", "silver"],
        "sizes": [],
        "storage": [],
        "tags": ["electronics", "camera"],
        "ptags": ["electronics", "tech", "photography"],
        "features": ["24MP APS-C sensor", "4K video", "Built-in Wi-Fi", "Tilting touchscreen", "Dual SD slots"],
        "specs": ["Sensor: 24MP APS-C", "Video: 4K@60fps", "Mount: E-mount", "Stabilization: 5-axis"],
        "images": ["photo-1502920917128-1aa500764cbd", "photo-1606980625512-b7df3df7c8f7"],
        "hero": "photo-1502920917128-1aa500764cbd",
    },
    "electronics-accessories": {
        "count": 14,
        "name": "Tech Accessories",
        "description": "Cables, chargers, mounts, and power banks.",
        "vertical": "electronics",
        "department": "Electronics",
        "price_range": (199, 4999),
        "bases": ["Power Bank", "USB-C Cable", "Wireless Charger", "Phone Stand", "Webcam", "USB Hub", "Laptop Stand"],
        "adjectives": ["Compact", "Travel", "Premium", "Multi-port"],
        "brands": ["Anker", "Mi", "boAt", "Belkin", "Portronics", "Stuffcool"],
        "colors": ["black", "white", "silver"],
        "sizes": [],
        "storage": ["10000mAh", "20000mAh"],
        "tags": ["electronics", "accessory"],
        "ptags": ["electronics", "tech"],
        "features": ["20W fast charging", "Power Delivery support", "USB-C in/out", "LED indicator"],
        "specs": ["Capacity: 20000mAh", "Output: 22.5W max", "Ports: 1xUSB-A + 1xUSB-C"],
        "images": ["photo-1609091839311-d5365f9ff1c5", "photo-1583394838336-acd977736f90"],
        "hero": "photo-1609091839311-d5365f9ff1c5",
    },

    # ============ HOME ============
    "home-kitchen": {
        "count": 14,
        "name": "Kitchen Appliances",
        "description": "Mixers, pressure cookers, air fryers, and small appliances.",
        "vertical": "general",
        "department": "Kitchen",
        "price_range": (699, 19999),
        "bases": ["Mixer Grinder", "Pressure Cooker", "Air Fryer", "Induction Cooktop", "Electric Kettle", "Microwave Oven", "Hand Blender", "Toaster"],
        "adjectives": ["Pro", "Plus", "Smart"],
        "brands": ["Prestige", "Bajaj", "Philips", "Pigeon", "Hawkins", "Butterfly", "Crompton"],
        "colors": ["white", "black", "silver", "red"],
        "sizes": [],
        "storage": [],
        "tags": ["home", "kitchen", "appliance"],
        "ptags": ["home", "kitchen", "everyday"],
        "features": ["750W motor", "3 stainless-steel jars", "Overload protection", "2-year warranty", "ISI-marked"],
        "specs": ["Power: 750W", "Speed: 3 settings", "Warranty: 2 years"],
        "images": ["photo-1556909114-f6e7ad7d3136", "photo-1565183997392-2f6f122e5912"],
        "hero": "photo-1556909114-f6e7ad7d3136",
    },
    "home-decor": {
        "count": 10,
        "name": "Home Decor",
        "description": "Cushions, planters, wall art, and lighting.",
        "vertical": "furniture",
        "department": "Home Living",
        "price_range": (299, 7999),
        "bases": ["Cushion Cover Set", "Ceramic Planter", "Wall Clock", "Photo Frame", "Floor Lamp", "Table Lamp", "Wall Art Print"],
        "adjectives": ["Bohemian", "Minimalist", "Classic", "Mid-Century"],
        "brands": ["Pepperfry Home", "Urban Ladder", "FabIndia Home", "Home Centre", "Chumbak"],
        "colors": ["natural", "white", "black", "blue", "olive", "brass"],
        "sizes": [],
        "storage": [],
        "tags": ["home", "decor"],
        "ptags": ["home", "decor"],
        "features": ["Hand-crafted", "Sustainable materials", "Natural finish"],
        "specs": ["Material: Ceramic / cotton", "Care: Spot clean"],
        "images": ["photo-1567538096631-e0c55bd6374c", "photo-1493663284031-b7e3aefcae8e"],
        "hero": "photo-1567538096631-e0c55bd6374c",
    },
}


# Lightweight FE-friendly photo URL: stable Unsplash CDN with auto-format.
def _img(photo_id: str) -> str:
    return (
        f"https://images.unsplash.com/{photo_id}?auto=format&fit=crop&w=900&q=80"
    )


def _slugify(*parts: str) -> str:
    return "-".join(
        "".join(c for c in part.lower().replace(" ", "-") if c.isalnum() or c == "-")
        for part in parts
        if part
    ).strip("-")


def _round_price(low: int, high: int) -> int:
    """Pick a price in [low, high], rounded to a believable retail break (₹99/₹999)."""
    raw = RNG.randint(low, high)
    if raw < 1000:
        rounded = max(99, (raw // 50) * 50 - 1)  # …49 / …99
    elif raw < 10000:
        rounded = (raw // 100) * 100 - 1         # …99
    else:
        rounded = (raw // 500) * 500 - 1         # …499 / …999
    return max(rounded, low)


def _compare_at(price: int) -> int | None:
    """30% chance of having a strikethrough MRP between 10-25% above price."""
    if RNG.random() > 0.30:
        return None
    bump = RNG.uniform(0.10, 0.25)
    return int(round(price * (1 + bump) / 50)) * 50 - 1


def _option_id(label: str) -> str:
    return _slugify(label)


def _pick_image(cat_slug: str, idx: int, vertical: str) -> tuple[str, list[str]]:
    """Return (primary_url, [extra_urls]) — one unique image per product when
    the pool is large enough; with controlled, minimal duplication when the
    pool is smaller than the product count.

    Strategy:
      1. Try the category's verified pool first; round-robin so the first N
         products in a category get unique images, with the (N+i)th wrapping.
      2. If the category pool is empty, fall back to the vertical pool
         (other categories with the same `vertical`) so no product references
         a broken URL.
    """
    pool = VERIFIED_POOLS.get(cat_slug, [])
    if not pool:
        # Fallback to the vertical-level pool (any category sharing the same vertical).
        # Built lazily on first miss; cached on the function attribute.
        cache = getattr(_pick_image, "_vertical_cache", {})
        if vertical not in cache:
            from_categories = [
                ids for k, ids in VERIFIED_POOLS.items()
                if k in CATEGORIES and CATEGORIES[k]["vertical"] == vertical
            ]
            cache[vertical] = [pid for chunk in from_categories for pid in chunk]
            _pick_image._vertical_cache = cache  # type: ignore[attr-defined]
        pool = cache[vertical] or list({pid for ids in VERIFIED_POOLS.values() for pid in ids})

    primary_id = pool[idx % len(pool)]
    primary = _img(primary_id)
    # Extras — different from primary, drawn from same pool. 2 extras when pool is rich.
    extras_ids = [pool[(idx + j) % len(pool)] for j in (1, 2) if len(pool) > 1]
    extras = [_img(p) for p in extras_ids if p != primary_id]
    return primary, extras


def _generate_one(
    cat_slug: str,
    cat: dict,
    idx: int,
    image_offset: int,
) -> dict:
    base = RNG.choice(cat["bases"])
    adj = RNG.choice(cat["adjectives"]) if cat["adjectives"] else ""
    brand = RNG.choice(cat["brands"])

    # Name combinations: "{Brand} {Adj} {Base}" with occasional flavour words.
    name_parts = [brand, adj, base] if adj else [brand, base]
    name = " ".join(p for p in name_parts if p)

    slug = _slugify(brand, adj, base, str(idx + 1))

    price = _round_price(*cat["price_range"])
    compare_at = _compare_at(price)

    # Inventory: 70% in-stock, 20% low-stock, 10% backorder.
    inv_roll = RNG.random()
    inventory_status = "in-stock" if inv_roll < 0.70 else ("low-stock" if inv_roll < 0.90 else "backorder")

    # Rating distribution skewed high (typical e-comm).
    rating = round(RNG.uniform(3.8, 4.9), 1)
    review_count = RNG.choice([
        RNG.randint(8, 60), RNG.randint(60, 400), RNG.randint(400, 2500),
    ])

    primary, extra_imgs = _pick_image(cat_slug, idx, cat["vertical"])

    color_options = [
        {"id": _option_id(c), "label": c.replace("-", " ").title()}
        for c in RNG.sample(cat["colors"], k=min(len(cat["colors"]), RNG.randint(2, 5)))
    ] if cat["colors"] else []
    size_options = [
        {"id": _option_id(s), "label": s}
        for s in cat["sizes"]
    ] if cat["sizes"] else []
    storage_options = [
        {"id": _option_id(s), "label": s}
        for s in cat["storage"]
    ] if cat["storage"] else []

    features = RNG.sample(cat["features"], k=min(len(cat["features"]), RNG.randint(3, 5)))
    specification = RNG.sample(cat["specs"], k=min(len(cat["specs"]), RNG.randint(3, 6)))

    description = (
        f"{name} — {adj.lower() + ' ' if adj else ''}{base.lower()} from {brand}. "
        f"{features[0]} and {features[1].lower() if len(features) > 1 else 'thoughtfully made'}."
    )
    long_description = (
        f"The {name} is built around {base.lower()} essentials with a focus on "
        f"{features[0].lower()}. {brand} adds craft details: "
        f"{', '.join(f.lower() for f in features[1:])}. "
        f"A go-to for {cat['ptags'][0].replace('-', ' ')} "
        f"shoppers in India."
    )

    badges = []
    if compare_at:
        pct = round((compare_at - price) / compare_at * 100)
        badges.append(f"{pct}% off")
    if inventory_status == "low-stock":
        badges.append("Low stock")
    if rating >= 4.6 and review_count >= 100:
        badges.append("Highly rated")
    if RNG.random() < 0.20:
        badges.append("Bestseller")
    if RNG.random() < 0.15:
        badges.append("New")

    free_delivery = RNG.random() < 0.65

    out: dict = {
        "id": f"prod-{cat_slug}-{idx + 1:03d}",
        "slug": slug,
        "name": name,
        "brand": brand,
        "category": cat_slug,
        "price": price,
        "rating": rating,
        "reviewCount": review_count,
        "image": primary,
        "description": description,
        "features": features,
        "badges": badges,
        "inventoryStatus": inventory_status,
        "personalizationTags": cat["ptags"],
        "vertical": cat["vertical"],
        "freeDelivery": free_delivery,
        "department": cat["department"],
        "tags": cat["tags"] + [base.lower().replace(" ", "-")],
        "specification": specification,
        "longDescription": long_description,
        "images": [primary] + [i for i in extra_imgs if i != primary][:2],
    }
    if compare_at:
        out["compareAt"] = compare_at
    if color_options:
        out["colorOptions"] = color_options
    if size_options:
        out["sizeOptions"] = size_options
    if storage_options:
        out["storageOptions"] = storage_options
    return out


def main() -> None:
    # IMPORTANT: only preserve the 13 *hand-curated* legacy products (ids
    # like prod-1 .. prod-13). Anything else came from a previous generator
    # run and would otherwise stick around in the dedup step, freezing old
    # images on disk forever even when the pool changes.
    raw_existing = json.loads((SEED_DIR / "products.seed.json").read_text())
    legacy_products = [p for p in raw_existing if not p.get("id", "").startswith("prod-") or p.get("id", "")[5:].isdigit()]
    raw_existing_cats = json.loads((SEED_DIR / "categories.seed.json").read_text())
    legacy_categories = [c for c in raw_existing_cats if not c.get("id", "").startswith("cat-") or c["slug"] in {"trail-running", "city-commute", "studio-recovery", "home-living", "tech-desk"}]

    new_products: list[dict] = []
    new_categories: list[dict] = []
    for cat_idx, (cat_slug, cat) in enumerate(CATEGORIES.items()):
        new_categories.append({
            "id": f"cat-{cat_slug}",
            "slug": cat_slug,
            "name": cat["name"],
            "description": cat["description"],
            "hero": _img(cat["hero"]),
        })
        for i in range(cat["count"]):
            new_products.append(_generate_one(cat_slug, cat, i, image_offset=cat_idx))

    # Preserve the 13 legacy products + 5 legacy categories at the front so
    # FK refs from existing customer events / cart / wishlist rows stay valid.
    all_products = legacy_products + new_products
    all_categories = legacy_categories + new_categories

    # Idempotency: dedupe by slug, keep the first (legacy) occurrence.
    seen_p: set[str] = set()
    deduped_products: list[dict] = []
    for p in all_products:
        if p["slug"] in seen_p:
            continue
        seen_p.add(p["slug"])
        deduped_products.append(p)

    seen_c: set[str] = set()
    deduped_categories: list[dict] = []
    for c in all_categories:
        if c["slug"] in seen_c:
            continue
        seen_c.add(c["slug"])
        deduped_categories.append(c)

    (SEED_DIR / "products.seed.json").write_text(json.dumps(deduped_products, indent=2))
    (SEED_DIR / "categories.seed.json").write_text(json.dumps(deduped_categories, indent=2))

    print(f"wrote {len(deduped_products)} products to {SEED_DIR / 'products.seed.json'}")
    print(f"wrote {len(deduped_categories)} categories to {SEED_DIR / 'categories.seed.json'}")
    # Distribution sanity check.
    from collections import Counter
    by_cat = Counter(p["category"] for p in deduped_products)
    by_vert = Counter(p["vertical"] for p in deduped_products if p.get("vertical"))
    by_dept = Counter(p["department"] for p in deduped_products if p.get("department"))
    print("\nproducts per category:")
    for slug, n in sorted(by_cat.items(), key=lambda x: -x[1]):
        print(f"  {slug:30s} {n}")
    print("\nproducts per vertical:")
    for v, n in sorted(by_vert.items(), key=lambda x: -x[1]):
        print(f"  {v:15s} {n}")
    print("\nproducts per department:")
    for d, n in sorted(by_dept.items(), key=lambda x: -x[1]):
        print(f"  {d:15s} {n}")


if __name__ == "__main__":
    main()
