"""Load the old portal's fourteen exhibitor forms into one edition as sample order forms.

Source: the old PHP portal (resources/views/order-forms/form-*.blade.php and
resources/data/form-options.json), transcribed here once: titles, notes, catalog items and prices,
choices (contractors, forwarders, product categories), and the free badges and parking passes per
booth area. See docs/EXHIBITOR_ORDER_FORMS.md, appendix A, for how each old form maps to ours.

Goes through the desk API as a staff user with order_form.manage, so every rule and the audit log
apply. Safe to run again: a form number already in the edition is kept and only its missing
catalog items are added; choices are set only on a form that has none yet.

    EMS_URL=http://localhost:8000 EMS_EMAIL=... EMS_PASSWORD=... \
        python -m scripts.seed_sample_order_forms --edition INATEX2027

Options: --draft keeps new forms unpublished; --images also copies each item's picture from the
old portal (peragaexpo.com); --dry-run only prints what would be added.
"""

import argparse
import os
import sys
from datetime import date, timedelta
from decimal import Decimal
from typing import Any
from urllib.parse import unquote

import httpx

OLD_IMAGES = "https://peragaexpo.com/adminoem/admin/content/upload_item/"

# (section, code, name, size, price, picture file on the old portal)
Item = tuple[str | None, str, str, str | None, str, str | None]

PAYMENT_NOTE = (
    "Orders are delivered only after full payment. No cancellation or refund once an order is "
    "confirmed or after the deadline. Orders after the deadline are charged at the surcharge "
    "price; onsite orders at the onsite price."
)

