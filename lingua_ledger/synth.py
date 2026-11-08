"""Synthetic multilingual invoices: rendered PDF, clean PNG, scan-degraded JPG and exact gold per document."""

from __future__ import annotations

import json
import random
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from string import ascii_uppercase
from xml.sax.saxutils import escape

import numpy as np
import pypdfium2 as pdfium
from PIL import Image, ImageChops, ImageFilter
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import Paragraph, Table, TableStyle

from .config import DATA_PROCESSED
from .normalize import iban_check_digits
from .schemas import Invoice, LineItem
from .validate import validate

DATASET = "synth_invoices"
LANGS = ("en", "de", "fr", "es", "it", "pt", "ja")
DPI = 150
CJK_FONT = "HeiseiKakuGo-W5"
PAGE_W, PAGE_H = A4
MARGIN = 48
INK = colors.HexColor("#1f2328")
MUTED = colors.HexColor("#5b636e")
RULE = colors.HexColor("#c9ced6")
HEADER_FILL = colors.HexColor("#eef0f3")
ZEBRA_FILL = colors.HexColor("#f3f5f8")
ACCENTS = ("#1f4e79", "#7a1f3d", "#1d6b52", "#8a4b08", "#3b3f8f", "#5a2a82")
LOGO_SHAPES = ("square", "circle", "round")
TEMPLATES = ("classic", "band", "minimal")

MONTH_NAMES = {
    "en": ("January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
           "November", "December"),
    "de": ("Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August", "September", "Oktober",
           "November", "Dezember"),
    "fr": ("janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre",
           "novembre", "décembre"),
    "es": ("enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre",
           "noviembre", "diciembre"),
    "it": ("gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto", "settembre",
           "ottobre", "novembre", "dicembre"),
    "pt": ("janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro",
           "novembro", "dezembro"),
}


def _month(lang: str, d: date) -> str:
    return MONTH_NAMES[lang][d.month - 1]


DATE_FORMATS = {
    "en": (lambda d: f"{d:%d/%m/%Y}", lambda d: f"{d.day} {_month('en', d)[:3]} {d.year}",
           lambda d: f"{d.day} {_month('en', d)} {d.year}"),
    "de": (lambda d: f"{d:%d.%m.%Y}", lambda d: f"{d.day}. {_month('de', d)} {d.year}"),
    "fr": (lambda d: f"{d:%d/%m/%Y}", lambda d: f"{'1er' if d.day == 1 else d.day} {_month('fr', d)} {d.year}"),
    "es": (lambda d: f"{d:%d/%m/%Y}", lambda d: f"{d.day} de {_month('es', d)} de {d.year}"),
    "it": (lambda d: f"{d:%d/%m/%Y}", lambda d: f"{d.day} {_month('it', d)} {d.year}"),
    "pt": (lambda d: f"{d:%d/%m/%Y}", lambda d: f"{d:%d-%m-%Y}", lambda d: f"{d.day} de {_month('pt', d)} de {d.year}"),
    "ja": (lambda d: f"{d.year}年{d.month}月{d.day}日", lambda d: f"{d:%Y/%m/%d}"),
}

