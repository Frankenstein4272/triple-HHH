import os
import io
import json
import flet as ft
from supabase import create_client, Client
import google.generativeai as genai
import PIL.Image

# --- إعدادات Supabase السحابية ---
SUPABASE_URL = "https://qygefxheemltsaampjbh.supabase.co"
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "sb_publishable_-ra_ou-i5SnqG-aItNPJzg_RtkWYYyC")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- إعدادات الذكاء الاصطناعي (Gemini) ---
_k_parts = ["AQ.Ab8RN6KJB4uOPzF", "ne62AK-bM0rgoz_AUj", "SWpgMB02fEF_EMNJg"]
DEFAULT_GEMINI_KEY = "".join(_k_parts)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", DEFAULT_GEMINI_KEY)

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

async def main(page: ft.Page):
    page.title = "Triple H - الشحنات"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.rtl = True
    page.scroll = "auto"
    page.padding = 15

    orders_list = ft.Column(spacing=10)

    # حقول إدخال البيانات
    code_in = ft.TextField(label="كود الشحنة", text_align=ft.TextAlign.RIGHT)
    name_in = ft.TextField(label="اسم العميل (المستلم)", text_align=ft.TextAlign.RIGHT)
    phone_in = ft.TextField(label="رقم الهاتف", keyboard_type=ft.KeyboardType.PHONE, text_align=ft.TextAlign.RIGHT)
    address_in = ft.TextField(label="العنوان بالتفصيل", text_align=ft.TextAlign.RIGHT)
    courier_in = ft.TextField(label="اسم المندوب", text_align=ft.TextAlign.RIGHT)
    price_in = ft.TextField(label="سعر الشحنة (EGP)", keyboard_type=ft.KeyboardType.NUMBER, text_align=ft.TextAlign.RIGHT, value="0")
    fee_in = ft.TextField(label="مصاريف الشحن (EGP)", keyboard_type=ft.KeyboardType.NUMBER, text_align=ft.TextAlign.RIGHT, value="0")
    notes_in = ft.TextField(label="ملاحظات إضافية", text_align=ft.TextAlign.RIGHT)
    
    status_dd = ft.Dropdown(
        label="الحالة",
        value="قيد الانتظار",
        options=[
            ft.dropdown.Option("قيد الانتظار"),
            ft.dropdown.Option("مع المندوب"),
            ft.dropdown.Option("تم التسليم بنجاح"),
            ft.dropdown.Option("تم الإلغاء / مرتجع"),
        ]
    )

    loading_indicator = ft.ProgressBar(visible=False, color="#3b82f6")

    async def show_msg(text, color="green"):
        snack = ft.SnackBar(ft.Text(text), bgcolor=color)
        page.overlay.append(snack)
        snack.open = True
        await page.update_async()

    # --- معالجة واستخراج بيانات الشحنة من الصورة بالذكاء الاصطناعي ---
    async def process_image_with_ai(file_path=None, file_bytes=None):
        if not GEMINI_API_KEY:
            await show_msg("مفتاح Gemini غير مفعل!", color="red")
            return

        loading_indicator.visible = True
        await page.update_async()

        try:
            if file_bytes:
                img = PIL.Image.open(io.BytesIO(file_bytes))
            elif file_path:
                img = PIL.Image.open(file_path)
            else:
                await show_msg("لم يتم العثور على ملف الصورة", color="red")
                return

            model = genai.GenerativeModel("gemini-1.5-flash")

            prompt = """
            أنت مساعد ذكي متخصص في استخراج بيانات شحنات التوصيل من الصور (سواء كانت مكتوبة بخط اليد أو مطبوعة).
            قم بتحليل الصورة واستخرج البيانات بدقة بصيغة JSON فقط:
            {
                "order_code": "كود الشحنة أو رقم البوليصة إن وجد",
                "customer_name": "اسم العميل المستلم",
                "phone": "رقم الهاتف",
                "address": "العنوان بالتفصيل المحافظة والمنطقة والشارع",
                "item_price": 0,
                "shipping_fee": 0,
                "notes": "أي ملاحظات إضافية على الطرد"
            }
            إذا لم تجد قيمة لحقل معين اجعل قيمته نص فارغ "" أو 0 للمبالغ. لا تضف أي شرح أو نصوص خارج الـ JSON.
            """

            response = model.generate_content([prompt, img])
            text_resp = response.text.strip()

            if text_resp.startswith("```json"):
                text_resp = text_resp[7:]
            if text_resp.startswith("```"):
                text_resp = text_resp[3:]
            if text_resp.endswith("```"):
                text_resp = text_resp[:-3]
            
            data = json.loads(text_resp.strip())

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

            await show_msg("تم استخراج بيانات الشحنة من الورقة بنجاح! 🎯")
        except Exception as ex:
            await show_msg("خطأ في قراءة الصورة: " + str(ex), color="red")
        finally:
            loading_indicator.visible = False
            await page.update_async()

    # --- اختيار وتصوير الملف ---
    async def pick_file_click(e):
        try:
            picker = ft.FilePicker()
            files = await picker.pick_files(
                allow_multiple=False,
                allowed_extensions=["png", "jpg", "jpeg"]
            )
            if files and len(files) > 0:
                selected_file = files[0]
                await process_image_with_ai(
                    file_path=getattr(selected_file, 'path', None),
                    file_bytes=getattr(selected_file, 'bytes', None)
                )
        except Exception as ex:
            await show_msg("خطأ في فتح مستعرض الصور: " + str(ex), color="red")

    # --- تحميل قائمة الشحنات من Supabase ---
    async def load_orders(e=None):
        orders_list.controls.clear()
        try:
            res = supabase.table("orders").select("*").order("id", desc=True).execute()
            if not res.data:
                orders_list.controls.append(
                    ft.Container(content=ft.Text("لا توجد شحنات مسجلة", color="grey"), alignment=ft.alignment.center, padding=20)
                )
            else:
                for item in res.data:
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
                                        content=ft.Text(status, size=11, weight="bold"),
                                        bgcolor="white", padding=ft.padding.symmetric(horizontal=6, vertical=3), border_radius=4
                                    )
                                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                                ft.Text("👤 العميل: " + str(item.get('customer_name', ''))),
                                ft.Text("📞 الهاتف: " + str(item.get('phone', ''))),
                                ft.Text("📍 العنوان: " + str(item.get('address', ''))),
                                ft.Text("🚚 المندوب: " + str(item.get('courier', ''))),
                                ft.Divider(),
                                ft.Text("💵 الإجمالي: " + "{:.2f}".format(total) + " EGP", weight="bold", color="#047857"),
                                ft.Text("📝 ملاحظات: " + str(item.get('notes', '-')), size=11, italic=True)
                            ], spacing=3)
                        )
                    )
                    orders_list.controls.append(card)
            await page.update_async()
        except Exception as err:
            await show_msg("خطأ في جلب البيانات: " + str(err), color="red")

    # --- إضافة وحفظ شحنة جديدة ---
    async def add_order_click(e):
        if not code_in.value or not name_in.value or not phone_in.value:
            await show_msg("يرجى ملء الكود والاسم والهاتف!", color="orange")
            return
        
        try:
            p_val = float(price_in.value or 0)
            f_val = float(fee_in.value or 0)
        except ValueError:
            await show_msg("أدخل أرقام صحيحة في الأسعار", color="red")
            return

        data = {
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
            await show_msg("تمت إضافة الشحنة بنجاح ✅")
            code_in.value = name_in.value = phone_in.value = address_in.value = courier_in.value = notes_in.value = ""
            price_in.value = fee_in.value = "0"
            await load_orders()
        except Exception as err:
            await show_msg("خطأ أثناء الحفظ: " + str(err), color="red")

    # واجهة التطبيق
    page.add(
        ft.AppBar(title=ft.Text("Triple H - الشحنات", color="white"), bgcolor="#1e293b", center_title=True),
        ft.Container(
            content=ft.Column([
                ft.ExpansionTile(
                    title=ft.Text("➕ إضافة شحنة جديدة", weight="bold", color="#0f766e"),
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
                                code_in, name_in, phone_in, address_in, courier_in,
                                ft.Row([price_in, fee_in]),
                                status_dd, notes_in,
                                ft.ElevatedButton("حفظ الأوردر", icon=ft.Icons.SAVE, on_click=add_order_click, bgcolor="#10b981", color="white", height=45)
                            ])
                        )
                    ]
                ),
                ft.Divider(),
                ft.Row([
                    ft.Text("📋 قائمة الشحنات", size=18, weight="bold"),
                    ft.IconButton(icon=ft.Icons.REFRESH, on_click=load_orders)
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                orders_list
            ])
        )
    )

    await load_orders()

if __name__ == "__main__":
    ft.app(target=main)