FORMS: list[dict[str, Any]] = [
    {
        "code": "01",
        "title": "E-Directory Listing",
        "group": 1,
        "details_type": "directory_listing",
        "instructions": (
            "Your company profile for the online exhibitor directory. Tell us how you want to be "
            "listed, which products you show, and your agents or principals."
        ),
        "options": {
            "PRODUCT_CATEGORY": [
                "Fiber",
                "Filaments",
                "Yarns",
                "Industrial Textiles",
                "Accessories & Trimmings",
                "Textile Services",
                "Printing Accessories",
                "Fabrics",
                "Button",
                "Zipper",
                "Processing Equipment, Finishing & Converting Machinery",
                "Raw Materials for Nonwovens and Ancillaries",
                "Nonwoven Fabric",
                "Nonwoven Roll Goods",
                "Nonwoven Products",
                "Nonwoven Services",
                "Bedding",
                "Bed Linens",
                "Quilts, Blankets",
                "Pillows",
                "Kitchen Linens",
                "Towels",
                "Table Decorations, Table Coverings",
                "Carpets and Rugs",
                "Bath Textiles and Accessories",
                "Curtains, Curtain Textiles and Accessories",
                "Decorative Cushions",
                "Upholstery Fabrics",
                "Others",
            ],
        },
    },
    {
        "code": "02",
        "title": "E-Directory & Onsite Advertising",
        "group": 1,
        "details_type": "advertising",
        "has_catalog": True,
        "attachment_purposes": ["LOGO", "OTHER"],
        "secondary_deadline_label": "Material Deadline",
        "instructions": (
            "Advertising space is booked first come, first served. The organizer is not "
            "responsible for any error, loss, damage, or claim from an advertisement that fails "
            "to appear.\n\nArtwork: four color, original artwork. Send your logo and the ad "
            "artwork as attachments before the Material Deadline."
        ),
        "items": [
            ("E-Directory Advertising", "AD-01", "Run of full page", None, "9193100", None),
            (
                "Onsite Advertising",
                "AD-02",
                "Giant banner, printed by organizer",
                "6 m (W) x 4 m (H)",
                "18241300",
                None,
            ),
            (
                "Onsite Advertising",
                "AD-03",
                "Giant banner, printed by exhibitor",
                "6 m (W) x 4 m (H)",
                "14184100",
                None,
            ),
            (
                "Onsite Advertising",
                "AD-04",
                "Hanging banner, 2 sides (minimum 5 pcs)",
                "2 m (W) x 1 m (H)",
                "1014300",
                None,
            ),
            (
                "Onsite Advertising",
                "AD-05",
                "Horizontal banner",
                "6 m (W) x 1.12 m (H)",
                "1835400",
                None,
            ),
            (
                "Onsite Advertising",
                "AD-06",
                "Vertical banner (minimum 5 pcs)",
                "0.9 m (W) x 4 m (H)",
                "1432900",
                None,
            ),
            (
                "Onsite Advertising",
                "AD-07",
                "Panel pillar ads, 4 sides (sticker)",
                "1 m (W) x 2.5 m (H)",
                "14377300",
                None,
            ),
        ],
        "descriptions": {
            "AD-02": "Material: flexi banner.",
            "AD-03": "Material: flexi banner.",
            "AD-04": "Material: flexi.",
            "AD-05": "Material: flexi.",
            "AD-06": "Material: flexi.",
            "AD-07": "Material: sticker.",
        },
    },
    {
        "code": "02a",
        "title": "Social Media Promotion",
        "group": 1,
        "details_type": "social_media",
        "attachment_purposes": ["LOGO", "PRODUCT_IMAGE"],
        "instructions": (
            "Send a photo of your product with a short description to be shown in the online "
            "exhibitor directory and other promotions. Only booths above 54 sqm are shown in "
            "the social media promotion.\n\nUp to three product photos per company: the product "
            "only, no text, logo, or photo grouping. JPG or PNG, up to 2 MB, 1080 x 1080 px at "
            "300 dpi. All logos are used for promotion."
        ),
        "options": {
            "PRODUCT_CATEGORY": ["Home Textiles", "Products Textiles", "Technical Textiles"],
        },
    },
    {
        "code": "03",
        "title": "Stand Service & Stand Construction",
        "group": 1,
        "details_type": "stand_service",
        "instructions": (
            "Standard booth facilities by booth size (9 / 18 / 27 / 36 / 54 sqm):\n"
            "- Reception desk (lockable): 1 / 2 / 3 / 4 / 8\n"
            "- Chairs: 3 / 6 / 8 / 12 / 20\n"
            "- Glass round table: 1 / 1 / 1 / 2 / 4\n"
            "- Storage: - / 2x1x2.5 m / 2x1x2.5 m / 2x2x2.5 m / 2x3x2.5 m\n"
            "- Folding door: - / 1 / 1 / 1 / 1\n"
            "- Fluorescent lamp: 2 / 4 / 6 / 8 / 12\n"
            "- Power: 2A/1P / 4A/1P / 6A/1P / 6+2A/1P / 10+2A/1P (one unit each)\n"
            "- Waste basket: 1 / 1 / 2 / 2 / 4\n"
            "- Fascia name board: 1-2 / 2-4 / 2-4 / 6-8 / 6-8\n"
            "Each 9 sqm comes with 2A/1P power (440 W / 220 V). The facilities cannot be "
            "exchanged.\n\n"
            "Fascia name: write the company name in block letters, at most 60 characters. A "
            "change made onsite costs USD 35 per panel.\n\n"
            "Building your own stand: send the drawing by email before the deadline. A "
            "non-official contractor pays working power onsite, a refundable deposit to the "
            "venue, and an inspection fee of Rp 30,000/sqm to the organizer.\n\n"
            "Recommended contractors: PT. Aditi Indonesia Jaya, PT. Efast Global Indonesia, "
            "PT. Parama Arsa Multikreasi, PT. CK Helmer, PT. City Neon Prima Mandiri, "
            "PT. Royal Cipta Inter Asia, PT. Pentawira Cipta Indonesia."
        ),
        "options": {
            "STAND_SERVICE": [
                "Use organizer's stand service",
                "Build our own stand (using contractor)",
            ],
            "OFFICIAL_CONTRACTOR": [
                "PT. Wanindo Prima",
                "PT. Samudra Dyan Praga",
                "PT. City Neonindo Indah Murni",
            ],
        },
    },
    {
        "code": "04",
        "title": "Electrical Fittings & Supplies",
        "group": 2,
        "has_catalog": True,
        "allow_custom_items": True,
        "attachment_purposes": ["FITTING_LOCATION"],
        "instructions": (
            "Mark where each fitting goes on your booth layout and attach it.\n\n"
            "3-phase supply for machinery comes with an MCB. Bring your own stabilizer for "
            "sensitive equipment: the organizer is not responsible for damage from voltage or "
            "frequency changes. One socket per exhibit; multi-point connections are not "
            "allowed. Only the official contractor may work on the main supply line. Items are "
            "rented; prices include the power point and electricity on show days, not a direct "
            "connection to machinery.\n\n" + PAYMENT_NOTE
        ),
        "items": [
            (
                "A. Lighting & Equipment",
                "E-001",
                "Fluorescent lamp @ 40 watt (incl. power)",
                None,
                "740600",
                "E-001-20171011171858-Fluorescent%20Lamp%2040%20W.jpg",
            ),
            (
                "A. Lighting & Equipment",
                "E-003",
                "Long arm spotlight @ 100 watt (incl. power)",
                None,
                "1046500",
                "E-003-20171011171950-Long%20Arm%20Spotlight%20100%20W.jpg",
            ),
            (
                "A. Lighting & Equipment",
                "E-004",
                "Downlight halogen @ 50 watt (incl. power)",
                "Ø 9 cm",
                "1014300",
                "E-004-20171011172013-Downlight%20Halogen%20LT%205%2050%20W%209%20cm.jpg",
            ),
            (
                "A. Lighting & Equipment",
                "E-007",
                "Halogen @ 150 watt (incl. power)",
                "18 x 14 x 11 cm",
                "1207500",
                "E-007-20171011172110-Halogen%20@%20150W%2018cm%20x%2014cm%20x%2011cm.jpg",
            ),
            (
                "A. Lighting & Equipment",
                "E-008",
                "Plug 1 hole",
                None,
                "386400",
                "E-008-20171011172132-Plug%201%20Hole.jpg",
            ),
            (
                "A. Lighting & Equipment",
                "E-010",
                "Multi connection",
                None,
                "305900",
                "E-010-20171011172201-Multi%20Connection.jpg",
            ),
            (
                "A. Lighting & Equipment",
                "E-011",
                "LCD TV 42 with standing (incl. power)",
                None,
                "9193100",
                "E-011-20171011172217-LCD%20TV%2042.jpg",
            ),
            (
                "A. Lighting & Equipment",
                "E-013",
                "Bracket plasma",
                None,
                "2415000",
                "E-013-20171011172248-Bracket%20Plasma.jpg",
            ),
            (
                "A. Lighting & Equipment",
                "E-014",
                "Standing plasma",
                None,
                "2415000",
                "E-014-20171011172301-Standing%20Plasma.jpg",
            ),
            (
                "A. Lighting & Equipment",
                "E-019",
                "Low refrigerator @ 1200 W (incl. power)",
                "60 x 60 x 60 cm",
                "2994600",
                "E-019-20171011172318-Low%20Refrigerator%2060x60x60.jpg",
            ),
            (
                "A. Lighting & Equipment",
                "E-020",
                "High refrigerator @ 2000 W (incl. power)",
                "47 x 53 x 105 cm",
                "3896200",
                "E-020-20171011172337-High%20Refrigerator%2047cm%20x%2053cm%20x%20105cm.jpg",
            ),
            (
                "A. Lighting & Equipment",
                "E-021",
                "Water dispenser + 5 gallon water (incl. power)",
                None,
                "2720900",
                "E-021-20171011172359-Water%20Dispenser%20%2B%205%20Gallons%20Waters.jpg",
            ),
            (
                "B. Electricity Power",
                "E-023",
                "2 amp power point (1 phase) 220 V + plug 1 hole",
                None,
                "1239700",
                None,
            ),
            (
                "B. Electricity Power",
                "E-024",
                "4 amp power point (1 phase) 220 V + plug 1 hole",
                None,
                "1400700",
                None,
            ),
            (
                "B. Electricity Power",
                "E-025",
                "6 amp power point (1 phase) 220 V + plug 1 hole",
                None,
                "1722700",
                None,
            ),
            (
                "B. Electricity Power",
                "E-025a",
                "6 amp power point (1 phase) 220 V + plug 1 hole, 24 hours",
                None,
                "2592100",
                None,
            ),
            (
                "B. Electricity Power",
                "E-026",
                "10 amp power point (1 phase) 220 V",
                None,
                "2302300",
                None,
            ),
            (
                "B. Electricity Power",
                "E-026a",
                "10 amp power point (1 phase) 220 V, 24 hours",
                None,
                "3284400",
                None,
            ),
            (
                "B. Electricity Power",
                "E-027",
                "16 amp power point (1 phase) 220 V",
                None,
                "3445400",
                None,
            ),
            (
                "B. Electricity Power",
                "E-028",
                "25 amp power point (1 phase) 220 V",
                None,
                "3976700",
                None,
            ),
            (
                "B. Electricity Power",
                "E-029",
                "32 amp power point (1 phase) 220 V",
                None,
                "4781700",
                None,
            ),
            (
                "B. Electricity Power",
                "E-030",
                "15 amp power point (3 phase) 380 V",
                None,
                "6762000",
                None,
            ),
            (
                "B. Electricity Power",
                "E-031",
                "30 amp power point (3 phase) 380 V",
                None,
                "15230600",
                None,
            ),
            (
                "B. Electricity Power",
                "E-032",
                "60 amp power point (3 phase) 380 V",
                None,
                "23522100",
                None,
            ),
            (
                "B. Electricity Power",
                "E-033",
                "100 amp power point (3 phase) 380 V",
                None,
                "34663300",
                None,
            ),
            (
                "B. Electricity Power",
                "E-034",
                "125 amp power point (3 phase) 380 V",
                None,
                "37593500",
                None,
            ),
            (
                "B. Electricity Power",
                "E-034a",
                "150 amp power point (3 phase) 380 V",
                None,
                "46995900",
                None,
            ),
            (
                "B. Electricity Power",
                "E-035",
                "200 amp power point (3 phase) 380 V",
                None,
                "52952900",
                None,
            ),
        ],
    },
    {
        "code": "05",
        "title": "Compressed Air",
        "group": 2,
        "has_catalog": True,
        "allow_custom_items": True,
        "attachment_purposes": ["FITTING_LOCATION"],
        "instructions": (
            "For each connection, write the pipe size (3/4 inch inner diameter), working "
            "pressure (bar / PSI, at most 7 bar), and air volume (liter / minute) in the "
            "remarks, and attach your booth layout with the location.\n\n" + PAYMENT_NOTE
        ),
        "items": [
            ("Compressed Air Items", "C-01", "Compressed air", None, "7406000", None),
            (
                "Compressed Air Items",
                "C-02",
                "Additional valve C/A",
                "1/2 inch each",
                "3348800",
                None,
            ),
            (
                "Compressed Air Items",
                "C-03",
                "Additional vlok + coupler installation",
                None,
                "177100",
                None,
            ),
            (
                "Compressed Air Items",
                "C-04",
                "Additional vlok + fitting hose installation",
                None,
                "177100",
                None,
            ),
            (
                "Compressed Air Items",
                "C-05",
                "Additional vlok + additional valve installation",
                None,
                "177100",
                None,
            ),
            (
                "Compressed Air Items",
                "C-06",
                "Additional vlok + nozzle installation",
                None,
                "177100",
                None,
            ),
        ],
        "descriptions": {
            "C-01": "The contractor provides up to the ball valve, standard ring size 3/4 inch.",
        },
    },
    {
        "code": "06",
        "title": "Water & Waste",
        "group": 2,
        "has_catalog": True,
        "allow_custom_items": True,
        "attachment_purposes": ["FITTING_LOCATION"],
        "instructions": (
            "Write the water in and water out sizes (inches) in the remarks and attach your "
            "booth layout with the location. Iron, rubber, or PVC pipelines are supplied by the "
            "official contractor at the exhibitor's expense.\n\n" + PAYMENT_NOTE
        ),
        "items": [
            ("Water & Waste Items", "W-01", "Water / waste", None, "6118000", None),
        ],
    },
    {
        "code": "07",
        "title": "Furniture & Display Rental",
        "group": 2,
        "has_catalog": True,
        "allow_custom_items": True,
        "instructions": "If you need more furniture, order it below.\n\n" + PAYMENT_NOTE,
        "items": [
            (
                "Furniture Items",
                "F-001",
                "Standard chair",
                None,
                "289800",
                "F-001-20241023140228-HALL%20A%2CD.jpg",
            ),
            (
                "Furniture Items",
                "F-003",
                "Barstool",
                "H. 52 cm",
                "515200",
                "F-003-20171011181020-Barstool%20H.52%20cm.jpg",
            ),
            (
                "Furniture Items",
                "F-004",
                "Easy arm chair",
                "H. 42 cm",
                "660100",
                "F-004-20171011181040-Easy%20Arm%20Chair%20H.42%20cm.jpg",
            ),
            (
                "Furniture Items",
                "F-009",
                "Wooden top round table",
                "Ø 80 cm, H. 75 cm",
                "756700",
                "F-009-20171011181154-Wooden%20Top%20Round%20Table%2080cm%20H.75cm.jpg",
            ),
            (
                "Furniture Items",
                "F-010",
                "Glass top round table",
                "Ø 100 cm, H. 75 cm",
                "772800",
                "F-010-20171011181208-Glass%20Top%20Round%20Table%20100cm%20H.75cm.jpg",
            ),
            (
                "Furniture Items",
                "F-013",
                "Reception desk",
                "100 x 50 x 75 cm",
                "644000",
                "F-013-20171011181247-Reception%20Desk%20100x50x75%20cm.jpg",
            ),
            (
                "Furniture Items",
                "F-014",
                "Lockable desk",
                "100 x 50 x 75 cm",
                "788900",
                "F-014-20171011181301-Lockable%20Desk%20100x50x75%20cm.jpg",
            ),
            (
                "Furniture Items",
                "F-015",
                "Display box small",
                "50 x 50 x 50 cm",
                "466900",
                "F-015-20171011181314-Display%20Box%20Small%2050x50x50%20cm.jpg",
            ),
            (
                "Furniture Items",
                "F-016",
                "Display box medium",
                "50 x 50 x 75 cm",
                "563500",
                "F-016-20171011181328-Display%20Box%20Medium%2050x50x75%20cm.jpg",
            ),
            (
                "Furniture Items",
                "F-017",
                "Display box large",
                "50 x 50 x 100 cm",
                "692300",
                "F-017-20171011181341-Display%20Box%20Large%2050x50x100%20cm.jpg",
            ),
            (
                "Furniture Items",
                "F-018",
                "3 tier counter",
                "50 x 50 x 50/75/100 cm",
                "2060800",
                "F-018-20171011181355-3%20Tier%20Counter%2050x50x50%2C75%2C100%20cm.jpg",
            ),
            (
                "Furniture Items",
                "F-019",
                "2 tier counter",
                "50 x 50 x 50/75 cm",
                "1610000",
                "F-019-20171011181411-2%20Tier%20Counter%2050x50x50%2C75%20cm.jpg",
            ),
            (
                "Furniture Items",
                "F-020",
                "Low showcase",
                "100 x 50 x 100 cm",
                "1159200",
                "F-020-20171011181425-Low%20Showcase%20100x50x100%20cm.jpg",
            ),
            (
                "Furniture Items",
                "F-021",
                "Square high showcase without light (I)",
                "50 x 50 x 200 cm",
                "1416800",
                "F-021-20250123085627-square.jpg",
            ),
            (
                "Furniture Items",
                "F-022",
                "High showcase without light (II)",
                "100 x 50 x 200 cm",
                "2543800",
                "F-022-20171011181507-High%20Showcase%20Without%20Light%20100x50x200%20cm.jpg",
            ),
            (
                "Furniture Items",
                "F-023",
                "Standing panel board",
                "100 x 250 cm",
                "869400",
                "F-023-20171011181519-Standing%20Panel%20Board%20100x250%20cm.jpg",
            ),
            (
                "Furniture Items",
                "F-024",
                "Shelving rack (per piece)",
                "100 x 30 cm",
                "515200",
                "F-024-20171011181535-Shelving%20Rack%20100x30%20cm.jpg",
            ),
            (
                "Furniture Items",
                "F-026",
                "Waste basket",
                "95 x 150 cm",
                "112700",
                "F-026-20231108105704-waste%20basket.png",
            ),
            (
                "Furniture Items",
                "F-027",
                "Brochure rack",
                "H. 40 cm",
                "676200",
                "F-027-20250123085642-brochure.jpg",
            ),
            (
                "Furniture Items",
                "F-028",
                "Potted plant",
                None,
                "595700",
                "F-028-20171011181628-Potted%20Plan.jpg",
            ),
            (
                "Furniture Items",
                "F-030",
                "Standing coat hanger",
                None,
                "644000",
                "standing%20coat.jpeg",
            ),
            ("Furniture Items", "F-033", "Folding door", None, "2817500", "folding%20door.jpeg"),
            ("Furniture Items", "F-034B", "Pegboard", None, "1094800", "pegboard.jpeg"),
            ("Furniture Items", "F-035", "Hook 20 cm", None, "32200", "hook.jpeg"),
            ("Furniture Items", "F-036", "Rod hanger", None, "901600", "rod%20hanger.jpeg"),
        ],
    },
    {
        "code": "08",
        "title": "Exhibit Details (Machinery)",
        "group": 2,
        "details_type": "exhibit_details",
        "instructions": (
            "List the machinery and exhibits you bring: quantity, content, dimensions, and "
            "weight, and whether they are for sale or operated during the show."
        ),
    },
    {
        "code": "08a",
        "title": "Freight Forwarder Service",
        "group": 2,
        "details_type": "freight",
        "instructions": (
            "Choose the official freight forwarder, or give the details of your own shipping "
            "agent. List the goods with quantity, content, size (L x W x H in meters), and "
            "weight. Check the hall's floor loading limit before shipping heavy machinery, and "
            "ask the official forwarders for a quotation."
        ),
        "options": {
            "OFFICIAL_FORWARDER": [
                "PT. Sri Langka",
                "PT. Maximos Global Logistik",
                "PT. DSV Solutions Indonesia",
            ],
        },
    },
    {
        "code": "09",
        "title": "Exhibitor Badges & Visa",
        "group": 2,
        "details_type": "badges_visa",
        "has_catalog": True,
        "attachment_purposes": ["VISA_LIST"],
        "instructions": (
            "Free badges by booth size: 9 sqm 5, 18 sqm 10, 27 sqm 15, 36 sqm 20, 54 sqm 25, "
            "72 sqm and above 30. Business invitations: 100 up to 27 sqm, 150 up to 54 sqm, 200 "
            "above. Collect badges at the organizer's onsite office; wear them at all times "
            "during move-in and the show.\n\nNeed a visa invitation letter? Attach the list of "
            "names (XLSX)."
        ),
        "items": [
            (None, "B-01", "Exhibitor badge", None, "0", None),
        ],
        "max_quantity": {"B-01": 30},
        "allowances": {
            "B-01": [("9", 5), ("18", 10), ("27", 15), ("36", 20), ("54", 25), ("72", 30)],
        },
    },
    {
        "code": "10",
        "title": "Seminar",
        "group": 2,
        "details_type": "seminar",
        "has_catalog": True,
        "currency": "USD",
        "instructions": (
            "Hold a seminar during the show, first come, first served. The organizer provides, "
            "for 30 people: chairs with covers, a reception desk, a speaker table with chairs, "
            "an LCD projector with a 2 x 3 m screen (power included), a sound system, and a "
            "coffee break for 30. Not included: notebook, backdrop, invitations, decoration, or "
            "other seminar material."
        ),
        "items": [
            (None, "S-01", "Seminar presentation (up to 2 hours)", None, "1575", None),
        ],
    },
    {
        "code": "11",
        "title": "Internet / Wi-Fi",
        "group": 2,
        "has_catalog": True,
        "instructions": (
            "Prices are for the show period. The Wi-Fi username and password are given after "
            "your order is approved. Contact the organizer for anything else.\n\n" + PAYMENT_NOTE
        ),
        "items": [
            (
                "Internet/Wi-Fi Items",
                "I-01",
                "Dedicated Wi-Fi 30 Mbps, incl. 1 switcher or access share",
                None,
                "8855000",
                None,
            ),
            (
                "Internet/Wi-Fi Items",
                "I-02",
                "Dedicated Wi-Fi 50 Mbps, incl. 1 switcher or access share",
                None,
                "11511500",
                None,
            ),
            (
                "Internet/Wi-Fi Items",
                "I-03",
                "Dedicated Wi-Fi 80 Mbps, incl. 1 switcher or access share",
                None,
                "14892500",
                None,
            ),
            (
                "Internet/Wi-Fi Items",
                "I-04",
                "Additional access share / point",
                None,
                "4025000",
                None,
            ),
        ],
    },
    {
        "code": "12",
        "title": "Parking Pass",
        "group": 2,
        "details_type": "parking",
        "has_catalog": True,
        "instructions": (
            "Free car passes by booth size: below 9 sqm 1, 9 to 26 sqm 2, 27 to 36 sqm 3, 37 to "
            "54 sqm 4, above 54 sqm 5. Extra passes are valid for every show day. One pass is "
            "valid for one plate number; write the plates below. Extra passes cannot be "
            "cancelled or returned. Prices follow the venue and may change."
        ),
        "items": [
            (None, "P-01", "Car parking pass", None, "241500", None),
            (None, "P-02", "Motorcycle parking pass", None, "88550", None),
        ],
        "allowances": {
            "P-01": [("0", 1), ("9", 2), ("27", 3), ("37", 4), ("54.01", 5)],
        },
    },
]