LOCALES: dict[str, dict] = {
    "en": {
        "country": "GB", "currency": "GBP", "symbol": "£", "symbol_after": False, "vat_rate": 20,
        "labels": {
            "invoice": "INVOICE", "number": "Invoice No.", "date": "Invoice Date", "due": "Due Date",
            "bill_to": "Bill To", "desc": "Description", "qty": "Qty", "unit": "Unit Price", "amount": "Amount",
            "subtotal": "Subtotal", "total": "Total Due", "vat_id": "VAT Reg. No.", "bank": "Bank",
            "terms": "Payment terms", "thanks": "Thank you for your business.",
        },
        "tax_label": "VAT {rate}%",
        "terms": "Payment due within {days} days of invoice date",
        "number": "INV-{year}-{seq:04d}",
        "vendors": (
            ("Hartley & Sons Ltd", ("14 King Street", "Manchester M2 4LQ"), "HS"),
            ("Brightwater Consulting Ltd", ("221 Deansgate", "Manchester M3 4EN"), "BC"),
            ("Northbridge Supplies Ltd", ("8 Castle Street", "Edinburgh EH2 3AT"), "NS"),
            ("Kestrel Digital Ltd", ("45 Broad Street", "Bristol BS1 2EP"), "KD"),
            ("Ashford Office Solutions Ltd", ("3 Station Road", "Reading RG1 1LG"), "AO"),
        ),
        "customers": (
            ("Thornton Logistics plc", ("12 Wharf Road", "London N1 7GR")),
            ("Greenfield Estates Ltd", ("90 Park Lane", "Leeds LS1 2SJ")),
            ("Marlow & Pike LLP", ("5 Cathedral Close", "Norwich NR1 4DH")),
            ("Oakridge Dental Practice", ("27 High Street", "Oxford OX1 4AH")),
        ),
        "items": (
            ("Consulting services (hours)", 65, 180, True),
            ("Website development - phase 1", 800, 4500, False),
            ("Annual software licence", 120, 1500, False),
            ("Server maintenance (monthly)", 90, 600, False),
            ("A4 copier paper, box of 5 reams", 18, 45, False),
            ("Ergonomic office chair", 95, 420, False),
            ("Staff training workshop (full day)", 250, 1800, False),
            ("Courier and delivery charges", 8, 60, False),
            ("Cloud hosting - business plan", 25, 300, False),
            ("Graphic design (hours)", 45, 120, True),
        ),
        "banks": (("NatWest", "NWBKGB2L", "NWBK"), ("Barclays Bank UK PLC", "BUKBGB22", "BUKB"),
                  ("Lloyds Bank", "LOYDGB2L", "LOYD"), ("HSBC UK Bank", "HBUKGB4B", "HBUK")),
    },
    "de": {
        "country": "DE", "currency": "EUR", "symbol": "€", "symbol_after": True, "vat_rate": 19,
        "labels": {
            "invoice": "RECHNUNG", "number": "Rechnungsnummer", "date": "Datum", "due": "Fällig am",
            "bill_to": "Rechnungsempfänger", "desc": "Beschreibung", "qty": "Menge", "unit": "Einzelpreis",
            "amount": "Betrag", "subtotal": "Zwischensumme", "total": "Gesamtbetrag", "vat_id": "USt-IdNr.",
            "bank": "Bank", "terms": "Zahlungsbedingungen", "thanks": "Vielen Dank für Ihren Auftrag.",
        },
        "tax_label": "MwSt. {rate} %",
        "terms": "Zahlbar innerhalb von {days} Tagen ohne Abzug",
        "number": "RE-{year}-{seq:05d}",
        "vendors": (
            ("Müller & Schmidt GmbH", ("Hauptstraße 12", "10115 Berlin"), "MS"),
            ("Bergmann Technik AG", ("Industriestraße 48", "70565 Stuttgart"), "BT"),
            ("Weber Bürobedarf KG", ("Lindenallee 7", "50668 Köln"), "WB"),
            ("Hoffmann IT-Services GmbH", ("Schillerstraße 23", "80336 München"), "HI"),
            ("Fischer Druck & Medien GmbH", ("Am Hafen 5", "20457 Hamburg"), "FD"),
        ),
        "customers": (
            ("Becker Bau GmbH", ("Gartenweg 3", "04109 Leipzig")),
            ("Koch Consulting UG", ("Friedrichstraße 88", "40217 Düsseldorf")),
            ("Wagner Elektro GmbH", ("Mühlenweg 14", "28195 Bremen")),
            ("Schulz Handels AG", ("Königsallee 60", "60311 Frankfurt am Main")),
        ),
        "items": (
            ("Beratungsleistung (Stunden)", 80, 190, True),
            ("Webentwicklung - Phase 1", 900, 5000, False),
            ("Softwarelizenz (jährlich)", 150, 1800, False),
            ("Wartung Serverinfrastruktur", 120, 750, False),
            ("Druckerpapier A4, 5 Pakete à 500 Blatt", 20, 55, False),
            ("Bürostuhl, ergonomisch", 110, 480, False),
            ("Mitarbeiterschulung (Tagessatz)", 600, 1600, False),
            ("Versandkosten", 6, 45, False),
            ("Cloud-Hosting Business-Tarif", 30, 320, False),
            ("Grafikdesign (Stunden)", 55, 130, True),
        ),
        "banks": (("Deutsche Bank", "DEUTDEFFXXX"), ("Commerzbank", "COBADEFFXXX"),
                  ("Sparkasse KölnBonn", "COLSDE33XXX"), ("Berliner Volksbank", "BEVODEBBXXX")),
    },
    "fr": {
        "country": "FR", "currency": "EUR", "symbol": "€", "symbol_after": True, "vat_rate": 20,
        "labels": {
            "invoice": "FACTURE", "number": "N° de facture", "date": "Date de facture", "due": "Date d'échéance",
            "bill_to": "Facturé à", "desc": "Désignation", "qty": "Qté", "unit": "Prix unitaire HT",
            "amount": "Montant HT", "subtotal": "Total HT", "total": "Total TTC", "vat_id": "N° TVA intracom.",
            "bank": "Banque", "terms": "Conditions de paiement", "thanks": "Merci de votre confiance.",
        },
        "tax_label": "TVA {rate} %",
        "terms": "Paiement à {days} jours à réception de facture",
        "number": "FA{year}-{seq:04d}",
        "vendors": (
            ("Dupont Conseil SARL", ("12 rue de la République", "69002 Lyon"), "DC"),
            ("Lefèvre & Fils SA", ("45 avenue Jean Jaurès", "31000 Toulouse"), "LF"),
            ("Martin Informatique SAS", ("8 boulevard Haussmann", "75009 Paris"), "MI"),
            ("Bernard Fournitures SARL", ("27 rue Sainte-Catherine", "33000 Bordeaux"), "BF"),
            ("Atelier Moreau SAS", ("3 quai des Chartrons", "33300 Bordeaux"), "AM"),
        ),
        "customers": (
            ("Société Girard Transports", ("18 rue du Port", "44000 Nantes")),
            ("Cabinet Rousseau Avocats", ("6 place Bellecour", "69002 Lyon")),
            ("Boulangerie Petit SARL", ("52 rue de la Paix", "67000 Strasbourg")),
            ("Hôtel Lambert SAS", ("9 promenade des Anglais", "06000 Nice")),
        ),
        "items": (
            ("Prestation de conseil (heures)", 70, 180, True),
            ("Développement site web - phase 1", 900, 4800, False),
            ("Licence logicielle annuelle", 140, 1600, False),
            ("Maintenance informatique mensuelle", 110, 700, False),
            ("Ramettes papier A4 (carton de 5)", 19, 50, False),
            ("Fauteuil de bureau ergonomique", 120, 450, False),
            ("Formation du personnel (journée)", 650, 1500, False),
            ("Frais de port et d'emballage", 7, 40, False),
            ("Hébergement cloud - offre Pro", 30, 300, False),
            ("Création graphique (heures)", 50, 120, True),
        ),
        "banks": (("BNP Paribas", "BNPAFRPPXXX"), ("Crédit Agricole", "AGRIFRPPXXX"),
                  ("Société Générale", "SOGEFRPPXXX")),
    },
    "es": {
        "country": "ES", "currency": "EUR", "symbol": "€", "symbol_after": True, "vat_rate": 21,
        "labels": {
            "invoice": "FACTURA", "number": "Nº de factura", "date": "Fecha de factura",
            "due": "Fecha de vencimiento", "bill_to": "Facturar a", "desc": "Descripción", "qty": "Cant.",
            "unit": "Precio unitario", "amount": "Importe", "subtotal": "Base imponible", "total": "Total factura",
            "vat_id": "NIF-IVA", "bank": "Banco", "terms": "Forma de pago", "thanks": "Gracias por su confianza.",
        },
        "tax_label": "IVA {rate}%",
        "terms": "Transferencia bancaria a {days} días",
        "number": "F{year}/{seq:04d}",
        "vendors": (
            ("Construcciones García S.L.", ("Calle Mayor 15", "28013 Madrid"), "CG"),
            ("Distribuciones Fernández S.A.", ("Avenida Diagonal 432", "08037 Barcelona"), "DF"),
            ("Soluciones Informáticas López S.L.", ("Calle Colón 22", "46004 Valencia"), "SL"),
            ("Suministros Martínez S.L.", ("Calle Larios 9", "29005 Málaga"), "SM"),
            ("Gráficas Sánchez S.L.", ("Gran Vía 28", "48001 Bilbao"), "GS"),
        ),
        "customers": (
            ("Hostelería Ruiz S.L.", ("Plaza Nueva 4", "41001 Sevilla")),
            ("Clínica Dental Moreno", ("Calle Alfonso I 17", "50003 Zaragoza")),
            ("Transportes Jiménez S.A.", ("Avenida de la Constitución 30", "18012 Granada")),
            ("Inmobiliaria Navarro S.L.", ("Calle Uría 41", "33003 Oviedo")),
        ),
        "items": (
            ("Servicios de consultoría (horas)", 60, 160, True),
            ("Desarrollo web - fase 1", 800, 4500, False),
            ("Licencia de software anual", 120, 1500, False),
            ("Mantenimiento informático mensual", 100, 650, False),
            ("Papel A4 para impresora (caja de 5 paquetes)", 18, 45, False),
            ("Silla de oficina ergonómica", 90, 400, False),
            ("Formación del personal (jornada)", 500, 1400, False),
            ("Gastos de envío", 6, 40, False),
            ("Alojamiento en la nube - plan empresa", 25, 280, False),
            ("Diseño gráfico (horas)", 40, 110, True),
        ),
        "banks": (("Banco Santander", "BSCHESMMXXX"), ("BBVA", "BBVAESMMXXX"), ("CaixaBank", "CAIXESBBXXX")),
    },
    "it": {
        "country": "IT", "currency": "EUR", "symbol": "€", "symbol_after": False, "vat_rate": 22,
        "labels": {
            "invoice": "FATTURA", "number": "Fattura n.", "date": "Data fattura", "due": "Scadenza",
            "bill_to": "Destinatario", "desc": "Descrizione", "qty": "Q.tà", "unit": "Prezzo unitario",
            "amount": "Importo", "subtotal": "Imponibile", "total": "Totale documento", "vat_id": "Partita IVA",
            "bank": "Banca", "terms": "Modalità di pagamento", "thanks": "Grazie per la preferenza.",
        },
        "tax_label": "IVA {rate}%",
        "terms": "Bonifico bancario a {days} giorni data fattura",
        "number": "{seq}/{year}",
        "vendors": (
            ("Rossi Forniture S.r.l.", ("Via Roma 25", "20121 Milano MI"), "RF"),
            ("Bianchi Consulting S.p.A.", ("Corso Vittorio Emanuele II 112", "10121 Torino TO"), "BC"),
            ("Ferrari Informatica S.r.l.", ("Via dei Mille 8", "40121 Bologna BO"), "FI"),
            ("Esposito & Figli S.n.c.", ("Via Toledo 156", "80134 Napoli NA"), "EF"),
            ("Studio Grafico Romano S.r.l.", ("Piazza della Signoria 3", "50122 Firenze FI"), "SR"),
        ),
        "customers": (
            ("Ristorante Colombo S.r.l.", ("Via Garibaldi 21", "16124 Genova GE")),
            ("Ricci Costruzioni S.p.A.", ("Viale Europa 70", "00144 Roma RM")),
            ("Farmacia Marino", ("Corso Italia 5", "95129 Catania CT")),
            ("Hotel Greco S.r.l.", ("Lungomare Trieste 12", "84121 Salerno SA")),
        ),
        "items": (
            ("Consulenza professionale (ore)", 60, 170, True),
            ("Sviluppo sito web - fase 1", 850, 4600, False),
            ("Licenza software annuale", 130, 1500, False),
            ("Assistenza tecnica mensile", 100, 650, False),
            ("Carta per fotocopie A4 (5 risme)", 18, 48, False),
            ("Sedia da ufficio ergonomica", 95, 420, False),
            ("Corso di formazione del personale", 550, 1500, False),
            ("Spese di spedizione", 6, 40, False),
            ("Hosting cloud - piano business", 25, 290, False),
            ("Progettazione grafica (ore)", 45, 115, True),
        ),
        "banks": (("Intesa Sanpaolo", "BCITITMMXXX"), ("UniCredit", "UNCRITMMXXX"), ("Banco BPM", "BAPPIT21XXX")),
    },
    "pt": {
        "country": "PT", "currency": "EUR", "symbol": "€", "symbol_after": True, "vat_rate": 23,
        "labels": {
            "invoice": "FATURA", "number": "Fatura n.º", "date": "Data da fatura", "due": "Data de vencimento",
            "bill_to": "Cliente", "desc": "Descrição", "qty": "Qtd.", "unit": "Preço unitário", "amount": "Valor",
            "subtotal": "Subtotal", "total": "Total a pagar", "vat_id": "NIF", "bank": "Banco",
            "terms": "Condições de pagamento", "thanks": "Obrigado pela preferência.",
        },
        "tax_label": "IVA {rate}%",
        "terms": "Pagamento a {days} dias por transferência bancária",
        "number": "FT {year}/{seq}",
        "vendors": (
            ("Silva & Costa, Lda.", ("Rua Augusta 100", "1100-053 Lisboa"), "SC"),
            ("Ferreira Tecnologia, S.A.", ("Avenida da Boavista 1200", "4100-130 Porto"), "FT"),
            ("Santos Papelaria, Lda.", ("Rua de Santa Catarina 45", "4000-447 Porto"), "SP"),
            ("Oliveira Consultores, Lda.", ("Avenida da Liberdade 210", "1250-147 Lisboa"), "OC"),
            ("Pereira Gráfica, Lda.", ("Rua Ferreira Borges 12", "3000-180 Coimbra"), "PG"),
        ),
        "customers": (
            ("Restaurante Rodrigues, Lda.", ("Rua do Comércio 33", "8000-245 Faro")),
            ("Martins Construções, S.A.", ("Avenida Central 87", "4710-229 Braga")),
            ("Clínica Sousa", ("Rua Direita 15", "3500-116 Viseu")),
            ("Hotel Fernandes, Lda.", ("Largo da Sé 2", "7000-651 Évora")),
        ),
        "items": (
            ("Serviços de consultoria (horas)", 55, 150, True),
            ("Desenvolvimento de website - fase 1", 750, 4200, False),
            ("Licença de software anual", 110, 1400, False),
            ("Manutenção informática mensal", 90, 600, False),
            ("Papel de fotocópia A4 (caixa de 5 resmas)", 17, 45, False),
            ("Cadeira de escritório ergonómica", 85, 380, False),
            ("Formação de colaboradores (dia)", 450, 1300, False),
            ("Portes de envio", 5, 35, False),
            ("Alojamento cloud - plano empresarial", 25, 260, False),
            ("Design gráfico (horas)", 40, 100, True),
        ),
        "banks": (("Caixa Geral de Depósitos", "CGDIPTPLXXX"), ("Millennium bcp", "BCOMPTPLXXX"),
                  ("Novo Banco", "BESCPTPLXXX")),
    },
    "ja": {
        "country": "JP", "currency": "JPY", "symbol": "￥", "symbol_after": False, "vat_rate": 10,
        "labels": {
            "invoice": "請求書", "number": "請求書番号", "date": "請求日", "due": "お支払期限", "bill_to": "請求先",
            "desc": "品目", "qty": "数量", "unit": "単価", "amount": "金額", "subtotal": "小計",
            "total": "合計金額", "vat_id": "登録番号", "bank": "お振込先", "terms": "お支払条件",
            "thanks": "今後ともよろしくお願い申し上げます。",
        },
        "tax_label": "消費税（{rate}%）",
        "terms": "請求日より{days}日以内にお振込みください",
        "number": "{year}-{seq:04d}",
        "vendors": (
            ("株式会社山田商事", ("〒150-0041", "東京都渋谷区神南1-2-3"), "YS"),
            ("佐藤システム株式会社", ("〒530-0001", "大阪府大阪市北区梅田2-4-9"), "SS"),
            ("有限会社鈴木印刷", ("〒460-0008", "愛知県名古屋市中区栄3-5-12"), "SP"),
            ("株式会社東京デザイン", ("〒106-0032", "東京都港区六本木4-8-7"), "TD"),
            ("高橋オフィスサプライ株式会社", ("〒810-0001", "福岡県福岡市中央区天神1-10-20"), "TO"),
        ),
        "customers": (
            ("株式会社伊藤製作所", ("〒220-0012", "神奈川県横浜市西区みなとみらい2-2-1")),
            ("渡辺商店株式会社", ("〒600-8216", "京都府京都市下京区東塩小路町721")),
            ("中村建設株式会社", ("〒980-0021", "宮城県仙台市青葉区中央1-3-1")),
            ("小林クリニック", ("〒060-0005", "北海道札幌市中央区北5条西2-5")),
        ),
        "items": (
            ("コンサルティング業務（時間）", 8000, 25000, False),
            ("ウェブサイト制作費（第1期）", 100000, 600000, False),
            ("ソフトウェアライセンス（年間）", 15000, 200000, False),
            ("サーバー保守費用（月額）", 10000, 80000, False),
            ("コピー用紙 A4 500枚×5冊", 2000, 6000, False),
            ("オフィスチェア", 12000, 60000, False),
            ("社員研修費（1日）", 50000, 200000, False),
            ("配送料", 500, 5000, False),
            ("クラウドサーバー利用料", 3000, 40000, False),
            ("デザイン制作費", 20000, 150000, False),
        ),
        "banks": (("三菱UFJ銀行", "渋谷支店"), ("みずほ銀行", "梅田支店"), ("三井住友銀行", "名古屋支店"),
                  ("りそな銀行", "六本木支店")),
    },
}

