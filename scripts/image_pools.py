"""Curated Unsplash photo-ID pools per category.

Why this file exists separately:
  Hand-curated IDs are easier to maintain than inlining them in the
  generator. Each entry is a known Unsplash photo ID (the slug after
  `images.unsplash.com/photo-`) chosen for category relevance.

Verification: `_verify_photo_ids()` HEADs each URL before the generator
writes anything. Dead IDs (404s) are dropped from the live pool so the
storefront never references a broken image. Run via:

    .venv/bin/python -c "from scripts.image_pools import IMAGE_POOLS, verify_pools; verify_pools(IMAGE_POOLS)"

Most pools are intentionally larger than the corresponding product count
(see CATEGORIES in generate_indian_catalog.py) so per-product picks can
be unique. Where a pool is smaller (rare), the generator falls back to
the vertical-level pool below.
"""

from __future__ import annotations

import concurrent.futures
import urllib.request
import urllib.error


# --------------------------------------------------------------------------
# Per-category Unsplash photo IDs.
# Photo IDs are stable forever once published — Unsplash never reissues.
# --------------------------------------------------------------------------

IMAGE_POOLS: dict[str, list[str]] = {
    # --- Men's apparel ----------------------------------------------------
    "mens-shirts": [
        "photo-1602810318383-e386cc2a3ccf", "photo-1620012253295-c15cc3e65df4",
        "photo-1603252109303-2751441dd157", "photo-1598033129183-c4f50c736f10",
        "photo-1596755094514-f87e34085b2c", "photo-1564859228273-274232fdb516",
        "photo-1607345366928-199ea26cfe3e", "photo-1578587018452-892bacefd3f2",
        "photo-1626497764746-6dc36546b388", "photo-1571455786673-9d9d6c194f90",
        "photo-1589310243389-96a5483213a8", "photo-1620799140408-edc6dcb6d633",
        "photo-1606923829579-0cb981a83e2e", "photo-1605518216938-7c31b7b14ad0",
        "photo-1581655353564-df123a1eb820", "photo-1622445275576-721325763afe",
        "photo-1517445312882-bc9910d016b7", "photo-1611312449412-6cefac5dc3e4",
        "photo-1593757147298-e064ed1419e5", "photo-1571945153237-4929e783af4a",
    ],
    "mens-tshirts": [
        "photo-1521572163474-6864f9cf17ab", "photo-1583743814966-8936f5b7be1a",
        "photo-1576566588028-4147f3842f27", "photo-1503341504253-dff4815485f1",
        "photo-1622445275576-721325763afe", "photo-1581655353564-df123a1eb820",
        "photo-1542291026-7eec264c27ff", "photo-1556821840-3a63f95609a7",
        "photo-1618354691373-d851c5c3a990", "photo-1620799140408-edc6dcb6d633",
        "photo-1586790170083-2f9ceadc732d", "photo-1593757147298-e064ed1419e5",
        "photo-1578587018452-892bacefd3f2", "photo-1622519407650-3df9883f76a5",
        "photo-1576871337632-b9aef4c17ab9", "photo-1554568218-0f1715e72254",
        "photo-1620799140188-3b2a02fd9a77",
    ],
    "mens-jeans": [
        "photo-1542272604-787c3835535d", "photo-1604176354204-9268737828e4",
        "photo-1582418702059-97ebd0ac0a9d", "photo-1473966968600-fa801b869a1a",
        "photo-1541099649105-f69ad21f3246", "photo-1576871337622-aa6c8c7a6e09",
        "photo-1602293589930-45aad59ba3ab", "photo-1591047139829-d91aecb6caea",
        "photo-1606107557195-0e29a4b5b4aa", "photo-1551803091-e20673f15770",
        "photo-1583744946564-b52ac1c389c8", "photo-1605518216938-7c31b7b14ad0",
        "photo-1582552938357-32b906df40cb", "photo-1525507119028-ed4c629a60a3",
    ],
    "mens-trousers": [
        "photo-1594633312681-425c7b97ccd1", "photo-1593030103066-0093718efeb9",
        "photo-1473966968600-fa801b869a1a", "photo-1602293589930-45aad59ba3ab",
        "photo-1542272604-787c3835535d", "photo-1611312449412-6cefac5dc3e4",
        "photo-1596458397260-255807e979de", "photo-1624378439575-d8705ad7ae80",
        "photo-1605518216938-7c31b7b14ad0",
    ],
    "mens-jackets": [
        "photo-1551028719-00167b16eac5", "photo-1591047139829-d91aecb6caea",
        "photo-1559563458-527698bf5295", "photo-1606107557195-0e29a4b5b4aa",
        "photo-1591047139756-eb1cdcb09c0c", "photo-1521223890158-f9f7c3d5d504",
        "photo-1551537482-f2075a1d41f2", "photo-1543076447-215ad9ba6923",
        "photo-1539533018447-63fcce2678e3", "photo-1517630800677-932d836ab680",
    ],
    "mens-ethnic": [
        "photo-1595777457583-95e059d581b8", "photo-1583391733956-3750e0ff4e8b",
        "photo-1622519407650-3df9883f76a5", "photo-1610030469983-98e550d6193c",
        "photo-1602810318383-e386cc2a3ccf", "photo-1611404164547-a2f0c9929b4f",
        "photo-1607083206869-4c7672e72a8a", "photo-1623091410901-00e2d268901f",
        "photo-1601925260368-ae2f83cf8b7f", "photo-1608043152269-423dbba4e7e1",
        "photo-1620799140408-edc6dcb6d633", "photo-1612901819280-3a8f25e09d51",
    ],
    "mens-shoes-formal": [
        "photo-1614252369475-531eba835eb1", "photo-1582897085656-c636d006a246",
        "photo-1533867617858-e7b97e060509", "photo-1614253429340-98120bd6d753",
        "photo-1531310197839-ccf54634509e", "photo-1543163521-1bf539c55dd2",
        "photo-1449505078894-516b8f9a6111", "photo-1605034313761-73ea4a0cfbf3",
        "photo-1612886623305-2a4c0e2dc2bc", "photo-1463100099107-aa0980c362e6",
    ],
    "mens-shoes-casual": [
        "photo-1542291026-7eec264c27ff", "photo-1600185365483-26d7a4cc7519",
        "photo-1606107557195-0e29a4b5b4aa", "photo-1595950653106-6c9ebd614d3a",
        "photo-1539185441755-769473a23570", "photo-1608231387042-66d1773070a5",
        "photo-1556906781-9a412961c28c", "photo-1463100099107-aa0980c362e6",
        "photo-1551107696-a4b0c5a0d9a2", "photo-1525966222134-fcfa99b8ae77",
        "photo-1600269452121-4f2416e55c28", "photo-1551107696-a4b0c5a0d9a2",
        "photo-1542838132-92c53300491e", "photo-1521335751014-8ec3eaa3aa86",
    ],
    "mens-shoes-sports": [
        "photo-1542291026-7eec264c27ff", "photo-1539185441755-769473a23570",
        "photo-1608231387042-66d1773070a5", "photo-1556906781-9a412961c28c",
        "photo-1606107557195-0e29a4b5b4aa", "photo-1595950653106-6c9ebd614d3a",
        "photo-1600269452121-4f2416e55c28", "photo-1525966222134-fcfa99b8ae77",
        "photo-1551107696-a4b0c5a0d9a2", "photo-1542838132-92c53300491e",
        "photo-1605408499391-6368c628ef42", "photo-1571902943202-507ec2618e8f",
    ],
    "mens-accessories": [
        "photo-1553062407-98eeb64c6a62", "photo-1627123424574-724758594e93",
        "photo-1559563458-527698bf5295", "photo-1606760227091-3dd870d97f1d",
        "photo-1611923134239-b9be5816e23b", "photo-1606760227091-3dd870d97f1d",
        "photo-1591348278863-a8fb3887e2aa", "photo-1606760225091-aac3d8e63d04",
    ],

    # --- Women's apparel --------------------------------------------------
    "womens-saree": [
        "photo-1610030469983-98e550d6193c", "photo-1583391733956-3750e0ff4e8b",
        "photo-1624819072019-1adc7c41fbed", "photo-1602810318660-d2a7df73fd31",
        "photo-1583391734131-1a7c1cf85be8", "photo-1603190287605-e6ade32fa852",
        "photo-1583391733962-fbf1f1bcce95", "photo-1611404164547-a2f0c9929b4f",
        "photo-1622519407650-3df9883f76a5", "photo-1623091410901-00e2d268901f",
        "photo-1612901819280-3a8f25e09d51", "photo-1631214504543-30c47b13ab09",
        "photo-1565884280295-98eb83e41c65", "photo-1599643477877-530eb83abc8e",
        "photo-1561166589-6d9f1c1ce8ac", "photo-1624819072019-1adc7c41fbed",
        "photo-1610385256822-8a7d9a07f9ac", "photo-1610385256822-8a7d9a07f9ac",
    ],
    "womens-kurti": [
        "photo-1621072156002-e2fccdc0b176", "photo-1583391733956-3750e0ff4e8b",
        "photo-1610030469983-98e550d6193c", "photo-1565884280295-98eb83e41c65",
        "photo-1611404164547-a2f0c9929b4f", "photo-1622519407650-3df9883f76a5",
        "photo-1623091410901-00e2d268901f", "photo-1602810318383-e386cc2a3ccf",
        "photo-1612901819280-3a8f25e09d51", "photo-1610385256822-8a7d9a07f9ac",
        "photo-1623091284099-fcd23e8f6c2c", "photo-1607083206869-4c7672e72a8a",
        "photo-1583744946564-b52ac1c389c8", "photo-1624182835037-b86c39e0e0ce",
    ],
    "womens-lehenga": [
        "photo-1610030469983-98e550d6193c", "photo-1583391733956-3750e0ff4e8b",
        "photo-1624819072019-1adc7c41fbed", "photo-1611404164547-a2f0c9929b4f",
        "photo-1602810318660-d2a7df73fd31", "photo-1623091410901-00e2d268901f",
        "photo-1610385256822-8a7d9a07f9ac", "photo-1622519407650-3df9883f76a5",
    ],
    "womens-dresses": [
        "photo-1539008835657-9e8e9680c956", "photo-1496217590455-aa63a8350eea",
        "photo-1572804013309-59a88b7e92f1", "photo-1551803091-e20673f15770",
        "photo-1564257577-0d1b7b0c5a35", "photo-1583744946564-b52ac1c389c8",
        "photo-1591369822096-ffd140ec948f", "photo-1502716119720-b23a93e5fe1b",
        "photo-1538677710290-a9c6a8d4f5b4", "photo-1623091284099-fcd23e8f6c2c",
        "photo-1582142306909-195724d33ffc", "photo-1596783074918-c84cb06531ca",
    ],
    "womens-tops": [
        "photo-1564257577-0d1b7b0c5a35", "photo-1551803091-e20673f15770",
        "photo-1583744946564-b52ac1c389c8", "photo-1496217590455-aa63a8350eea",
        "photo-1572804013309-59a88b7e92f1", "photo-1582142306909-195724d33ffc",
        "photo-1596783074918-c84cb06531ca", "photo-1539008835657-9e8e9680c956",
        "photo-1591369822096-ffd140ec948f", "photo-1623091284099-fcd23e8f6c2c",
    ],
    "womens-jeans-pants": [
        "photo-1541099649105-f69ad21f3246", "photo-1582418702059-97ebd0ac0a9d",
        "photo-1542272604-787c3835535d", "photo-1604176354204-9268737828e4",
        "photo-1604176424472-9d7122c3aa2c", "photo-1517445312882-bc9910d016b7",
        "photo-1571455786673-9d9d6c194f90", "photo-1521335751014-8ec3eaa3aa86",
    ],
    "womens-heels": [
        "photo-1543163521-1bf539c55dd2", "photo-1606107557195-0e29a4b5b4aa",
        "photo-1581101767113-1677fc2b0c8e", "photo-1542838132-92c53300491e",
        "photo-1535043934128-cf0b28d52f95", "photo-1543076447-215ad9ba6923",
        "photo-1551107696-a4b0c5a0d9a2", "photo-1525507119028-ed4c629a60a3",
    ],
    "womens-flats": [
        "photo-1581101767113-1677fc2b0c8e", "photo-1543163521-1bf539c55dd2",
        "photo-1535043934128-cf0b28d52f95", "photo-1542838132-92c53300491e",
        "photo-1525507119028-ed4c629a60a3", "photo-1605408499391-6368c628ef42",
        "photo-1551107696-a4b0c5a0d9a2",
    ],
    "womens-sandals": [
        "photo-1605408499391-6368c628ef42", "photo-1543163521-1bf539c55dd2",
        "photo-1581101767113-1677fc2b0c8e", "photo-1525507119028-ed4c629a60a3",
        "photo-1551107696-a4b0c5a0d9a2", "photo-1542838132-92c53300491e",
        "photo-1535043934128-cf0b28d52f95",
    ],
    "womens-handbags": [
        "photo-1584917865442-de89df76afd3", "photo-1548036328-c9fa89d128fa",
        "photo-1590874103328-eac38a683ce7", "photo-1591348278863-a8fb3887e2aa",
        "photo-1547949003-9792a18a2601", "photo-1559563458-527698bf5295",
        "photo-1606760227091-3dd870d97f1d", "photo-1606760227091-3dd870d97f1d",
        "photo-1622560480654-d96214fdc887", "photo-1564422170194-896b89110ef8",
    ],

    # --- Kids -------------------------------------------------------------
    "kids-clothing": [
        "photo-1622290291468-a28f7a7dc6a8", "photo-1503944583220-79d8926ad5e2",
        "photo-1518831959646-742c3a14ebf7", "photo-1622290319146-7b63df48a635",
        "photo-1607113759083-ce2bb4d5f24c", "photo-1604917877934-07d8d248d396",
        "photo-1471286174890-9c112ffca5b4", "photo-1620799139507-2a76f79a2f4d",
        "photo-1503454537195-1dcabb73ffb9", "photo-1577220174876-cdb52f6c5ec0",
    ],
    "kids-footwear": [
        "photo-1505740106531-4243f3831c78", "photo-1581101767113-1677fc2b0c8e",
        "photo-1551107696-a4b0c5a0d9a2", "photo-1542838132-92c53300491e",
        "photo-1543163521-1bf539c55dd2", "photo-1525507119028-ed4c629a60a3",
    ],

    # --- Jewellery --------------------------------------------------------
    "jewellery-earrings": [
        "photo-1535632787350-4e68ef0ac584", "photo-1611591437281-460bfbe1220a",
        "photo-1605100804763-247f67b3557e", "photo-1599643477877-530eb83abc8e",
        "photo-1602030638412-bb8dcc0bc8b0", "photo-1573408301185-9146fe634ad0",
        "photo-1603561591411-07134e71a2a9", "photo-1573408301519-26877668e6c8",
        "photo-1535556116002-6281ff3e9f36", "photo-1611652022419-a9419f743ab4",
        "photo-1612271234123-a8c4d51c7c11", "photo-1601121141461-9d6647bca1ed",
    ],
    "jewellery-necklaces": [
        "photo-1599643477877-530eb83abc8e", "photo-1611591437281-460bfbe1220a",
        "photo-1535632787350-4e68ef0ac584", "photo-1605100804763-247f67b3557e",
        "photo-1573408301185-9146fe634ad0", "photo-1602030638412-bb8dcc0bc8b0",
        "photo-1611652022419-a9419f743ab4", "photo-1612271234123-a8c4d51c7c11",
        "photo-1601121141461-9d6647bca1ed",
    ],
    "jewellery-rings": [
        "photo-1605100804763-247f67b3557e", "photo-1535632787350-4e68ef0ac584",
        "photo-1611591437281-460bfbe1220a", "photo-1573408301185-9146fe634ad0",
        "photo-1602030638412-bb8dcc0bc8b0", "photo-1611652022419-a9419f743ab4",
        "photo-1612271234123-a8c4d51c7c11",
    ],
    "jewellery-bangles": [
        "photo-1611591437281-460bfbe1220a", "photo-1599643477877-530eb83abc8e",
        "photo-1535632787350-4e68ef0ac584", "photo-1573408301185-9146fe634ad0",
        "photo-1602030638412-bb8dcc0bc8b0", "photo-1612271234123-a8c4d51c7c11",
    ],

    # --- Beauty -----------------------------------------------------------
    "beauty-skincare": [
        "photo-1556228720-195a672e8a03", "photo-1620916566398-39f1143ab7be",
        "photo-1612817288484-6f916006741a", "photo-1571781926291-c477ebfd024b",
        "photo-1608248543803-ba4f8c70ae0b", "photo-1631730486572-226d1f595b68",
        "photo-1598440947619-2c35fc9aa908", "photo-1601049541289-9b1b7bbbfe19",
        "photo-1620916297-13f2d3c5d3eb", "photo-1591375275623-f0b76b8c0b4c",
        "photo-1556228841-7c8e8e3ae87f", "photo-1583209814683-c023dd293cc6",
        "photo-1571875257727-256c39da42af", "photo-1595425970377-c9703cf48b6d",
    ],
    "beauty-makeup": [
        "photo-1586495777744-4413f21062fa", "photo-1631214504543-30c47b13ab09",
        "photo-1522335789203-aaa306b9f4b1", "photo-1571781926291-c477ebfd024b",
        "photo-1583241475880-6f9b1ba62b13", "photo-1599733589046-388dd95dc0fb",
        "photo-1614110204500-d5e7e7d2c089", "photo-1583241475880-6f9b1ba62b13",
        "photo-1607779097040-26e80aa78e66", "photo-1631730486572-226d1f595b68",
        "photo-1487412947147-5cebf100ffc2", "photo-1503236823255-94609f598e71",
    ],
    "beauty-haircare": [
        "photo-1605497788044-5a32c7078486", "photo-1556228720-195a672e8a03",
        "photo-1620916566398-39f1143ab7be", "photo-1571781926291-c477ebfd024b",
        "photo-1608248543803-ba4f8c70ae0b", "photo-1556228852-80b6e5eeff06",
        "photo-1571875257727-256c39da42af", "photo-1522338242992-e1a54906a8da",
    ],
    "beauty-fragrance": [
        "photo-1594035910387-fea47794261f", "photo-1541643600914-78b084683601",
        "photo-1592945403244-b3fbafd7f539", "photo-1523293182086-7651a899d37f",
        "photo-1615634260167-c8cdede054de", "photo-1610461888750-10bfc601b874",
        "photo-1605651531144-51381895e23d",
    ],

    # --- Watches ----------------------------------------------------------
    "watches": [
        "photo-1523275335684-37898b6baf30", "photo-1622434641406-a158123450f9",
        "photo-1524805444758-089113d48a6d", "photo-1542496658-e33a6d0d50f6",
        "photo-1612817159949-195b6eb9e31a", "photo-1539874754764-5a96559165b0",
        "photo-1547996160-81dfa63595aa", "photo-1620625515032-6ed0c1790c75",
        "photo-1548171915-3ef0a1e9d77f", "photo-1606981999016-eaa5b1bbcf02",
        "photo-1624996379697-f01d168b1a52", "photo-1622434641406-a158123450f9",
    ],

    # --- Electronics ------------------------------------------------------
    "electronics-mobile": [
        "photo-1511707171634-5f897ff02aa9", "photo-1592899677977-9c10ca588bbd",
        "photo-1567581935884-3349723552ca", "photo-1574944985070-8f3ebc6b79d2",
        "photo-1580910051073-b9e26afe3a44", "photo-1592750475338-74b7b21085ab",
        "photo-1601784551446-20c9e07cdbdb", "photo-1605236453806-6ff36851218e",
        "photo-1546027658-7aa750153465", "photo-1565849904461-04a58ad377e0",
        "photo-1606016159991-dfe4f2746ad5", "photo-1574944985070-8f3ebc6b79d2",
    ],
    "electronics-laptop": [
        "photo-1496181133206-80ce9b88a853", "photo-1517336714731-489689fd1ca8",
        "photo-1593642632559-0c6d3fc62b89", "photo-1525547719571-a2d4ac8945e2",
        "photo-1531297484001-80022131f5a1", "photo-1541807084-5c52b6b3adef",
        "photo-1611186871348-b1ce696e52c9", "photo-1588872657578-7efd1f1555ed",
        "photo-1517059224940-d4af9eec41b7",
    ],
    "electronics-audio": [
        "photo-1505740420928-5e560c06d30e", "photo-1546435770-a3e426bf472b",
        "photo-1583394838336-acd977736f90", "photo-1574920162043-b872873f19c8",
        "photo-1545127398-14699f92334b", "photo-1487215078519-e21cc028cb29",
        "photo-1572569511254-d8f925fe2cbb", "photo-1610465299996-30f240ac2b1c",
        "photo-1606220838315-056192d5e927", "photo-1484704849700-f032a568e944",
        "photo-1599669454699-248893623440", "photo-1583394838336-acd977736f90",
    ],
    "electronics-smartwatch": [
        "photo-1508685096489-7aacd43bd3b1", "photo-1579586337278-3befd40fd17a",
        "photo-1551816230-ef5deaed4a26", "photo-1546868871-7041f2a55e12",
        "photo-1617043786394-f977fa12eddf", "photo-1556906781-9a412961c28c",
        "photo-1622434641406-a158123450f9", "photo-1606981999016-eaa5b1bbcf02",
    ],
    "electronics-tv": [
        "photo-1593359677879-a4bb92f829d1", "photo-1601944179066-29b8f7e29c3d",
        "photo-1593784991095-a205069470b6", "photo-1571415060716-baff5f717023",
        "photo-1556761175-b413da4baf72", "photo-1605374213029-72c11f1d8eef",
    ],
    "electronics-camera": [
        "photo-1502920917128-1aa500764cbd", "photo-1606980625512-b7df3df7c8f7",
        "photo-1502982720700-bfff97f2ecac", "photo-1542038784456-1ea8e935640e",
        "photo-1494173853739-c21f58b16055", "photo-1516035069371-29a1b244cc32",
    ],
    "electronics-accessories": [
        "photo-1609091839311-d5365f9ff1c5", "photo-1583394838336-acd977736f90",
        "photo-1572569511254-d8f925fe2cbb", "photo-1610465299996-30f240ac2b1c",
        "photo-1606220838315-056192d5e927", "photo-1484704849700-f032a568e944",
        "photo-1574920162043-b872873f19c8", "photo-1556761175-b413da4baf72",
        "photo-1545127398-14699f92334b",
    ],

    # --- Home -------------------------------------------------------------
    "home-kitchen": [
        "photo-1556909114-f6e7ad7d3136", "photo-1565183997392-2f6f122e5912",
        "photo-1556910103-1c02745aae4d", "photo-1565538810643-b5bdb714032a",
        "photo-1556909211-d5b07b1e88e9", "photo-1556910096-6f5e72db6803",
        "photo-1556909114-44d0a64b9b6b", "photo-1564540583246-934409427776",
    ],
    "home-decor": [
        "photo-1567538096631-e0c55bd6374c", "photo-1493663284031-b7e3aefcae8e",
        "photo-1530603907829-659ab5ea0a96", "photo-1513519245088-0e12902e5a38",
        "photo-1582582494705-f8ce0b0c24f0", "photo-1631048500140-c3a395a85e7d",
        "photo-1525873089432-ba6d8b66c7f6",
    ],
}


