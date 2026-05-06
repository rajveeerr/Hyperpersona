"""Seed the product_catalog table with a hand-crafted starter catalog.

(Distinct from `seed_products.py` which seeds the storefront `products`
table + product-catalog OpenSearch index for the M1 catalog endpoints.)

40 products across two complementary themes (tech + outdoor) so the
demo can show recommendations that span categories sensibly:
  - laptop in cart       -> bag, mouse, monitor (tech complements)
  - hiking boots in cart -> backpack, socks, water bottle (outdoor)
  - mixed cart           -> diverse complements

Each product has a short description that becomes part of the prompt
when the LLM picks complements.

Idempotent: re-running overwrites the same rows.

Prices are in INR.

Usage: make seed-recommender-catalog
"""

import os

from shared.dynamo import DynamoClient

ENDPOINT = os.getenv("DYNAMODB_ENDPOINT", "http://localhost:8001")
REGION = os.getenv("AWS_REGION", "us-east-1")


PRODUCTS: list[dict] = [
    # --- Laptops ---------------------------------------------------------
    {"product_id": "laptop_dell_xps_15", "name": "Dell XPS 15 Laptop",
     "category": "Electronics", "subcategory": "Laptops", "price": 149317.00,
     "description": "15.6\" 4K OLED, Intel i7, 16GB RAM, 1TB SSD. High-end ultraportable for creators."},
    {"product_id": "laptop_macbook_pro_14", "name": "MacBook Pro 14\"",
     "category": "Electronics", "subcategory": "Laptops", "price": 165917.00,
     "description": "14.2\" Liquid Retina XDR, M3 Pro chip, 18GB unified memory. Apple silicon performance laptop."},
    {"product_id": "laptop_thinkpad_x1", "name": "ThinkPad X1 Carbon",
     "category": "Electronics", "subcategory": "Laptops", "price": 132717.00,
     "description": "14\" business laptop, Intel i7, 16GB RAM, military-grade durability."},
    {"product_id": "laptop_surface_4", "name": "Surface Laptop 4",
     "category": "Electronics", "subcategory": "Laptops", "price": 107817.00,
     "description": "13.5\" touchscreen, AMD Ryzen 5, 8GB RAM. Lightweight Windows ultrabook."},

    # --- Laptop bags & cases --------------------------------------------
    {"product_id": "bag_leather_brief", "name": "Leather Laptop Brief 15\"",
     "category": "Accessories", "subcategory": "Laptop Bags", "price": 12367.00,
     "description": "Full-grain leather briefcase, fits 15\" laptops. Premium executive style."},
    {"product_id": "bag_canvas_sleeve", "name": "Canvas Laptop Sleeve 15\"",
     "category": "Accessories", "subcategory": "Laptop Bags", "price": 3237.00,
     "description": "Padded canvas sleeve with felt lining. Lightweight protection for daily commute."},
    {"product_id": "bag_hardshell_case", "name": "Hard Shell Travel Case",
     "category": "Accessories", "subcategory": "Laptop Bags", "price": 7387.00,
     "description": "Rugged polycarbonate shell, foam interior. Travel protection for laptops up to 16\"."},
    {"product_id": "bag_tech_backpack", "name": "Tech Backpack 25L",
     "category": "Accessories", "subcategory": "Backpacks", "price": 10707.00,
     "description": "Padded laptop sleeve, USB charging pass-through, water-resistant. 25L commuter backpack."},
    {"product_id": "bag_messenger_canvas", "name": "Waxed Canvas Messenger Bag",
     "category": "Accessories", "subcategory": "Laptop Bags", "price": 9047.00,
     "description": "Waxed canvas with leather trim. Crossbody messenger fits a 15\" laptop."},

    # --- Mice ------------------------------------------------------------
    {"product_id": "mouse_logi_mx_master", "name": "Logitech MX Master 3S",
     "category": "Electronics", "subcategory": "Mice", "price": 8217.00,
     "description": "Wireless ergonomic mouse, 8K DPI, multi-device. Productivity standard."},
    {"product_id": "mouse_apple_magic", "name": "Apple Magic Mouse",
     "category": "Electronics", "subcategory": "Mice", "price": 6557.00,
     "description": "Multi-touch surface, rechargeable. Pairs natively with Mac."},
    {"product_id": "mouse_razer_gaming", "name": "Razer DeathAdder V3 Gaming Mouse",
     "category": "Electronics", "subcategory": "Mice", "price": 5727.00,
     "description": "30K DPI optical sensor, 90M click switches. Esports-grade gaming mouse."},
    {"product_id": "mouse_logi_lift_vertical", "name": "Logitech Lift Vertical Mouse",
     "category": "Electronics", "subcategory": "Mice", "price": 4897.00,
     "description": "57-degree vertical design. Reduces wrist strain on long workdays."},

    # --- Keyboards -------------------------------------------------------
    {"product_id": "keyboard_keychron_k8", "name": "Keychron K8 Mechanical Keyboard",
     "category": "Electronics", "subcategory": "Keyboards", "price": 9047.00,
     "description": "Wireless mechanical keyboard, hot-swappable switches, Mac/Windows compatible."},
    {"product_id": "keyboard_apple_magic", "name": "Apple Magic Keyboard",
     "category": "Electronics", "subcategory": "Keyboards", "price": 8217.00,
     "description": "Slim aluminum keyboard, scissor switches. Designed for Mac."},
    {"product_id": "keyboard_logi_ergo", "name": "Logitech Ergo K860 Split Keyboard",
     "category": "Electronics", "subcategory": "Keyboards", "price": 10707.00,
     "description": "Curved split design, palm rest. Reduces wrist tension for long typing sessions."},

    # --- Monitors --------------------------------------------------------
    {"product_id": "monitor_4k_27", "name": "27\" 4K Monitor",
     "category": "Electronics", "subcategory": "Monitors", "price": 28967.00,
     "description": "27-inch 4K IPS panel, USB-C with 65W power delivery. Single-cable laptop dock."},
    {"product_id": "monitor_ultrawide_34", "name": "34\" Ultrawide Curved Monitor",
     "category": "Electronics", "subcategory": "Monitors", "price": 41417.00,
     "description": "34-inch curved ultrawide, 3440x1440. Immersive multitasking display."},

    # --- Hubs / cables / chargers ---------------------------------------
    {"product_id": "hub_usbc_8in1", "name": "USB-C 8-in-1 Hub",
     "category": "Electronics", "subcategory": "Cables", "price": 6557.00,
     "description": "8 ports incl HDMI, ethernet, SD/microSD, 100W passthrough. Travel-ready hub."},
    {"product_id": "dock_thunderbolt", "name": "Thunderbolt 4 Dock",
     "category": "Electronics", "subcategory": "Cables", "price": 20667.00,
     "description": "Dual 4K display support, 96W charging, 11 ports. Desktop docking station."},
    {"product_id": "charger_usbc_65w", "name": "65W USB-C GaN Charger",
     "category": "Electronics", "subcategory": "Cables", "price": 3237.00,
     "description": "Compact GaN charger, single USB-C port. Powers most laptops."},

    # --- Audio -----------------------------------------------------------
    {"product_id": "headphones_sony_xm5", "name": "Sony WH-1000XM5",
     "category": "Electronics", "subcategory": "Audio", "price": 28967.00,
     "description": "Industry-leading noise cancellation, 30hr battery. Premium over-ear headphones."},
    {"product_id": "earbuds_apple_airpods_pro", "name": "AirPods Pro (2nd gen)",
     "category": "Electronics", "subcategory": "Audio", "price": 20667.00,
     "description": "Active noise cancellation, transparency mode. Ear-tips fit test included."},

    # --- Webcam / privacy -----------------------------------------------
    {"product_id": "webcam_logi_1080p", "name": "Logitech C920 1080p Webcam",
     "category": "Electronics", "subcategory": "Accessories", "price": 5727.00,
     "description": "1080p HD webcam, autofocus, stereo mics. Standard remote-work webcam."},

    # --- Hiking boots ---------------------------------------------------
    {"product_id": "boots_salomon_x_ultra", "name": "Salomon X Ultra 4 GTX",
     "category": "Outdoor", "subcategory": "Hiking Boots", "price": 14027.00,
     "description": "Gore-Tex waterproof, Contagrip MA outsole. All-day trail performance hiker."},
    {"product_id": "boots_merrell_moab", "name": "Merrell Moab 3 Mid",
     "category": "Outdoor", "subcategory": "Hiking Boots", "price": 10707.00,
     "description": "Mid-cut hiker, breathable mesh, Vibram outsole. Most popular trail boot."},
    {"product_id": "boots_lasportiva_tx4", "name": "La Sportiva TX4 Approach",
     "category": "Outdoor", "subcategory": "Hiking Boots", "price": 15687.00,
     "description": "Approach shoe, sticky climbing rubber. Bridges hiking and light climbing."},
    {"product_id": "boots_keen_targhee", "name": "KEEN Targhee III Mid",
     "category": "Outdoor", "subcategory": "Hiking Boots", "price": 12035.00,
     "description": "Waterproof leather, roomy toe box. Popular wider-foot hiker."},

    # --- Backpacks (outdoor) --------------------------------------------
    {"product_id": "backpack_osprey_30", "name": "Osprey Talon 30L Day Pack",
     "category": "Outdoor", "subcategory": "Backpacks", "price": 14027.00,
     "description": "Versatile 30L day pack, AirScape suspension. All-day comfort for hikes."},
    {"product_id": "backpack_deuter_50", "name": "Deuter Aircontact 50L",
     "category": "Outdoor", "subcategory": "Backpacks", "price": 19837.00,
     "description": "50L weekend pack, Aircontact back system. Multi-day backpacking."},
    {"product_id": "backpack_camelbak_hydration", "name": "Camelbak Octane 12L Hydration Vest",
     "category": "Outdoor", "subcategory": "Backpacks", "price": 10707.00,
     "description": "Trail running vest with 2L reservoir. Hands-free hydration for long runs."},

    # --- Socks ----------------------------------------------------------
    {"product_id": "socks_smartwool_hike", "name": "Smartwool Hike Wool Socks",
     "category": "Outdoor", "subcategory": "Apparel", "price": 1992.00,
     "description": "Merino wool blend, light cushioning. Moisture-wicking trail socks."},
    {"product_id": "socks_darn_tough", "name": "Darn Tough Hiker Crew",
     "category": "Outdoor", "subcategory": "Apparel", "price": 2158.00,
     "description": "Lifetime-guaranteed merino wool. Cult favorite hiking sock."},

    # --- Water bottles --------------------------------------------------
    {"product_id": "bottle_hydroflask_32", "name": "Hydro Flask 32oz Insulated Bottle",
     "category": "Outdoor", "subcategory": "Hydration", "price": 4150.00,
     "description": "Vacuum-insulated stainless steel. Cold for 24hrs, hot for 12hrs."},
    {"product_id": "bottle_platypus_collapsible", "name": "Platypus Collapsible Bottle 1L",
     "category": "Outdoor", "subcategory": "Hydration", "price": 1245.00,
     "description": "Collapsible BPA-free bottle. Packs flat when empty."},

    # --- Trekking gear --------------------------------------------------
    {"product_id": "poles_blackdiamond", "name": "Black Diamond Trail Trekking Poles",
     "category": "Outdoor", "subcategory": "Gear", "price": 10790.00,
     "description": "3-section adjustable aluminum poles. Reduce knee impact on descents."},
    {"product_id": "jacket_arcteryx_rain", "name": "Arc'teryx Beta LT Rain Jacket",
     "category": "Outdoor", "subcategory": "Apparel", "price": 33117.00,
     "description": "Gore-Tex 3-layer shell, packable. Premium hardshell rain jacket."},
    {"product_id": "headlamp_petzl_actik", "name": "Petzl Actik Core Headlamp",
     "category": "Outdoor", "subcategory": "Gear", "price": 5810.00,
     "description": "450 lumen rechargeable headlamp, red-light mode. Trail-running staple."},
    {"product_id": "multitool_leatherman_wave", "name": "Leatherman Wave+ Multi-tool",
     "category": "Outdoor", "subcategory": "Gear", "price": 9047.00,
     "description": "18 tools incl pliers, knife, saw. Made-in-USA pocket workshop."},
    {"product_id": "firstaid_adventure_kit", "name": "Adventure Medical First Aid Kit",
     "category": "Outdoor", "subcategory": "Gear", "price": 2905.00,
     "description": "Compact first-aid kit for 1-4 people, 1-4 days. Hiking essential."},
]


def main() -> None:
    dynamo = DynamoClient(endpoint=ENDPOINT, region=REGION)
    print(f"endpoint: {ENDPOINT}")
    print(f"seeding {len(PRODUCTS)} products into product_catalog ...")
    dynamo.batch_put_recommender_products(PRODUCTS)

    # Sanity-check by counting
    items = dynamo.scan_recommender_products()
    print(f"product_catalog now has {len(items)} items")

    # Print breakdown by category
    by_cat: dict[str, int] = {}
    for p in items:
        cat = p.get("subcategory", "?")
        by_cat[cat] = by_cat.get(cat, 0) + 1
    for cat, n in sorted(by_cat.items()):
        print(f"  {cat:20} {n}")


if __name__ == "__main__":
    main()