FRACTIONAL_QUANTITIES = ("1", "1.5", "2", "2.5", "3", "4", "5", "6", "7.5", "8", "10", "12")
WHOLE_QUANTITIES = (1, 1, 1, 1, 2, 2, 3, 4, 5, 6, 8, 10, 12, 20, 25)
BIG_TICKET_QUANTITIES = (1, 1, 1, 2, 3)
PAYMENT_DAYS = (14, 30, 30, 45, 60)


@dataclass
class InvoiceSpec:
    doc_id: str
    lang: str
    template: str
    accent: colors.Color
    logo_shape: str
    vendor_name: str
    vendor_lines: tuple[str, ...]
    initials: str
    vendor_tax_id: str
    customer_name: str
    customer_lines: tuple[str, ...]
    number: str
    invoice_date: date
    due_date: date
    date_variant: int
    items: list[tuple[str, Decimal, Decimal, Decimal]]
    subtotal: Decimal
    tax_amount: Decimal
    total: Decimal
    vat_rate: int
    iban: str | None
    bank_lines: tuple[str, ...]
    terms: str

    @property
    def locale(self) -> dict:
        return LOCALES[self.lang]

    @property
    def labels(self) -> dict[str, str]:
        return LOCALES[self.lang]["labels"]

    @property
    def font(self) -> str:
        return CJK_FONT if self.lang == "ja" else "Helvetica"

    @property
    def bold(self) -> str:
        return CJK_FONT if self.lang == "ja" else "Helvetica-Bold"


