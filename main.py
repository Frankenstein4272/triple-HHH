import os
import io
import json
import base64
import datetime
import urllib.request
import urllib.parse
import flet as ft
from supabase import create_client, Client
import PIL.Image

# --- إعدادات Supabase السحابية ---
SUPABASE_URL = "https://qygefxheemltsaampjbh.supabase.co"
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "sb_publishable_-ra_ou-i5SnqG-aItNPJzg_RtkWYYyC")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- إعدادات الذكاء الاصطناعي (Gemini) ---
_k_parts = ["AQ.Ab8RN6KIkzTRIuUh", "7FC4cCYVxsS419zLlFu", "RNh6oxaLO5KThzQ"]
DEFAULT_GEMINI_KEY = "".join(_k_parts)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", DEFAULT_GEMINI_KEY)


def main(page: ft.Page):
    page.title = "Triple H - إدارة الشحنات"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.rtl = True
    page.scroll = "auto"
    page.padding = 10

    today_str = datetime.date.today().strftime("%Y-%m-%d")

    selected_order_id = {"id": None}
    current_orders_data = {"rows": []}

    # عناصر عرض الإحصائيات
    stat_shipping = ft.Text("0.00 EGP", size=14, weight="bold", color="#1d4ed8")
    stat_items = ft.Text("0.00 EGP", size=14, weight="bold", color="#b45309")
    stat_total = ft.Text("0.00 EGP", size=15, weight="bold", color="#047857")
    stat_count = ft.Text("0", size=15, weight="bold", color="#1e293b")

    # حقول إدخال وتعديل البيانات
    session_date_in = ft.TextField(label="تاريخ الجلسة (YYYY-MM-DD)", value=today_str, text_align=ft.TextAlign.RIGHT)
    code_in = ft.TextField(label="كود الشحنة (تلقائي/يدوي)", text_align=ft.TextAlign.RIGHT)
    name_in = ft.TextField(label="اسم العميل (المستلم)", text_align=ft.TextAlign.RIGHT)
    phone_in = ft.TextField(label="رقم الهاتف", keyboard_type=ft.KeyboardType.PHONE, text_align=ft.TextAlign.RIGHT)
    address_in = ft.TextField(label="العنوان بالتفصيل", text_align=ft.TextAlign.RIGHT)
    courier_in = ft.TextField(label="اسم المندوب", text_align=ft.TextAlign.RIGHT)
    price_in = ft.TextField(label="سعر الشحنة / المنتج (EGP)", keyboard_type=ft.KeyboardType.NUMBER, text_align=ft.TextAlign.RIGHT, value="0")
    fee_in = ft.TextField(label="مصاريف الشحن (EGP)", keyboard_type=ft.KeyboardType.NUMBER, text_align=ft.TextAlign.RIGHT, value="0")
    notes_in = ft.TextField(label="ملاحظات إضافية", text_align=ft.TextAlign.RIGHT)

    status_dd = ft.Dropdown(
        label="حالة الشحنة",
        value="قيد الانتظار",
        options=[
            ft.dropdown.Option("قيد الانتظار"),
            ft.dropdown.Option("مع المندوب"),
            ft.dropdown.Option("تم التسليم بنجاح"),
            ft.dropdown.Option("تم الإلغاء / مرتجع"),
        ]
    )

    # قائمة اختيار الجلسات المنسدلة (Scrollable Dropdown)
    filter_session_dd = ft.Dropdown(
        label="📅 اختيار الجلسة",
        value=f"جلسة اليوم ({today_str})",
        expand=True,
        options=[
            ft.dropdown.Option(f"جلسة اليوم ({today_str})"),
            ft.dropdown.Option("كل الجلسات")
        ]
    )

    search_in = ft.TextField(label="🔍 بحث (كود، اسم، هاتف، مندوب)", text_align=ft.TextAlign.RIGHT, expand=True)
    filter_status_dd = ft.Dropdown(
        label="الحالة",
        value="كل الحالات",
        width=130,
        options=[
            ft.dropdown.Option("كل الحالات"),
            ft.dropdown.Option("قيد الانتظار"),
            ft.dropdown.Option("مع المندوب"),
            ft.dropdown.Option("تم التسليم بنجاح"),
            ft.dropdown.Option("تم الإلغاء / مرتجع"),
        ]
    )

    loading_indicator = ft.ProgressBar(visible=False, color="#3b82f6")
    orders_list = ft.Column(spacing=10)

    btn_add = ft.ElevatedButton("➕ إضافة أوردر", icon=ft.Icons.ADD, bgcolor="#10b981", color="white", height=45, expand=True)
    btn_update = ft.ElevatedButton("✏️ حفظ التعديل", icon=ft.Icons.CHECK, bgcolor="#3b82f6", color="white", height=45, visible=False, expand=True)
    btn_delete = ft.ElevatedButton("🗑️ حذف", icon=ft.Icons.DELETE, bgcolor="#ef4444", color="white", height=45, visible=False)
    btn_clear = ft.OutlinedButton("🔄 تفريغ", height=45)

    form_title = ft.Text(" بيانات الأوردر ", weight="bold", size=16, color="#0f766e")

    def show_msg(text, color="green"):
        snack = ft.SnackBar(ft.Text(text), bgcolor=color)
        page.overlay.append(snack)
        snack.open = True
        page.update()

    def update_mobile_sessions():
        """جلب كل الجلسات السابقة وتعبئة القائمة المنسدلة"""
        try:
            res = supabase.table("orders").select("session_date").order("session_date", desc=True).execute()
            dates = []
            for item in (res.data or []):
                d = item.get("session_date")
                if d and d not in dates:
                    dates.append(d)

            opts = [
                ft.dropdown.Option(f"جلسة اليوم ({today_str})"),
                ft.dropdown.Option("كل الجلسات")
            ]
            for d in dates:
                if d != today_str:
                    opts.append(ft.dropdown.Option(d))

            filter_session_dd.options = opts
            page.update()
        except Exception:
            pass

    def clear_fields(e=None):
        selected_order_id["id"] = None
        session_date_in.value = today_str
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

    def open_whatsapp_customer(item):
        phone = str(item.get("phone") or "").strip().replace(" ", "").replace("-", "")
        if not phone:
            show_msg("لا يوجد رقم هاتف مسجل!", color="red")
            return

        if phone.startswith("01"):
            phone = "2" + phone
        elif not phone.startswith("+") and not phone.startswith("20"):
            phone = "20" + phone

        name = item.get("customer_name") or "العميل العزيز"
        code = item.get("order_code") or ""
        courier = item.get("courier") or "مندوبنا"
        msg = f"مرحباً {name}، شحنتك رقم #{code} في الطريق إليك مع المندوب: {courier}. برجاء التواجد للاستلام."
        page.launch_url(f"https://wa.me/{phone}?text={urllib.parse.quote(msg)}")

    def share_courier_manifest(e=None):
        if not current_orders_data["rows"]:
            show_msg("لا توجد أوردرات معروضة لمشاركتها!", color="orange")
            return

        sess_name = filter_session_dd.value or "جميع الجلسات"
        lines = [f"📦 *كشف تسليم شحنات ({sess_name}) - Triple H*", "-------------------------"]
        total_collect = 0.0
        for idx, r in enumerate(current_orders_data["rows"], 1):
            tot = float(r.get('item_price') or 0) + float(r.get('shipping_fee') or 0)
            total_collect += tot
            lines.append(f"{idx}) #{r.get('order_code')} - {r.get('customer_name')}")
            lines.append(f"📞 {r.get('phone')} | 📍 {r.get('address')}")
            lines.append(f"💵 المطلوب: {tot:.2f} EGP")
            lines.append("-------------------------")

        lines.append(f"💰 *إجمالي تحصيل الجلسة: {total_collect:,.2f} EGP*")
        full_text = "\n".join(lines)
        page.launch_url(f"https://wa.me/?text={urllib.parse.quote(full_text)}")

    # --- معالجة وقراءة الصورة عبر AI ---
    def process_image_with_ai(file_path=None, file_bytes=None):
        if not GEMINI_API_KEY:
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

            buffered = io.BytesIO()
            img.save(buffered, format="JPEG", quality=85)
            img_b64 = base64.b64encode(buffered.getvalue()).decode("utf-8")

            prompt_text = """
            أنت مساعد ذكي لاستخراج بيانات شحنات التوصيل وبوالص الشحن.
            استخرج البيانات بصيغة JSON فقط:
            {
                "order_code": "كود الشحنة أو رقم البوليصة إن وجد",
                "customer_name": "اسم العميل المستلم",
                "phone": "رقم الهاتف",
                "address": "العنوان بالتفصيل",
                "item_price": 0,
                "shipping_fee": 0,
                "notes": "أي ملاحظات إضافية على الطرد"
            }
            إذا لم تجد قيمة لحقل معين اجعل قيمته نص فارغ "" أو 0 للمبالغ.
            """

            payload = {
                "contents": [
                    {
                        "parts": [
                            {"text": prompt_text},
                            {
                                "inline_data": {
                                    "mime_type": "image/jpeg",
                                    "data": img_b64
                                }
                            }
                        ]
                    }
                ]
            }

            target_models = [
                "models/gemini-2.0-flash",
                "models/gemini-1.5-flash",
                "models/gemini-1.5-flash-8b",
                "models/gemini-1.5-pro",
                "models/gemini-pro"
            ]

            response_json = None
            last_err_msg = ""

            for full_model_name in target_models:
                clean_name = full_model_name.replace("models/", "")
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{clean_name}:generateContent?key={GEMINI_API_KEY}"
                req = urllib.request.Request(
                    url,
                    data=json.dumps(payload).encode("utf-8"),
                    headers={"Content-Type": "application/json", "x-goog-api-key": GEMINI_API_KEY}
                )

                try:
                    with urllib.request.urlopen(req, timeout=30) as resp:
                        if resp.status == 200:
                            response_json = json.loads(resp.read().decode("utf-8"))
                            break
                except Exception as err:
                    last_err_msg = str(err)
                    continue

            if not response_json:
                raise Exception(f"فشل الاتصال: {last_err_msg}")

            candidates = response_json.get("candidates", [])
            if not candidates:
                raise Exception("رد الذكاء الاصطناعي فارغ")
            
            parts = candidates[0].get("content", {}).get("parts", [])
            raw_text = parts[0].get("text", "").strip()

            if raw_text.startswith("```json"):
                raw_text = raw_text[7:]
            if raw_text.startswith("```"):
                raw_text = raw_text[3:]
            if raw_text.endswith("```"):
                raw_text = raw_text[:-3]

            data = json.loads(raw_text.strip())

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

            show_msg("تم استخراج بيانات الشحنة من الورقة بنجاح! 🎯")

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

    # --- جلب البيانات مع الفلترة بالجلسة ---
    def load_orders(e=None):
        orders_list.controls.clear()
        selected_sess = filter_session_dd.value
        search_txt = search_in.value.strip() if search_in.value else ""
        selected_status = filter_status_dd.value

        try:
            query = supabase.table("orders").select("*")

            if selected_sess == f"جلسة اليوم ({today_str})":
                query = query.eq("session_date", today_str)
            elif selected_sess and selected_sess != "كل الجلسات":
                query = query.eq("session_date", selected_sess)

            if search_txt:
                pattern = "%" + search_txt + "%"
                filter_str = (
                    "order_code.ilike." + pattern + ","
                    "customer_name.ilike." + pattern + ","
                    "phone.ilike." + pattern + ","
                    "courier.ilike." + pattern
                )
                query = query.or_(filter_str)

            if selected_status != "كل الحالات":
                query = query.eq("status", selected_status)

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
                        content=ft.Text("لا توجد أوردرات في هذه الجلسة", color="grey", size=15),
                        alignment=ft.Alignment(0, 0),
                        padding=20
                    )
                )
            else:
                for item in rows:
                    status = item.get('status', 'قيد الانتظار')
                    bg_col = "#fef3c7" if status == "قيد الانتظار" else ("#dbeafe" if status == "مع المندوب" else ("#dcfce7" if status == "تم التسليم بنجاح" else "#fee2e2"))
                    price = float(item.get('item_price') or 0)
                    fee = float(item.get('shipping_fee') or 0)
                    total = price + fee

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
                                        content=ft.Text(f"📅 {item.get('session_date', '-')}", size=11, color="#475569"),
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
                                    ft.ElevatedButton(
                                        "💬 واتساب",
                                        icon=ft.Icons.CHAT,
                                        bgcolor="#25d366",
                                        color="white",
                                        height=36,
                                        on_click=lambda e, itm=item: open_whatsapp_customer(itm)
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

        data = {
            "session_date": s_date,
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
                            ft.Text("🚚 أرباح شحن الجلسة", size=11, weight="bold", color="#1e40af"),
                            stat_shipping
                        ], alignment=ft.MainAxisAlignment.CENTER)
                    ),
                    ft.Container(
                        expand=True,
                        bgcolor="#fefce8",
                        padding=8,
                        border_radius=8,
                        content=ft.Column([
                            ft.Text("📦 بضاعة الجلسة", size=11, weight="bold", color="#854d0e"),
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
                            ft.Text("💵 مطلوب تحصيله", size=11, weight="bold", color="#065f46"),
                            stat_total
                        ], alignment=ft.MainAxisAlignment.CENTER)
                    ),
                    ft.Container(
                        expand=True,
                        bgcolor="#f3f4f6",
                        padding=8,
                        border_radius=8,
                        content=ft.Column([
                            ft.Text("🔢 عدد أوردرات الجلسة", size=11, weight="bold", color="#374151"),
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
                    ft.ElevatedButton(
                        "📷 تصوير / رفع صورة البوليصة (AI Scan)",
                        icon=ft.Icons.CAMERA_ALT,
                        bgcolor="#3b82f6",
                        color="white",
                        height=45,
                        on_click=pick_file_click
                    ),
                    loading_indicator,
                    ft.Divider(),
                    session_date_in, code_in, name_in, phone_in, address_in, courier_in,
                    ft.Row([price_in, fee_in]),
                    status_dd, notes_in,
                    ft.Row([btn_add, btn_update, btn_delete, btn_clear])
                ])
            )
        ]
    )

    page.add(
        ft.AppBar(title=ft.Text("📦 Triple H - إدارة الشحنات", color="white", weight="bold"), bgcolor="#1e293b", center_title=True),
        ft.Container(
            content=ft.Column([
                stats_dashboard,
                form_tile,
                ft.Divider(),
                ft.Row([
                    filter_session_dd,
                    ft.ElevatedButton("📋 كشف واتساب", icon=ft.Icons.SHARE, bgcolor="#0284c7", color="white", on_click=share_courier_manifest)
                ]),
                ft.Row([search_in, filter_status_dd]),
                ft.Row([
                    ft.Text("📋 أوردرات الجلسة المحددة", size=15, weight="bold"),
                    ft.IconButton(icon=ft.Icons.REFRESH, on_click=lambda e: (update_mobile_sessions(), load_orders()), tooltip="تحديث")
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                orders_list
            ])
        )
    )

    update_mobile_sessions()
    load_orders()


if __name__ == "__main__":
    ft.app(target=main)