class Desk:
    """A signed-in desk session: cookie plus the CSRF header on writes."""

    def __init__(self, base: str, email: str, password: str) -> None:
        self.http = httpx.Client(base_url=base.rstrip("/") + "/api/v1", timeout=30)
        self._check(self.http.post("/auth/login", json={"email": email, "password": password}))
        me = self._check(self.http.get("/auth/me"))
        self.http.headers["X-CSRF-Token"] = me["csrf_token"]

    @staticmethod
    def _check(r: httpx.Response) -> Any:
        if r.is_error:
            raise SystemExit(f"{r.request.method} {r.request.url.path}: {r.status_code} {r.text}")
        return r.json() if r.content else None

    def get(self, path: str, **params: Any) -> Any:
        return self._check(self.http.get(path, params=params))

    def send(self, method: str, path: str, **kw: Any) -> Any:
        return self._check(self.http.request(method, path, **kw))


def deadlines(edition: dict[str, Any]) -> dict[int, date]:
    """Group 1 (listing, ads, stand) closes four weeks before the show, the rest three weeks."""
    start = date.fromisoformat(edition["start_date"])
    return {1: start - timedelta(days=28), 2: start - timedelta(days=21)}


def seed(desk: Desk, edition_code: str, publish: bool, images: bool, dry_run: bool) -> None:
    editions = desk.get("/editions", page_size=500)["items"]
    edition = next((e for e in editions if e["code"] == edition_code), None)
    if edition is None:
        raise SystemExit(f"edition {edition_code} not found")
    due = deadlines(edition)
    existing = {f["code"]: f for f in desk.get("/order-forms", edition_id=edition["id"])["items"]}
    pictures = httpx.Client(timeout=30, follow_redirects=True) if images else None

    for n, spec in enumerate(FORMS):
        code = spec["code"]
        form = existing.get(code)
        if form is None:
            body = {
                "edition_id": edition["id"],
                "code": code,
                "title": spec["title"],
                "details_type": spec.get("details_type"),
                "has_catalog": spec.get("has_catalog", False),
                "allow_custom_items": spec.get("allow_custom_items", False),
                "attachment_purposes": spec.get("attachment_purposes", []),
                "deadline_on": due[spec["group"]].isoformat(),
                "instructions": spec["instructions"],
                "sort_order": (n + 1) * 10,
            }
            if "currency" in spec:
                body["currency"] = spec["currency"]
            if "secondary_deadline_label" in spec:
                body["secondary_deadline_label"] = spec["secondary_deadline_label"]
                body["secondary_deadline_on"] = due[2].isoformat()
            print(f"{code} {spec['title']}: new form")
            if dry_run:
                continue
            form = desk.send("POST", "/order-forms", json=body)
        else:
            print(f"{code} {spec['title']}: already there, adding what is missing")
            if dry_run:
                continue

        fid = form["id"]
        have = {
            i["code"] for i in desk.get(f"/order-forms/{fid}/items", include_inactive=True)["items"]
        }
        added = 0
        for order, (section, icode, name, size, price, picture) in enumerate(spec.get("items", [])):
            if icode in have:
                continue
            item = desk.send(
                "POST",
                f"/order-forms/{fid}/items",
                json={
                    "section": section,
                    "code": icode,
                    "name": name,
                    "size": size,
                    "description": spec.get("descriptions", {}).get(icode),
                    "price_regular": str(Decimal(price)),
                    "max_quantity": spec.get("max_quantity", {}).get(icode),
                    "sort_order": (order + 1) * 10,
                },
            )
            added += 1
            tiers = spec.get("allowances", {}).get(icode)
            if tiers:
                desk.send(
                    "PUT",
                    f"/order-forms/{fid}/items/{item['id']}/allowances",
                    json={"tiers": [{"min_area_sqm": a, "free_quantity": q} for a, q in tiers]},
                )
            if pictures and picture:
                upload_picture(desk, pictures, fid, item["id"], picture)
        if added:
            print(f"   {added} catalog items")

        options = spec.get("options", {})
        if options:
            current = desk.get(f"/order-forms/{fid}/options")["options"]
            for kind, values in options.items():
                if not current.get(kind):
                    desk.send(
                        "PUT", f"/order-forms/{fid}/options", json={"kind": kind, "values": values}
                    )
                    print(f"   {len(values)} choices for {kind.lower().replace('_', ' ')}")

        if publish and not form["is_published"]:
            fresh = desk.get(f"/order-forms/{fid}")
            desk.send(
                "PATCH",
                f"/order-forms/{fid}",
                json={"is_published": True, "version": fresh["version"]},
            )
            print("   published")