def format_number(value: Decimal, lang: str, decimals: int | None = None) -> str:
    places = (0 if lang == "ja" else 2) if decimals is None else decimals
    text = f"{value:,.{places}f}"
    if lang in ("de", "es", "it", "pt"):
        return text.translate(str.maketrans(",.", ".,"))
    if lang == "fr":
        return text.replace(",", " ").replace(".", ",")
    return text


def format_money(value: Decimal, lang: str) -> str:
    loc = LOCALES[lang]
    number = format_number(value, lang)
    if loc["symbol_after"]:
        return f"{number} {loc['symbol']}"
    return f"{loc['symbol']} {number}" if lang == "it" else f"{loc['symbol']}{number}"


def format_quantity(value: Decimal, lang: str) -> str:
    if value == value.to_integral_value():
        return str(int(value))
    return format_number(value, lang, 1)


def format_date(value: date, lang: str, variant: int) -> str:
    formats = DATE_FORMATS[lang]
    return formats[variant % len(formats)](value)


def _digits(rng: random.Random, n: int) -> str:
    return "".join(str(rng.randrange(10)) for _ in range(n))


def _es_cif_control(body: str) -> str:
    total = sum(int(body[i]) for i in (1, 3, 5))
    for i in (0, 2, 4, 6):
        doubled = int(body[i]) * 2
        total += doubled // 10 + doubled % 10
    return str((10 - total % 10) % 10)


