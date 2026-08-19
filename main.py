import os
import io
import re
import json
import base64
import datetime
import urllib.parse
import webbrowser
import flet as ft
from supabase import create_client, Client
from google import genai
from google.genai import types
import PIL.Image

import arabic_reshaper
from bidi.algorithm import get_display

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# --- إعدادات Supabase السحابية ---
SUPABASE_URL = "https://qygefxheemltsaampjbh.supabase.co"
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "sb_publishable_-ra_ou-i5SnqG-aItNPJzg_RtkWYYyC")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- إعدادات الذكاء الاصطناعي (Gemini الحديث) ---
_k_parts = ["AQ.Ab8RN6KIkzTRIuUh", "7FC4cCYVxsS419zLlFu", "RNh6oxaLO5KThzQ"]
DEFAULT_GEMINI_KEY = "".join(_k_parts)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", DEFAULT_GEMINI_KEY)

ai_client = None
if GEMINI_API_KEY:
    try:
        ai_client = genai.Client(api_key=GEMINI_API_KEY)
    except Exception:
        ai_client = None


def reshape_ar(text):
    if not text:
        return ""
    text_str = str(text)
    reshaped = arabic_reshaper.reshape(text_str)
    return get_display(reshaped)


async def main(page: ft.Page):
    page.title = "Triple H - إدارة الشحنات والمرتجعات"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.rtl = True
    page.scroll = "auto"
    page.padding = 10

    today_str = datetime.date.today().strftime("%Y-%m-%d")

    selected_order_id = {"id": None}
    current_orders_data = {"rows": []}

    stat_shipping = ft.Text("0.00 EGP", size=13, weight="bold", color="#1d4ed8")
    stat_items = ft.Text("0.00 EGP", size=13, weight="bold", color="#b45309")
    stat_total = ft.Text("0.00 EGP", size=14, weight="bold", color="#047857")
    stat_count = ft.Text("0", size=15, weight="bold", color="#1e293b")

    session_date_in = ft.TextField(label="تاريخ الجلسة (YYYY-MM-DD)", value=today_str, text_align=ft.TextAlign.RIGHT)
    company_in = ft.TextField(label="اسم الشركة / المتجر الراسل", value="عام", text_align=ft.TextAlign.RIGHT)
    code_in = ft.TextField(label="كود الشحنة (تلقائي/يدوي)", text_align=ft.TextAlign.RIGHT)
    name_in = ft.TextField(label="اسم العميل (المستلم)", text_align=ft.TextAlign.RIGHT)
    phone_in = ft.TextField(label="رقم الهاتف", keyboard_type=ft.KeyboardType.PHONE, text_align=ft.TextAlign.RIGHT)
    address_in = ft.TextField(label="العنوان بالتفصيل", text_align=ft.TextAlign.RIGHT)
    courier_in = ft.TextField(label="اسم المندوب", text_align=ft.TextAlign.RIGHT)
    
    price_in = ft.TextField(label="سعر المنتج (EGP)", keyboard_type=ft.KeyboardType.NUMBER, text_align=ft.TextAlign.RIGHT, value="0", expand=True)
    fee_in = ft.TextField(label="الشحن (EGP)", keyboard_type=ft.KeyboardType.NUMBER, text_align=ft.TextAlign.RIGHT, value="0", expand=True)
    notes_in = ft.TextField(label="ملاحظات إضافية", text_align=ft.TextAlign.RIGHT)

    status_dd = ft.Dropdown(
        label="حالة الشحنة",
        value="قيد الانتظار",
        options=[
            ft.dropdown.Option("قيد الانتظار"),
            ft.dropdown.Option("مع المندوب"),
            ft.dropdown.Option("تم التسليم بنجاح"),
            ft.dropdown.Option("لم يتم الرد"),
            ft.dropdown.Option("تم الإلغاء / مرتجع"),
        ]
    )

    filter_session_dd = ft.Dropdown(
        label="📅 اختيار الجلسة",
        value=f"جلسة اليوم ({today_str})",
        expand=True,
        options=[
            ft.dropdown.Option(f"جلسة اليوم ({today_str})"),
            ft.dropdown.Option("كل الجلسات")
        ]
    )

    filter_company_dd = ft.Dropdown(
        label="🏢 الشركة",
        value="كل الشركات",
        width=130,
        options=[
            ft.dropdown.Option("كل الشركات"),
            ft.dropdown.Option("عام")
        ]
    )

    search_in = ft.TextField(label="🔍 بحث (كود، اسم، هاتف، شركة، مندوب)", text_align=ft.TextAlign.RIGHT, expand=True)
    
    filter_status_dd = ft.Dropdown(
        label="الحالة",
        value="كل الحالات",
        width=125,
        options=[
            ft.dropdown.Option("كل الحالات"),
            ft.dropdown.Option("قيد الانتظار"),
            ft.dropdown.Option("مع المندوب"),
            ft.dropdown.Option("تم التسليم بنجاح"),
            ft.dropdown.Option("لم يتم الرد"),
            ft.dropdown.Option("تم الإلغاء / مرتجع"),
        ]
    )

    loading_indicator = ft.ProgressBar(visible=False, color="#3b82f6")
    orders_list = ft.Column(spacing=10)

    btn_add = ft.Button("➕ إضافة أوردر", icon=ft.Icons.ADD, bgcolor="#10b981", color="white", height=45, expand=True)
    btn_update = ft.Button("✏️ حفظ التعديل", icon=ft.Icons.CHECK, bgcolor="#3b82f6", color="white", height=45, visible=False, expand=True)
    btn_delete = ft.Button("🗑️ حذف", icon=ft.Icons.DELETE, bgcolor="#ef4444", color="white", height=45, visible=False)
    btn_clear = ft.OutlinedButton("🔄 تفريغ", height=45)

    form_title = ft.Text(" بيانات الأوردر ", weight="bold", size=16, color="#0f766e")

    def show_msg(text, color="green"):
        snack = ft.SnackBar(ft.Text(text), bgcolor=color)
        page.overlay.append(snack)
        snack.open = True
        page.update()

    def update_mobile_sessions():
        try:
            res = supabase.table("orders").select("session_date, company_name").order("session_date", desc=True).execute()
            dates = []
            comps = ["كل الشركات"]
            for item in (res.data or []):
                d = item.get("session_date")
                c = item.get("company_name")
                if d and d not in dates:
                    dates.append(d)
                if c and c not in comps:
                    comps.append(c)

            opts = [
                ft.dropdown.Option(f"جلسة اليوم ({today_str})"),
                ft.dropdown.Option("كل الجلسات")
            ]
            for d in dates:
                if d != today_str:
                    opts.append(ft.dropdown.Option(d))

            filter_session_dd.options = opts
            filter_company_dd.options = [ft.dropdown.Option(x) for x in comps]
            page.update()
        except Exception:
            pass

    def clear_fields(e=None):
        selected_order_id["id"] = None
        session_date_in.value = today_str
        company_in.value = "عام"
        code_in.value = ""
        name_in.value = ""
        phone_in.value = ""
        address_in.value = ""
        courier_in.value = ""
        price_in.value = "0"
        fee_in.value = "0"
        notes_in.value = ""
        status_dd.value = "قيد الانتظار"

        form_title.value = " بيانات الأوردر "
        form_title.color = "#0f766e"
        btn_add.visible = True
        btn_update.visible = False
        btn_delete.visible = False
        page.update()

    def select_order_for_edit(item):
        selected_order_id["id"] = item.get("id")
        session_date_in.value = str(item.get("session_date") or today_str)
        company_in.value = str(item.get("company_name") or "عام")
        code_in.value = str(item.get("order_code") or "")
        name_in.value = str(item.get("customer_name") or "")
        phone_in.value = str(item.get("phone") or "")
        address_in.value = str(item.get("address") or "")
        courier_in.value = str(item.get("courier") or "")
        price_in.value = str(item.get("item_price") or 0)
        fee_in.value = str(item.get("shipping_fee") or 0)
        status_dd.value = str(item.get("status") or "قيد الانتظار")
        notes_in.value = str(item.get("notes") or "")

        form_title.value = f"✏️ تعديل أوردر كود: #{code_in.value}"
        form_title.color = "#2563eb"
        btn_add.visible = False
        btn_update.visible = True
        btn_delete.visible = True

        form_tile.expanded = True
        page.update()
        show_msg(f"تم اختيار الأوردر #{code_in.value} للتعديل", color="#2563eb")

    async def open_whatsapp_customer(item):
        phone = re.sub(r'\D', '', str(item.get("phone") or ""))
        if not phone:
            show_msg("لا يوجد رقم هاتف مسجل!", color="red")
            return

        if phone.startswith("01"):
            phone = "2" + phone
        elif phone.startswith("1") and len(phone) == 10:
            phone = "20" + phone
        elif not phone.startswith("20") and len(phone) >= 10:
            phone = "20" + phone

        name = item.get("customer_name") or "العميل العزيز"
        code = item.get("order_code") or ""
        courier = item.get("courier") or "مندوبنا"
        msg = f"مرحباً {name}، شحنتك رقم #{code} في الطريق إليك مع المندوب: {courier}. برجاء التواجد للاستلام."
        url = f"https://wa.me/{phone}?text={urllib.parse.quote(msg)}"
        
        try:
            webbrowser.open(url)
        except Exception:
            pass

    # --- تصدير كشف المرتجعات PDF على الموبايل ---
    def export_returns_pdf_mobile(e=None):
        return_rows = [r for r in current_orders_data["rows"] if r.get('status') == 'تم الإلغاء / مرتجع']
        if not return_rows:
            show_msg("لا توجد أوردرات مرتجعة معروضة حالياً لتصديرها!", color="orange")
            return

        company_name = filter_company_dd.value
        if company_name == "كل الشركات":
            company_name = "مرتجعات الشركات المجمعة"

        try:
            downloads_path = os.path.join(os.path.expanduser("~"), "Downloads")
            if not os.path.exists(downloads_path):
                downloads_path = os.getcwd()

            time_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            file_name = f"Triple_H_Returns_{time_str}.pdf"
            file_path = os.path.join(downloads_path, file_name)

            font_candidates = [
                "C:\\Windows\\Fonts\\arial.ttf",
                "C:\\Windows\\Fonts\\tahoma.ttf",
                "/system/fonts/NotoNaskhArabic-Regular.ttf",
                "/system/fonts/NotoSansArabic-Regular.ttf"
            ]

            font_name, font_bold_name = 'Helvetica', 'Helvetica-Bold'
            for fc in font_candidates:
                if os.path.exists(fc):
                    try:
                        pdfmetrics.registerFont(TTFont('ArabicFont', fc))
                        font_name, font_bold_name = 'ArabicFont', 'ArabicFont'
                        break
                    except Exception:
                        continue

            doc = SimpleDocTemplate(file_path, pagesize=A4, rightMargin=15, leftMargin=15, topMargin=15, bottomMargin=15)
            elements = []
            styles = getSampleStyleSheet()

            title_style = ParagraphStyle(
                name="TitleStyleRetMob",
                fontName=font_bold_name,
                fontSize=14,
                leading=18,
                alignment=1,
                textColor=colors.HexColor("#c2410c")
            )
            elements.append(Paragraph(reshape_ar(f"Triple H - كشف تسليم مرتجعات ({company_name})"), title_style))
            elements.append(Spacer(1, 10))

            table_data = [[
                reshape_ar("سبب الإلغاء / ملاحظات"),
                reshape_ar("سعر البضاعة"),
                reshape_ar("رقم الهاتف"),
                reshape_ar("اسم العميل"),
                reshape_ar("الشركة / المتجر"),
                reshape_ar("كود الشحنة")
            ]]

            total_goods_sum = 0.0
            for r in return_rows:
                item_p = float(r.get('item_price') or 0)
                total_goods_sum += item_p
                table_data.append([
                    reshape_ar(str(r.get('notes') or '-')),
                    f"{item_p:.2f} EGP",
                    str(r.get('phone') or ''),
                    reshape_ar(str(r.get('customer_name') or '')[:20]),
                    reshape_ar(str(r.get('company_name') or '')[:16]),
                    str(r.get('order_code') or '')
                ])

            table_data.append([
                reshape_ar("إجمالي قيمة البضاعة المستردة"),
                f"{total_goods_sum:.2f} EGP",
                "", "", "", ""
            ])

            t = Table(table_data, colWidths=[175, 85, 80, 95, 75, 55])
            t.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#c2410c')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), font_bold_name),
                ('FONTNAME', (0, 1), (-1, -1), font_name),
                ('FONTSIZE', (0, 0), (-1, 0), 8.5),
                ('FONTSIZE', (0, 1), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 5),
                ('TOPPADDING', (0, 0), (-1, -1), 4),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#fed7aa')),
                ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#ffedd5')),
                ('FONTNAME', (0, -1), (-1, -1), font_bold_name),
                ('TEXTCOLOR', (1, -1), (1, -1), colors.HexColor('#c2410c')),
            ]))

            elements.append(t)
            doc.build(elements)
            show_msg(f"تم حفظ كشف المرتجعات PDF بنجاح في التنزيلات ✅\n{file_name}", color="#c2410c")

        except Exception as ex:
            show_msg(f"خطأ أثناء تصدير PDF: {ex}", color="red")

    # --- تصدير كشف تسليم المندوب PDF على الموبايل ---
    def export_courier_pdf_mobile(e=None):
        if not current_orders_data["rows"]:
            show_msg("لا توجد أوردرات لتصديرها!", color="orange")
            return

        try:
            downloads_path = os.path.join(os.path.expanduser("~"), "Downloads")
            if not os.path.exists(downloads_path):
                downloads_path = os.getcwd()

            time_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            file_name = f"Triple_H_Manifest_{time_str}.pdf"
            file_path = os.path.join(downloads_path, file_name)

            font_candidates = [
                "C:\\Windows\\Fonts\\arial.ttf",
                "C:\\Windows\\Fonts\\tahoma.ttf",
                "/system/fonts/NotoNaskhArabic-Regular.ttf",
                "/system/fonts/NotoSansArabic-Regular.ttf"
            ]

            font_name, font_bold_name = 'Helvetica', 'Helvetica-Bold'
            for fc in font_candidates:
                if os.path.exists(fc):
                    try:
                        pdfmetrics.registerFont(TTFont('ArabicFont', fc))
                        font_name, font_bold_name = 'ArabicFont', 'ArabicFont'
                        break
                    except Exception:
                        continue

            doc = SimpleDocTemplate(file_path, pagesize=A4, rightMargin=15, leftMargin=15, topMargin=15, bottomMargin=15)
            elements = []
            styles = getSampleStyleSheet()

            sess_info = filter_session_dd.value or "جميع الجلسات"
            title_style = ParagraphStyle(name="TitleStyleMob", fontName=font_bold_name, fontSize=14, leading=18, alignment=1, textColor=colors.HexColor("#1e293b"))
            elements.append(Paragraph(reshape_ar(f"Triple H - كشف تسليم شحنات المندوب ({sess_info})"), title_style))
            elements.append(Spacer(1, 10))

            table_data = [[
                reshape_ar("الملاحظات"),
                reshape_ar("المطلوب"),
                reshape_ar("الشحن"),
                reshape_ar("سعر المنتج"),
                reshape_ar("الهاتف"),
                reshape_ar("العنوان"),
                reshape_ar("الشركة"),
                reshape_ar("العميل"),
                reshape_ar("الكود")
            ]]

            total_items_sum, total_shipping_sum, grand_total_sum = 0.0, 0.0, 0.0

            for r in current_orders_data["rows"]:
                item_p = float(r.get('item_price') or 0)
                ship_f = float(r.get('shipping_fee') or 0)
                tot = item_p + ship_f
                total_items_sum += item_p
                total_shipping_sum += ship_f
                grand_total_sum += tot

                table_data.append([
                    reshape_ar(str(r.get('notes') or '-')),
                    f"{tot:.2f}",
                    f"{ship_f:.2f}",
                    f"{item_p:.2f}",
                    str(r.get('phone') or ''),
                    reshape_ar(str(r.get('address') or '')[:18]),
                    reshape_ar(str(r.get('company_name') or '')[:12]),
                    reshape_ar(str(r.get('customer_name') or '')[:15]),
                    str(r.get('order_code') or '')
                ])

            table_data.append([
                reshape_ar("إجمالي الجلسة"),
                f"{grand_total_sum:.2f} EGP",
                f"{total_shipping_sum:.2f}",
                f"{total_items_sum:.2f}",
                "", "", "", "", ""
            ])

            t = Table(table_data, colWidths=[65, 65, 45, 50, 70, 100, 65, 65, 45])
            t.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e293b')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), font_bold_name),
                ('FONTNAME', (0, 1), (-1, -1), font_name),
                ('FONTSIZE', (0, 0), (-1, 0), 8),
                ('FONTSIZE', (0, 1), (-1, -2), 7.5),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 5),
                ('TOPPADDING', (0, 0), (-1, -1), 4),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
                ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#f1f5f9')),
                ('FONTNAME', (0, -1), (-1, -1), font_bold_name),
                ('TEXTCOLOR', (1, -1), (1, -1), colors.HexColor('#047857')),
            ]))

            elements.append(t)
            doc.build(elements)
            show_msg(f"تم حفظ كشف التسليم PDF بنجاح في التنزيلات ✅\n{file_name}", color="#15803d")

        except Exception as ex:
            show_msg(f"خطأ أثناء تصدير PDF: {ex}", color="red")

    def process_image_with_ai(file_path=None, file_bytes=None):
        if not ai_client:
            show_msg("مفتاح Gemini غير مفعل!", color="red")
            return

        loading_indicator.visible = True
        page.update()

        try:
            if file_bytes:
                img = PIL.Image.open(io.BytesIO(file_bytes)).convert("RGB")
            elif file_path:
                img = PIL.Image.open(file_path).convert("RGB")
            else:
                show_msg("لم يتم العثور على ملف الصورة", color="red")
                return

            img.thumbnail((1024, 1024), PIL.Image.Resampling.LANCZOS)
            buffered = io.BytesIO()
            img.save(buffered, format="JPEG", quality=80, optimize=True)
            img_bytes_compressed = buffered.getvalue()

            prompt_text = """
            أنت خبير قراءة واستخراج بيانات بوالص وشحنات الشحن والتوصيل المكتوبة باللغة العربية (خط يد أو مطبوعة).
            استخرج البيانات التالية بدقة شديدة على شكل JSON فقط:
            {
                "company_name": "اسم الشركة أو المتجر الراسل إن وجد وإلا اجعلها عام",
                "order_code": "رقم البوليصة أو كود الشحنة إن وجد",
                "customer_name": "اسم العميل أو المستلم",
                "phone": "رقم الهاتف أو الموبايل",
                "address": "العنوان بالتفصيل المحافظة والمنطقة والشارع",
                "item_price": 0,
                "shipping_fee": 0,
                "notes": "أي ملاحظات إضافية على الطرد أو المحتويات"
            }
            إذا لم تجد قيمة لحقل معين اجعل قيمته نص فارغ "" أو 0 للمبالغ.
            """

            response = ai_client.models.generate_content(
                model='gemini-2.5-flash',
                contents=[
                    types.Part.from_bytes(data=img_bytes_compressed, mime_type='image/jpeg'),
                    prompt_text
                ],
                config=types.GenerateContentConfig(
                    temperature=0.0,
                    response_mime_type="application/json"
                )
            )

            raw_text = response.text.strip()
            json_match = re.search(r'\{.*\}', raw_text, re.DOTALL)
            clean_json_str = json_match.group(0) if json_match else raw_text
            data = json.loads(clean_json_str)

            if data.get("company_name"):
                company_in.value = str(data.get("company_name"))
            if data.get("order_code"):
                code_in.value = str(data.get("order_code"))
            if data.get("customer_name"):
                name_in.value = str(data.get("customer_name"))
            if data.get("phone"):
                phone_in.value = str(data.get("phone"))
            if data.get("address"):
                address_in.value = str(data.get("address"))
            if data.get("item_price"):
                price_in.value = str(data.get("item_price"))
            if data.get("shipping_fee"):
                fee_in.value = str(data.get("shipping_fee"))
            if data.get("notes"):
                notes_in.value = str(data.get("notes"))

            show_msg("تم استخراج بيانات الشحنة والشركة بنجاح! 🎯")

        except Exception as ex:
            show_msg("خطأ في قراءة الصورة: " + str(ex), color="red")
        finally:
            loading_indicator.visible = False
            page.update()

    async def pick_file_click(e):
        try:
            files = await ft.FilePicker().pick_files(
                allow_multiple=False,
                allowed_extensions=["png", "jpg", "jpeg"]
            )
            if files:
                for f in files:
                    process_image_with_ai(
                        file_path=getattr(f, 'path', None),
                        file_bytes=getattr(f, 'bytes', None)
                    )
                    break
        except Exception as ex:
            show_msg("خطأ في مستعرض الصور: " + str(ex), color="red")

    def load_orders(e=None):
        orders_list.controls.clear()
        selected_sess = filter_session_dd.value
        selected_comp = filter_company_dd.value
        selected_status = filter_status_dd.value
        search_txt = search_in.value.strip() if search_in.value else ""

        try:
            query = supabase.table("orders").select("*")

            if selected_sess == f"جلسة اليوم ({today_str})":
                query = query.eq("session_date", today_str)
            elif selected_sess and selected_sess != "كل الجلسات":
                query = query.eq("session_date", selected_sess)

            if selected_comp and selected_comp != "كل الشركات":
                query = query.eq("company_name", selected_comp)

            if selected_status != "كل الحالات":
                query = query.eq("status", selected_status)

            if search_txt:
                pattern = "%" + search_txt + "%"
                filter_str = (
                    "order_code.ilike." + pattern + ","
                    "customer_name.ilike." + pattern + ","
                    "phone.ilike." + pattern + ","
                    "company_name.ilike." + pattern + ","
                    "courier.ilike." + pattern
                )
                query = query.or_(filter_str)

            res = query.order("id", desc=True).execute()
            rows = res.data or []
            current_orders_data["rows"] = rows

            total_items = sum(float(r.get("item_price") or 0) for r in rows)
            total_shipping = sum(float(r.get("shipping_fee") or 0) for r in rows)
            grand_total = total_items + total_shipping

            stat_shipping.value = f"{total_shipping:,.2f} EGP"
            stat_items.value = f"{total_items:,.2f} EGP"
            stat_total.value = f"{grand_total:,.2f} EGP"
            stat_count.value = str(len(rows))

            if not rows:
                orders_list.controls.append(
                    ft.Container(
                        content=ft.Text("لا توجد أوردرات مطابقة للبحث", color="grey", size=15),
                        alignment=ft.Alignment(0, 0),
                        padding=20
                    )
                )
            else:
                for item in rows:
                    status = item.get('status', 'قيد الانتظار')
                    
                    bg_col = (
                        "#fef3c7" if status == "قيد الانتظار"
                        else ("#dbeafe" if status == "مع المندوب"
                        else ("#dcfce7" if status == "تم التسليم بنجاح"
                        else ("#ffedd5" if status == "لم يتم الرد"
                        else "#fee2e2")))
                    )
                    
                    price = float(item.get('item_price') or 0)
                    fee = float(item.get('shipping_fee') or 0)
                    total = price + fee

                    async def handle_wa(e, itm=item):
                        await open_whatsapp_customer(itm)

                    card = ft.Card(
                        elevation=3,
                        content=ft.Container(
                            bgcolor=bg_col,
                            padding=12,
                            border_radius=8,
                            content=ft.Column([
                                ft.Row([
                                    ft.Text("📦 كود: " + str(item.get('order_code', '')), weight="bold", size=15),
                                    ft.Container(
                                        content=ft.Text(f"🏢 {item.get('company_name', 'عام')}", size=11, weight="bold", color="#1e40af"),
                                        bgcolor="white", padding=4, border_radius=4
                                    ),
                                    ft.Container(
                                        content=ft.Text(status, size=11, weight="bold"),
                                        bgcolor="white", padding=5, border_radius=4
                                    )
                                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),

                                ft.Text("👤 العميل: " + str(item.get('customer_name', '')), weight="w600"),
                                ft.Text("📞 الهاتف: " + str(item.get('phone', ''))),
                                ft.Text("📍 العنوان: " + str(item.get('address', ''))),
                                ft.Text("🚚 المندوب: " + str(item.get('courier', ''))),
                                ft.Divider(),
                                ft.Row([
                                    ft.Text(f"📦 المنتج: {price:.2f} ج.م", size=12),
                                    ft.Text(f"🚚 الشحن: {fee:.2f} ج.م", size=12),
                                    ft.Text(f"💵 المطلوب: {total:.2f} ج.م", weight="bold", size=13, color="#047857"),
                                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                                ft.Text("📝 ملاحظات: " + str(item.get('notes', '-')), size=11, italic=True),

                                ft.Row([
                                    ft.Button(
                                        "💬 واتساب",
                                        icon=ft.Icons.CHAT,
                                        bgcolor="#25d366",
                                        color="white",
                                        height=36,
                                        on_click=handle_wa
                                    ),
                                    ft.OutlinedButton(
                                        "✏️ تعديل",
                                        icon=ft.Icons.EDIT,
                                        height=36,
                                        on_click=lambda e, itm=item: select_order_for_edit(itm),
                                    )
                                ], alignment=ft.MainAxisAlignment.END)
                            ], spacing=4)
                        )
                    )
                    orders_list.controls.append(card)
            page.update()
        except Exception as err:
            show_msg("خطأ في جلب البيانات: " + str(err), color="red")

    def add_order_click(e):
        if not code_in.value or not name_in.value or not phone_in.value:
            show_msg("يرجى ملء الكود والاسم ورقم الهاتف على الأقل!", color="orange")
            return

        try:
            p_val = float(price_in.value or 0)
            f_val = float(fee_in.value or 0)
        except ValueError:
            show_msg("يرجى إدخال أرقام صحيحة في خانات المبالغ", color="red")
            return

        s_date = session_date_in.value.strip() or today_str
        c_name = company_in.value.strip() or "عام"

        data = {
            "session_date": s_date,
            "company_name": c_name,
            "order_code": code_in.value,
            "customer_name": name_in.value,
            "phone": phone_in.value,
            "address": address_in.value,
            "courier": courier_in.value,
            "item_price": p_val,
            "shipping_fee": f_val,
            "status": status_dd.value,
            "notes": notes_in.value
        }

        try:
            supabase.table("orders").insert(data).execute()
            show_msg("تمت إضافة الشحنة بنجاح ✅")
            clear_fields()
            update_mobile_sessions()
            load_orders()
        except Exception as err:
            show_msg("خطأ أثناء الحفظ (قد يكون الكود مكرراً): " + str(err), color="red")

    def update_order_click(e):
        if not selected_order_id["id"]:
            show_msg("لم يتم تحديد أوردر للتعديل!", color="orange")
            return

        try:
            p_val = float(price_in.value or 0)
            f_val = float(fee_in.value or 0)
        except ValueError:
            show_msg("يرجى إدخال أرقام صحيحة في خانات المبالغ", color="red")
            return

        data = {
            "session_date": session_date_in.value.strip(),
            "company_name": company_in.value.strip() or "عام",
            "order_code": code_in.value,
            "customer_name": name_in.value,
            "phone": phone_in.value,
            "address": address_in.value,
            "courier": courier_in.value,
            "item_price": p_val,
            "shipping_fee": f_val,
            "status": status_dd.value,
            "notes": notes_in.value
        }

        try:
            supabase.table("orders").update(data).eq("id", selected_order_id["id"]).execute()
            show_msg("تم تحديث بيانات الأوردر بنجاح ✅")
            clear_fields()
            update_mobile_sessions()
            load_orders()
        except Exception as err:
            show_msg("فشل التعديل: " + str(err), color="red")

    def delete_order_click(e):
        if not selected_order_id["id"]:
            return

        try:
            supabase.table("orders").delete().eq("id", selected_order_id["id"]).execute()
            show_msg("تم حذف الأوردر بنجاح 🗑️")
            clear_fields()
            update_mobile_sessions()
            load_orders()
        except Exception as err:
            show_msg("فشل الحذف: " + str(err), color="red")

    btn_add.on_click = add_order_click
    btn_update.on_click = update_order_click
    btn_delete.on_click = delete_order_click
    btn_clear.on_click = clear_fields

    search_in.on_change = lambda e: load_orders()
    filter_status_dd.on_change = lambda e: load_orders()
    filter_session_dd.on_change = lambda e: load_orders()
    filter_company_dd.on_change = lambda e: load_orders()

    stats_dashboard = ft.Card(
        elevation=2,
        content=ft.Container(
            bgcolor="white",
            padding=10,
            border_radius=10,
            content=ft.Column([
                ft.Row([
                    ft.Container(
                        expand=True,
                        bgcolor="#eff6ff",
                        padding=8,
                        border_radius=8,
                        content=ft.Column([
                            ft.Text("🚚 أرباح شحن المعروض", size=11, weight="bold", color="#1e40af"),
                            stat_shipping
                        ], alignment=ft.MainAxisAlignment.CENTER)
                    ),
                    ft.Container(
                        expand=True,
                        bgcolor="#fefce8",
                        padding=8,
                        border_radius=8,
                        content=ft.Column([
                            ft.Text("📦 بضاعة الشحنات", size=11, weight="bold", color="#854d0e"),
                            stat_items
                        ], alignment=ft.MainAxisAlignment.CENTER)
                    )
                ]),
                ft.Row([
                    ft.Container(
                        expand=True,
                        bgcolor="#ecfdf5",
                        padding=8,
                        border_radius=8,
                        content=ft.Column([
                            ft.Text("💵 المطلوب تحصيله", size=11, weight="bold", color="#065f46"),
                            stat_total
                        ], alignment=ft.MainAxisAlignment.CENTER)
                    ),
                    ft.Container(
                        expand=True,
                        bgcolor="#f3f4f6",
                        padding=8,
                        border_radius=8,
                        content=ft.Column([
                            ft.Text("🔢 عدد الأوردرات", size=11, weight="bold", color="#374151"),
                            stat_count
                        ], alignment=ft.MainAxisAlignment.CENTER)
                    )
                ])
            ])
        )
    )

    form_tile = ft.ExpansionTile(
        title=form_title,
        controls=[
            ft.Container(
                padding=10,
                content=ft.Column([
                    ft.Button(
                        "📷 تصوير / رفع صورة البوليصة (AI Scan)",
                        icon=ft.Icons.CAMERA_ALT,
                        bgcolor="#3b82f6",
                        color="white",
                        height=45,
                        on_click=pick_file_click
                    ),
                    loading_indicator,
                    ft.Divider(),
                    session_date_in, company_in, code_in, name_in, phone_in, address_in, courier_in,
                    ft.Row([price_in, fee_in]),
                    status_dd, notes_in,
                    ft.Row([btn_add, btn_update, btn_delete, btn_clear])
                ])
            )
        ]
    )

    page.add(
        ft.AppBar(title=ft.Text("📦 Triple H - إدارة الشحنات والمرتجعات", color="white", weight="bold"), bgcolor="#1e293b", center_title=True),
        ft.Container(
            content=ft.Column([
                stats_dashboard,
                form_tile,
                ft.Divider(),
                ft.Row([
                    filter_session_dd,
                    filter_company_dd
                ]),
                ft.Row([
                    ft.Button("📦 كشف مرتجعات PDF", icon=ft.Icons.PICTURE_AS_PDF, bgcolor="#ea580c", color="white", on_click=export_returns_pdf_mobile, expand=True),
                    ft.Button("📄 كشف تسليم PDF", icon=ft.Icons.PICTURE_AS_PDF, bgcolor="#dc2626", color="white", on_click=export_courier_pdf_mobile, expand=True),
                ]),
                ft.Row([search_in, filter_status_dd]),
                ft.Row([
                    ft.Text("📋 قائمة الشحنات", size=15, weight="bold"),
                    ft.IconButton(icon=ft.Icons.REFRESH, on_click=lambda e: (update_mobile_sessions(), load_orders()), tooltip="تحديث")
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                orders_list
            ])
        )
    )

    update_mobile_sessions()
    load_orders()


if __name__ == "__main__":
    ft.run(main)