def upload_picture(
    desk: Desk, pictures: httpx.Client, form_id: str, item_id: str, picture: str
) -> None:
    r = pictures.get(OLD_IMAGES + picture)
    name = unquote(picture)
    kind = "image/png" if name.lower().endswith(".png") else "image/jpeg"
    if r.is_error or not r.content:
        print(f"   picture {name}: not found on the old portal ({r.status_code}), skipped")
        return
    sent = desk.http.post(
        f"/order-forms/{form_id}/items/{item_id}/image",
        files={
            "file": (
                name.rsplit(".", 1)[0] + (".png" if kind == "image/png" else ".jpg"),
                r.content,
                kind,
            )
        },
    )
    if sent.is_error:
        print(f"   picture {name}: not accepted ({sent.status_code}), skipped")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--edition", required=True, help="edition code, e.g. INATEX2027")
    parser.add_argument("--draft", action="store_true", help="keep new forms unpublished")
    parser.add_argument(
        "--images", action="store_true", help="copy item pictures from the old portal"
    )
    parser.add_argument("--dry-run", action="store_true", help="only print what would be added")
    args = parser.parse_args()
    base = os.environ.get("EMS_URL", "http://localhost:8000")
    email, password = os.environ.get("EMS_EMAIL"), os.environ.get("EMS_PASSWORD")
    if not email or not password:
        sys.exit("set EMS_EMAIL and EMS_PASSWORD (a staff user with order_form.manage)")
    seed(Desk(base, email, password), args.edition, not args.draft, args.images, args.dry_run)


if __name__ == "__main__":
    main()