def _it_partita_iva_check(base: str) -> str:
    odd = sum(int(base[i]) for i in range(0, 10, 2))
    even = sum((2 * int(base[i])) - (9 if 2 * int(base[i]) > 9 else 0) for i in range(1, 10, 2))
    return str((10 - (odd + even) % 10) % 10)


def _pt_nif_check(base: str) -> str:
    remainder = sum(int(base[i]) * (9 - i) for i in range(8)) % 11
    return "0" if remainder < 2 else str(11 - remainder)


def _jp_corporate_check(base: str) -> str:
    weighted = sum(int(d) * (1 if n % 2 else 2) for n, d in enumerate(reversed(base), start=1))
    return str(9 - weighted % 9)


def make_vat_id(country: str, rng: random.Random) -> str:
    if country in ("DE", "GB"):
        return f"{country}{rng.randint(1, 9)}{_digits(rng, 8)}"
    if country == "FR":
        siren = f"{rng.randint(1, 9)}{_digits(rng, 8)}"
        return f"FR{(12 + 3 * (int(siren) % 97)) % 97:02d}{siren}"
    if country == "ES":
        body = _digits(rng, 7)
        return f"ESB{body}{_es_cif_control(body)}"
    if country == "IT":
        base = _digits(rng, 7) + f"{rng.randint(1, 100):03d}"
        return f"IT{base}{_it_partita_iva_check(base)}"
    if country == "PT":
        base = f"5{_digits(rng, 7)}"
        return f"PT{base}{_pt_nif_check(base)}"
    if country == "JP":
        base = f"{rng.randint(1, 9)}{_digits(rng, 11)}"
        return f"T{_jp_corporate_check(base)}{base}"
    raise ValueError(f"no tax id format for {country}")


def make_iban(country: str, rng: random.Random, bank_code: str = "") -> str:
    bban = {
        "DE": lambda: _digits(rng, 18),
        "FR": lambda: _digits(rng, 23),
        "ES": lambda: _digits(rng, 20),
        "IT": lambda: rng.choice(ascii_uppercase) + _digits(rng, 22),
        "PT": lambda: _digits(rng, 21),
        "GB": lambda: bank_code + _digits(rng, 14),
    }[country]()
    return f"{country}{iban_check_digits(country, bban)}{bban}"


def group_iban(iban: str) -> str:
    return " ".join(iban[i:i + 4] for i in range(0, len(iban), 4))


def _quantize(value: Decimal, lang: str) -> Decimal:
    return value.quantize(Decimal(1) if lang == "ja" else Decimal("0.01"), rounding=ROUND_HALF_UP)


