import flet as ft
from supabase import create_client, Client

SUPABASE_URL = "https://qygefxheemltsaampjbh.supabase.co"
SUPABASE_KEY = "sb_publishable_-ra_ou-i5SnqG-aItNPJzg_RtkWYYyC"

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def main(page: ft.Page):
    page.title = "Triple H"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.rtl = True
    page.scroll = "auto"
    page.padding = 15

    orders_list = ft.Column(spacing=10)

    code_in = ft.TextField(label="كود الشحنة", text_align=ft.TextAlign.RIGHT)
    name_in = ft.TextField(label="اسم العميل", text_align=ft.TextAlign.RIGHT)
    phone_in = ft.TextField(label="رقم الهاتف", keyboard_type=ft.KeyboardType.PHONE, text_align=ft.TextAlign.RIGHT)
    address_in = ft.TextField(label="العنوان", text_align=ft.TextAlign.RIGHT)
    courier_in = ft.TextField(label="اسم المندوب", text_align=ft.TextAlign.RIGHT)
    price_in = ft.TextField(label="سعر الشحنة", keyboard_type=ft.KeyboardType.NUMBER, text_align=ft.TextAlign.RIGHT, value="0")
    fee_in = ft.TextField(label="مصاريف الشحن", keyboard_type=ft.KeyboardType.NUMBER, text_align=ft.TextAlign.RIGHT, value="0")
    notes_in = ft.TextField(label="ملاحظات", text_align=ft.TextAlign.RIGHT)
    
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

    def show_msg(text, color="green"):
        snack = ft.SnackBar(ft.Text(text), bgcolor=color)
        page.overlay.append(snack)
        snack.open = True
        page.update()

    def load_orders(e=None):
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
            page.update()
        except Exception as err:
            show_msg("خطأ في جلب البيانات: " + str(err), color="red")

    def add_order_click(e):
        if not code_in.value or not name_in.value or not phone_in.value:
            show_msg("يرجى ملء الكود والاسم والهاتف!", color="orange")
            return
        
        try:
            p_val = float(price_in.value or 0)
            f_val = float(fee_in.value or 0)
        except ValueError:
            show_msg("أدخل أرقام صحيحة في الأسعار", color="red")
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
            show_msg("تمت إضافة الشحنة بنجاح ✅")
            code_in.value = name_in.value = phone_in.value = address_in.value = courier_in.value = notes_in.value = ""
            price_in.value = fee_in.value = "0"
            load_orders()
        except Exception as err:
            show_msg("خطأ أثناء الحفظ: " + str(err), color="red")

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
                                code_in, name_in, phone_in, address_in, courier_in,
                                ft.Row([price_in, fee_in]),
                                status_dd, notes_in,
                                ft.ElevatedButton("حفظ الأوردر", icon=ft.Icons.SAVE, on_click=add_order_click, bgcolor="#10b981", color="white")
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

    load_orders()

if __name__ == "__main__":
    ft.app(target=main)