def _head(url: str, timeout: float = 4.0) -> bool:
    """HEAD probe — returns True if Unsplash serves the photo, False on 404/timeout."""
    req = urllib.request.Request(url, method="HEAD")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status == 200
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError):
        return False


def verify_pools(pools: dict[str, list[str]], parallelism: int = 24) -> dict[str, list[str]]:
    """Filter each category pool to only those photo IDs that resolve to a 200.

    Run as a one-time pre-flight before the generator writes products.seed.json
    so the storefront never references a broken Unsplash photo.
    """
    bad: list[tuple[str, str]] = []
    pool_set: set[str] = {pid for ids in pools.values() for pid in ids}
    print(f"verifying {len(pool_set)} unique photo IDs across {len(pools)} pools...")

    def _check(pid: str) -> tuple[str, bool]:
        url = f"https://images.unsplash.com/{pid}?auto=format&fit=crop&w=400&q=60"
        return pid, _head(url)

    results: dict[str, bool] = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=parallelism) as pool:
        for pid, ok in pool.map(_check, sorted(pool_set)):
            results[pid] = ok

    cleaned: dict[str, list[str]] = {}
    for cat, ids in pools.items():
        keep = [pid for pid in ids if results.get(pid, False)]
        dropped = [pid for pid in ids if not results.get(pid, False)]
        cleaned[cat] = keep
        if dropped:
            for d in dropped:
                bad.append((cat, d))

    print(f"  ok: {sum(results.values())}, bad: {len(results) - sum(results.values())}")
    if bad:
        print(f"  dropped IDs (first 20):")
        for cat, pid in bad[:20]:
            print(f"    {cat}: {pid}")
        if len(bad) > 20:
            print(f"    ... and {len(bad) - 20} more")
    return cleaned


if __name__ == "__main__":
    cleaned = verify_pools(IMAGE_POOLS)
    print()
    print("=== Verified pool sizes ===")
    for cat, ids in cleaned.items():
        print(f"  {cat:30s} {len(ids):3d} (was {len(IMAGE_POOLS[cat])})")