def _make_items(lang: str, rng: random.Random) -> list[tuple[str, Decimal, Decimal, Decimal]]:
    items = []
    for description, low, high, fractional in rng.sample(LOCALES[lang]["items"], rng.randint(2, 6)):
        big_ticket = high >= (100000 if lang == "ja" else 1000)
        if fractional:
            quantity = Decimal(rng.choice(FRACTIONAL_QUANTITIES))
        else:
            quantity = Decimal(rng.choice(BIG_TICKET_QUANTITIES if big_ticket else WHOLE_QUANTITIES))
        if lang == "ja":
            unit_price = Decimal(rng.randint(low // 100, high // 100) * 100)
        else:
            unit_price = (Decimal(rng.randint(low * 100, high * 100)) / 100).quantize(Decimal("0.01"))
        items.append((description, quantity, unit_price, _quantize(quantity * unit_price, lang)))
    return items


def build_spec(lang: str, index: int, rng: random.Random) -> InvoiceSpec:
    loc = LOCALES[lang]
    vendor_name, vendor_lines, initials = rng.choice(loc["vendors"])
    customer_name, customer_lines = rng.choice(loc["customers"])
    invoice_date = date(2025, 1, 1) + timedelta(days=rng.randint(0, 660))
    days = rng.choice(PAYMENT_DAYS)
    items = _make_items(lang, rng)
    subtotal = sum((item[3] for item in items), Decimal(0))
    tax_amount = _quantize(subtotal * loc["vat_rate"] / 100, lang)
    if lang == "ja":
        bank, branch = rng.choice(loc["banks"])
        iban = None
        bank_lines = (label_value(lang, loc["labels"]["bank"], f"{bank} {branch} 普通 {_digits(rng, 7)}"),)
    else:
        bank = rng.choice(loc["banks"])
        iban = make_iban(loc["country"], rng, bank[2] if len(bank) > 2 else "")
        bank_lines = (label_value(lang, loc["labels"]["bank"], bank[0]),
                      f"{label_value(lang, 'IBAN', group_iban(iban))}   {label_value(lang, 'BIC', bank[1])}")
    template_offset = sum(map(ord, lang)) % len(TEMPLATES)
    return InvoiceSpec(
        doc_id=f"synth_{lang}_{index:03d}",
        lang=lang,
        template=TEMPLATES[(index + template_offset) % len(TEMPLATES)],
        accent=colors.HexColor(rng.choice(ACCENTS)),
        logo_shape=rng.choice(LOGO_SHAPES),
        vendor_name=vendor_name,
        vendor_lines=vendor_lines,
        initials=initials,
        vendor_tax_id=make_vat_id(loc["country"], rng),
        customer_name=customer_name,
        customer_lines=customer_lines,
        number=loc["number"].format(year=invoice_date.year, seq=rng.randint(12, 4800)),
        invoice_date=invoice_date,
        due_date=invoice_date + timedelta(days=days),
        date_variant=rng.randrange(len(DATE_FORMATS[lang])),
        items=items,
        subtotal=subtotal,
        tax_amount=tax_amount,
        total=subtotal + tax_amount,
        vat_rate=loc["vat_rate"],
        iban=iban,
        bank_lines=bank_lines,
        terms=loc["terms"].format(days=days),
    )


def gold_for(spec: InvoiceSpec) -> dict:
    joiner = " " if spec.lang == "ja" else ", "
    return Invoice(
        vendor_name=spec.vendor_name,
        vendor_address=joiner.join(spec.vendor_lines),
        vendor_tax_id=spec.vendor_tax_id,
        customer_name=spec.customer_name,
        invoice_number=spec.number,
        invoice_date=spec.invoice_date.isoformat(),
        due_date=spec.due_date.isoformat(),
        currency=spec.locale["currency"],
        line_items=[LineItem(description=d, quantity=float(q), unit_price=float(u), total=float(t))
                    for d, q, u, t in spec.items],
        subtotal=float(spec.subtotal),
        tax_rate=float(spec.vat_rate),
        tax_amount=float(spec.tax_amount),
        total=float(spec.total),
        iban=spec.iban,
        payment_terms=spec.terms,
    ).model_dump()


def label_value(lang: str, label: str, value: str) -> str:
    if lang == "ja":
        return f"{label}：{value}"
    return f"{label} : {value}" if lang == "fr" else f"{label}: {value}"


def _text(c: Canvas, x: float, y: float, text: str, font: str, size: float, color=INK, align: str = "left",
          max_width: float | None = None) -> None:
    if max_width is not None:
        while size > 6 and pdfmetrics.stringWidth(text, font, size) > max_width:
            size -= 0.25
    c.setFont(font, size)
    c.setFillColor(color)
    if align == "right":
        c.drawRightString(x, y, text)
    elif align == "center":
        c.drawCentredString(x, y, text)
    else:
        c.drawString(x, y, text)


def _logo(c: Canvas, x: float, y: float, size: float, spec: InvoiceSpec, fill=None, ink=colors.white) -> None:
    c.setFillColor(fill or spec.accent)
    if spec.logo_shape == "circle":
        c.circle(x + size / 2, y + size / 2, size / 2, stroke=0, fill=1)
    elif spec.logo_shape == "round":
        c.roundRect(x, y, size, size, size * 0.22, stroke=0, fill=1)
    else:
        c.rect(x, y, size, size, stroke=0, fill=1)
    _text(c, x + size / 2, y + size / 2 - size * 0.14, spec.initials, "Helvetica-Bold", size * 0.4, ink, "center")


def _meta(spec: InvoiceSpec) -> list[tuple[str, str]]:
    labels = spec.labels
    return [
        (labels["number"], spec.number),
        (labels["date"], format_date(spec.invoice_date, spec.lang, spec.date_variant)),
        (labels["due"], format_date(spec.due_date, spec.lang, spec.date_variant)),
    ]


def _customer_display(spec: InvoiceSpec) -> str:
    return f"{spec.customer_name} 御中" if spec.lang == "ja" else spec.customer_name


def _bill_to(c: Canvas, spec: InvoiceSpec, x: float, y: float, width: float) -> None:
    _text(c, x, y, spec.labels["bill_to"], spec.bold, 9, spec.accent, max_width=width)
    _text(c, x, y - 16, _customer_display(spec), spec.bold, 11.5, max_width=width)
    for i, line in enumerate(spec.customer_lines):
        _text(c, x, y - 31 - 12 * i, line, spec.font, 9, MUTED, max_width=width)


def _draw_items(c: Canvas, spec: InvoiceSpec, style: str, x: float, top: float, width: float) -> float:
    labels = spec.labels
    cell = ParagraphStyle("cell", fontName=spec.font, fontSize=9, leading=11.5, textColor=INK,
                          wordWrap="CJK" if spec.lang == "ja" else None)
    header = [labels["desc"], labels["qty"], labels["unit"], labels["amount"]]
    rows = [[Paragraph(escape(d), cell), format_quantity(q, spec.lang), format_number(u, spec.lang),
             format_number(t, spec.lang)] for d, q, u, t in spec.items]
    table = Table([header, *rows], colWidths=[width - 255, 60, 95, 100])
    commands = [
        ("FONTNAME", (0, 0), (-1, 0), spec.bold),
        ("FONTNAME", (0, 1), (-1, -1), spec.font),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("TEXTCOLOR", (0, 0), (-1, -1), INK),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]
    if style == "grid":
        commands += [("GRID", (0, 0), (-1, -1), 0.6, RULE), ("BACKGROUND", (0, 0), (-1, 0), HEADER_FILL)]
    elif style == "band":
        commands += [
            ("BACKGROUND", (0, 0), (-1, 0), spec.accent),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, ZEBRA_FILL]),
            ("LINEBELOW", (0, -1), (-1, -1), 1, spec.accent),
        ]
    else:
        commands += [
            ("TEXTCOLOR", (0, 0), (-1, 0), MUTED),
            ("LINEBELOW", (0, 0), (-1, 0), 1.2, INK),
            ("LINEBELOW", (0, 1), (-1, -2), 0.4, RULE),
            ("LINEBELOW", (0, -1), (-1, -1), 1.0, INK),
        ]
    table.setStyle(TableStyle(commands))
    _, height = table.wrapOn(c, width, PAGE_H)
    table.drawOn(c, x, top - height)
    return top - height


def _draw_totals(c: Canvas, spec: InvoiceSpec, top: float, style: str) -> None:
    right = PAGE_W - MARGIN
    left = right - 250
    rows = [
        (spec.labels["subtotal"], format_money(spec.subtotal, spec.lang)),
        (spec.locale["tax_label"].format(rate=spec.vat_rate), format_money(spec.tax_amount, spec.lang)),
    ]
    y = top
    for label, value in rows:
        _text(c, left, y, label, spec.font, 9.5, max_width=140)
        _text(c, right, y, value, spec.font, 9.5, align="right", max_width=100)
        y -= 17
    y -= 4
    ink = INK
    if style == "box":
        c.setFillColor(spec.accent)
        c.rect(left - 8, y - 8, right - left + 16, 25, stroke=0, fill=1)
        ink = colors.white
    elif style == "line":
        c.setStrokeColor(INK)
        c.setLineWidth(0.8)
        c.line(left, y + 14, right, y + 14)
    else:
        c.setStrokeColor(INK)
        c.setLineWidth(0.6)
        c.line(left, y - 6, right, y - 6)
        c.line(left, y - 8.5, right, y - 8.5)
    _text(c, left, y, spec.labels["total"], spec.bold, 11.5, ink, max_width=140)
    _text(c, right, y, format_money(spec.total, spec.lang), spec.bold, 11.5, ink, "right", max_width=105)


def _draw_footer(c: Canvas, spec: InvoiceSpec, style: str) -> None:
    lines = [label_value(spec.lang, spec.labels["terms"], spec.terms), *spec.bank_lines]
    width = PAGE_W - 2 * MARGIN
    height = 14 * len(lines) + 30
    if style == "box":
        c.setFillColor(ZEBRA_FILL)
        c.rect(MARGIN, MARGIN, width, height, stroke=0, fill=1)
    elif style == "border":
        c.setStrokeColor(RULE)
        c.setLineWidth(0.8)
        c.rect(MARGIN, MARGIN, width, height, stroke=1, fill=0)
    else:
        c.setStrokeColor(RULE)
        c.setLineWidth(0.8)
        c.line(MARGIN, MARGIN + height, PAGE_W - MARGIN, MARGIN + height)
    y = MARGIN + height - 18
    for line in lines:
        _text(c, MARGIN + 10, y, line, spec.font, 8.5, INK, max_width=width - 20)
        y -= 14
    _text(c, MARGIN + 10, y - 2, spec.labels["thanks"], spec.font, 8.5, MUTED, max_width=width - 20)


def _vendor_block(c: Canvas, spec: InvoiceSpec, x: float, y: float, width: float, align: str,
                  size: float = 13) -> None:
    _text(c, x, y, spec.vendor_name, spec.bold, size, align=align, max_width=width)
    lines = [*spec.vendor_lines, label_value(spec.lang, spec.labels["vat_id"], spec.vendor_tax_id)]
    for i, line in enumerate(lines):
        _text(c, x, y - 15 - 11.5 * i, line, spec.font, 9, MUTED, align, max_width=width)


def _layout_classic(c: Canvas, spec: InvoiceSpec) -> None:
    top = PAGE_H - MARGIN
    _logo(c, MARGIN, top - 50, 50, spec)
    _vendor_block(c, spec, MARGIN + 62, top - 12, 225, "left")
    right = PAGE_W - MARGIN
    _text(c, right, top - 22, spec.labels["invoice"], spec.bold, 24, spec.accent, "right", max_width=190)
    for i, (label, value) in enumerate(_meta(spec)):
        y = top - 50 - 15 * i
        _text(c, right - 205, y, label, spec.bold, 9, MUTED, max_width=95)
        _text(c, right, y, value, spec.font, 9.5, align="right", max_width=105)
    _bill_to(c, spec, MARGIN, top - 125, 300)
    bottom = _draw_items(c, spec, "grid", MARGIN, top - 205, PAGE_W - 2 * MARGIN)
    _draw_totals(c, spec, bottom - 22, "line")
    _draw_footer(c, spec, "rule")


def _layout_band(c: Canvas, spec: InvoiceSpec) -> None:
    band = 96
    c.setFillColor(spec.accent)
    c.rect(0, PAGE_H - band, PAGE_W, band, stroke=0, fill=1)
    joiner = " " if spec.lang == "ja" else ", "
    _text(c, MARGIN, PAGE_H - 40, spec.vendor_name, spec.bold, 17, colors.white, max_width=370)
    _text(c, MARGIN, PAGE_H - 58, joiner.join(spec.vendor_lines), spec.font, 9, colors.white, max_width=370)
    _text(c, MARGIN, PAGE_H - 72, label_value(spec.lang, spec.labels["vat_id"], spec.vendor_tax_id), spec.font, 9,
          colors.white, max_width=370)
    _logo(c, PAGE_W - MARGIN - 56, PAGE_H - band + 20, 56, spec, fill=colors.white, ink=spec.accent)
    _text(c, MARGIN, PAGE_H - band - 40, spec.labels["invoice"], spec.bold, 22, spec.accent, max_width=230)
    for i, (label, value) in enumerate(_meta(spec)):
        y = PAGE_H - band - 64 - 15 * i
        _text(c, MARGIN, y, label, spec.bold, 9, MUTED, max_width=110)
        _text(c, MARGIN + 118, y, value, spec.font, 9.5, max_width=140)
    _bill_to(c, spec, PAGE_W / 2 + 30, PAGE_H - band - 34, PAGE_W / 2 - MARGIN - 30)
    bottom = _draw_items(c, spec, "band", MARGIN, PAGE_H - band - 130, PAGE_W - 2 * MARGIN)
    _draw_totals(c, spec, bottom - 24, "box")
    _draw_footer(c, spec, "box")


def _layout_minimal(c: Canvas, spec: InvoiceSpec) -> None:
    top = PAGE_H - MARGIN
    right = PAGE_W - MARGIN
    _logo(c, right - 44, top - 44, 44, spec)
    _vendor_block(c, spec, right - 56, top - 12, 240, "right", size=12)
    _text(c, MARGIN, top - 30, spec.labels["invoice"], spec.bold, 28, INK, max_width=200)
    row_top = top - 92
    c.setStrokeColor(RULE)
    c.setLineWidth(0.8)
    c.line(MARGIN, row_top, right, row_top)
    c.line(MARGIN, row_top - 42, right, row_top - 42)
    column = (right - MARGIN) / 3
    for i, (label, value) in enumerate(_meta(spec)):
        x = MARGIN + column * i
        _text(c, x, row_top - 15, label, spec.font, 8, MUTED, max_width=column - 10)
        _text(c, x, row_top - 32, value, spec.bold, 10.5, max_width=column - 10)
    _bill_to(c, spec, MARGIN, row_top - 68, 320)
    bottom = _draw_items(c, spec, "rules", MARGIN, row_top - 150, PAGE_W - 2 * MARGIN)
    _draw_totals(c, spec, bottom - 22, "double")
    _draw_footer(c, spec, "border")


LAYOUTS = {"classic": _layout_classic, "band": _layout_band, "minimal": _layout_minimal}


def register_fonts() -> None:
    if CJK_FONT not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(UnicodeCIDFont(CJK_FONT))


def render_pdf(spec: InvoiceSpec, path: Path) -> None:
    register_fonts()
    c = Canvas(str(path), pagesize=A4, invariant=1)
    c.setTitle(f"{spec.labels['invoice']} {spec.number}")
    c.setFillColor(colors.white)
    c.rect(0, 0, PAGE_W, PAGE_H, stroke=0, fill=1)
    LAYOUTS[spec.template](c, spec)
    c.showPage()
    c.save()


def rasterize(pdf_path: Path, dpi: int = DPI) -> Image.Image:
    pdf = pdfium.PdfDocument(str(pdf_path))
    try:
        page = pdf[0]
        image = page.render(scale=dpi / 72).to_pil().convert("RGB")
        page.close()
    finally:
        pdf.close()
    return image


def degrade(image: Image.Image, rng: random.Random) -> tuple[Image.Image, int]:
    """Scanner look: paper tint, slight skew, blur, sensor noise. Returns the image and a JPEG quality."""
    shade = rng.randint(226, 244)
    tint = (shade, shade - rng.randint(0, 3), shade - rng.randint(3, 10))
    out = ImageChops.multiply(image.convert("RGB"), Image.new("RGB", image.size, tint))
    out = out.rotate(rng.uniform(-1.5, 1.5), resample=Image.Resampling.BICUBIC, fillcolor=tint)
    out = out.filter(ImageFilter.GaussianBlur(rng.uniform(0.3, 0.8)))
    noise = np.random.default_rng(rng.getrandbits(32)).normal(0.0, rng.uniform(2.0, 5.0), out.size[::-1])
    pixels = np.asarray(out, dtype=np.float32) + noise[..., None]
    return Image.fromarray(np.clip(pixels, 0, 255).astype(np.uint8)), rng.randint(55, 80)


def generate(n_per_lang: int = 8, langs: tuple[str, ...] = LANGS, seed: int = 7,
             out_dir: Path = DATA_PROCESSED / DATASET) -> list[dict]:
    """Render n_per_lang invoices per language and write out_dir/samples.jsonl. Deterministic per seed."""
    out_dir = Path(out_dir)
    unknown = [lang for lang in langs if lang not in LOCALES]
    if unknown:
        raise ValueError(f"unsupported languages: {unknown}")
    records = []
    for lang in langs:
        lang_dir = out_dir / lang
        lang_dir.mkdir(parents=True, exist_ok=True)
        for index in range(n_per_lang):
            rng = random.Random(f"{seed}:{lang}:{index}")
            spec = build_spec(lang, index, rng)
            gold = gold_for(spec)
            failed = [r for r in validate("invoice", gold) if r.passed is False]
            if failed:
                raise RuntimeError(f"{spec.doc_id} gold fails validation: {[r.message for r in failed]}")
            pdf_path = lang_dir / f"{spec.doc_id}.pdf"
            render_pdf(spec, pdf_path)
            clean = rasterize(pdf_path)
            clean.save(lang_dir / f"{spec.doc_id}.png")
            noisy, quality = degrade(clean, rng)
            jpg_path = lang_dir / f"{spec.doc_id}.jpg"
            noisy.save(jpg_path, "JPEG", quality=quality)
            records.append({
                "doc_id": spec.doc_id,
                "dataset": DATASET,
                "doc_type": "invoice",
                "language": lang,
                "split": "test",
                "image_paths": [str(jpg_path.resolve())],
                "pdf_path": str(pdf_path.resolve()),
                "text": None,
                "gold": gold,
            })
    with (out_dir / "samples.jsonl").open("w", encoding="utf-8") as fh:
        for record in records:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    return records
