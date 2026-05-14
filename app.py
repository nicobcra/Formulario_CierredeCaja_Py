# Proyecto N-1 Automatizacion de Formularios a base de datos Excel
# Nicolas Becerra - 30/04/26
# Modulo Web - Flask backend con Supabase - Version 2.0

from werkzeug.security import generate_password_hash, check_password_hash
from flask import Flask, render_template, request, jsonify, redirect, session
from datetime import date, timedelta, datetime, timezone


# Timezone Colombia (UTC-5, sin horario de verano)
COL_TZ = timezone(timedelta(hours=-5))


def hoy_colombia():
    return datetime.now(COL_TZ).date()


import requests
import os

app = Flask(__name__)
app.config["SECRET_KEY"] = "controla_super_secret_key_estable_2026"

# Mantener sesión activa
app.config["SESSION_PERMANENT"] = True
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=7)

# Cookies seguras
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_REFRESH_EACH_REQUEST"] = True

# SOLO activar esto en producción HTTPS
# app.config["SESSION_COOKIE_SECURE"] = True





def usuario_logueado():
    return "usuario_id" in session

# Credenciales Supabase
SUPABASE_URL = "https://brumjdswhdzkoftmxjmx.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImJydW1qZHN3aGR6a29mdG14am14Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3Nzc1NjYzNDQsImV4cCI6MjA5MzE0MjM0NH0.YNypTWAsfcDxDrTmwlObEfPspnlHwyKHDx2t5yKXDEg"

# Headers que van en cada peticion a Supabase
HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation",
}


# Formato de cop
def formatear_cop(valor):
    return f"${valor:,.0f}".replace(",", ".")


# Limpia puntos, comas y simbolo de pesos para convertir el texto a numero
def parse_num(texto):
    texto = str(texto).replace(".", "").replace(",", "").replace("$", "").strip()
    return int(texto) if texto else 0


# Devuelve todas las ventas guardadas en Supabase ordenadas por fecha descendente
def obtener_ventas():
    try:
        res = requests.get(
            f"{SUPABASE_URL}/rest/v1/ventas",
            headers=HEADERS,
            params={
                "select": "*",
                "tienda_id": f"eq.{session['tienda_id']}",
                "order": "created_at.desc"
            }
        )
        ventas = []
        for row in res.json():
            ventas.append({
                "fecha": row.get("fecha", ""),
                "nequi": formatear_cop(row.get("nequi", 0)),
                "daviplata": formatear_cop(row.get("daviplata", 0)),
                "efectivo": formatear_cop(row.get("efectivo", 0)),
                "fiado": formatear_cop(row.get("fiado", 0)),
                "total": formatear_cop(row.get("total", 0)),
            })
        return ventas
    except Exception:
        return []


# Devuelve todos los proveedores activos de la tienda actual
def obtener_proveedores(tienda_id):

    try:

        res = requests.get(
            f"{SUPABASE_URL}/rest/v1/proveedores",
            headers=HEADERS,
            params={
                "select": "*",
                "tienda_id": f"eq.{tienda_id}",
                "activo": "eq.true",
                "order": "nombre.asc"
            }
        )

        return res.json()

    except Exception:
        return []

# Devuelve todos los pedidos de la tienda actual
def obtener_pedidos(tienda_id):

    try:

        res = requests.get(
            f"{SUPABASE_URL}/rest/v1/pedidos",
            headers=HEADERS,
            params={
                "select": "*,proveedores(nombre)",
                "tienda_id": f"eq.{tienda_id}",
                "order": "created_at.desc"
            }
        )

        pedidos = []

        for row in res.json():

            pedidos.append({
                "id": row.get("id"),
                "fecha": row.get("fecha", ""),
                "proveedor": row.get("proveedores", {}).get("nombre", "")
                    if row.get("proveedores") else "",
                "total": formatear_cop(row.get("total", 0)),
                "pagado_con": row.get("pagado_con", ""),
                "notas": row.get("notas", ""),
            })

        return pedidos

    except Exception:
        return []


# Obtiene ventas de hoy y de los ultimos 7 dias para el dashboard de inicio
# Obtiene ventas de hoy y de los ultimos 7 dias
def obtener_datos_inicio(tienda_id):

    try:

        res = requests.get(
            f"{SUPABASE_URL}/rest/v1/ventas",
            headers=HEADERS,
            params={
                "select": "*",
                "tienda_id": f"eq.{tienda_id}",
                "order": "fecha.desc",
                "limit": "30"
            }
        )

        if res.status_code != 200:
            return {
                "total_hoy": 0,
                "nequi_hoy": 0,
                "daviplata_hoy": 0,
                "efectivo_hoy": 0,
                "semana": [],
            }

        rows = res.json()

        hoy = hoy_colombia()

        # Venta de hoy
        venta_hoy = next(
            (
                r for r in rows
                if str(r.get("fecha", ""))[:10] == str(hoy)
            ),
            None
        )

        total_hoy = venta_hoy.get("total", 0) if venta_hoy else 0
        nequi_hoy = venta_hoy.get("nequi", 0) if venta_hoy else 0
        daviplata_hoy = venta_hoy.get("daviplata", 0) if venta_hoy else 0
        efectivo_hoy = venta_hoy.get("efectivo", 0) if venta_hoy else 0

        # Datos de los últimos 7 días
        dias_semana = [
            "Lun",
            "Mar",
            "Mie",
            "Jue",
            "Vie",
            "Sab",
            "Dom"
        ]

        semana = []

        for i in range(6, -1, -1):

            dia = hoy - timedelta(days=i)

            row = next(
                (
                    r for r in rows
                    if str(r.get("fecha", ""))[:10] == str(dia)
                ),
                None
            )

            semana.append({
                "dia": dias_semana[dia.weekday()],
                "fecha": str(dia),
                "total": row.get("total", 0) if row else 0,
                "nequi": row.get("nequi", 0) if row else 0,
                "daviplata": row.get("daviplata", 0) if row else 0,
                "efectivo": row.get("efectivo", 0) if row else 0,
                "es_hoy": dia == hoy,
            })

        return {
            "total_hoy": total_hoy,
            "nequi_hoy": nequi_hoy,
            "daviplata_hoy": daviplata_hoy,
            "efectivo_hoy": efectivo_hoy,
            "semana": semana,
        }

    except Exception as e:

        print("ERROR EN INICIO:", e)

        return {
            "total_hoy": 0,
            "nequi_hoy": 0,
            "daviplata_hoy": 0,
            "efectivo_hoy": 0,
            "semana": [],
        }

# LOGIN
@app.route("/", methods=["GET", "POST"])
@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        telefono = request.form.get("telefono", "").strip()
        password = request.form.get("password", "")

        try:

            # Buscar usuario por teléfono
            res = requests.get(
                f"{SUPABASE_URL}/rest/v1/usuarios",
                headers=HEADERS,
                params={
                    "telefono": f"eq.{telefono}",
                    "activo": "eq.true",
                    "select": "*"
                }
            )

            usuarios = res.json()

            # Validar existencia
            if len(usuarios) == 0:
                return render_template(
                    "login.html",
                    error="Número o contraseña incorrectos"
                )

            usuario = usuarios[0]

            # Validar contraseña encriptada
            password_correcta = check_password_hash(
                usuario["password"],
                password
            )

            if not password_correcta:
                return render_template(
                    "login.html",
                    error="Número o contraseña incorrectos"
                )

            # Guardar sesión
            session.permanent = True

            session["usuario_id"] = usuario["id"]
            session["tienda_id"] = usuario["tienda_id"]
            session["usuario_nombre"] = usuario["nombre"]
            session["rol"] = usuario["rol"]

            session.modified = True

            return redirect("/inicio")

        except Exception as e:
            return render_template(
                "login.html",
                error=str(e)

            )

    return render_template("login.html")

# Cerrar sesión
@app.route("/logout")
def logout():

    session.clear()

    return redirect("/login")

@app.route("/registro")
def registro():
    return render_template("registro.html")

# Ruta de Registro
@app.route("/crear-cuenta", methods=["POST"])
def crear_cuenta():

    try:

        data = request.json

        nombre_tienda = data.get("nombre_tienda", "").strip()
        nombre_admin = data.get("nombre_admin", "").strip()
        telefono = data.get("telefono", "").strip()
        correo = data.get("correo", "").strip().lower()
        password = data.get("password", "")
        confirmar = data.get("confirmar", "")

        # Validar campos vacíos
        if not nombre_tienda or not nombre_admin or not telefono or not correo or not password:

            return jsonify({
                "ok": False,
                "error": "Todos los campos son obligatorios"
            })

        # Validar passwords
        if password != confirmar:

            return jsonify({
                "ok": False,
                "error": "Las contraseñas no coinciden"
            })

        # =========================
        # VALIDAR TELÉFONO REPETIDO
        # =========================

        res_tel = requests.get(
            f"{SUPABASE_URL}/rest/v1/usuarios",
            headers=HEADERS,
            params={
                "telefono": f"eq.{telefono}",
                "select": "id"
            }
        )

        usuarios_tel = res_tel.json()

        if len(usuarios_tel) > 0:

            return jsonify({
                "ok": False,
                "error": "Ese número ya está registrado"
            })

        # =======================
        # VALIDAR CORREO REPETIDO
        # =======================

        res_correo = requests.get(
            f"{SUPABASE_URL}/rest/v1/usuarios",
            headers=HEADERS,
            params={
                "correo": f"eq.{correo}",
                "select": "id"
            }
        )

        usuarios_correo = res_correo.json()

        if len(usuarios_correo) > 0:

            return jsonify({
                "ok": False,
                "error": "Ese correo ya está registrado"
            })

        # Encriptar password
        password_hash = generate_password_hash(password)

        # Crear tienda
        tienda_payload = {
            "nombre": nombre_tienda
        }

        res_tienda = requests.post(
            f"{SUPABASE_URL}/rest/v1/tiendas",
            headers=HEADERS,
            json=tienda_payload
        )

        if res_tienda.status_code not in (200, 201):

            return jsonify({
                "ok": False,
                "error": res_tienda.text
            })

        tienda = res_tienda.json()[0]

        # Crear usuario admin
        usuario_payload = {
            "nombre": nombre_admin,
            "telefono": telefono,
            "correo": correo,
            "password": password_hash,
            "rol": "admin",
            "tienda_id": tienda["id"],
            "activo": True
        }

        res_usuario = requests.post(
            f"{SUPABASE_URL}/rest/v1/usuarios",
            headers=HEADERS,
            json=usuario_payload
        )

        if res_usuario.status_code not in (200, 201):

            return jsonify({
                "ok": False,
                "error": res_usuario.text
            })

        return jsonify({
            "ok": True
        })

    except Exception as e:

        return jsonify({
            "ok": False,
            "error": str(e)
        })

# Ruta principal - pagina de inicio con resumen del dia
@app.route("/inicio")
def inicio():

    if not usuario_logueado():
        return redirect("/login")

    tienda_id = session["tienda_id"]

    # Buscar datos de la tienda
    res_tienda = requests.get(
        f"{SUPABASE_URL}/rest/v1/tiendas",
        headers=HEADERS,
        params={
            "id": f"eq.{tienda_id}",
            "select": "*"
        }
    )

    tienda = {}

    if res_tienda.status_code == 200:

        tiendas = res_tienda.json()

        if len(tiendas) > 0:
            tienda = tiendas[0]

    datos = obtener_datos_inicio(tienda_id)

    return render_template(
        "inicio.html",
        modulo="inicio",
        datos=datos,
        tienda=tienda,
        usuario_nombre=session.get("usuario_nombre", "")
    )


# Ruta del modulo de ventas diarias
@app.route("/ventas")
def ventas():

    if "usuario_id" not in session:
        return redirect("/login")

    datos = obtener_ventas()

    return render_template(
        "ventas.html",
        ventas=datos,
        modulo="ventas"
    )


# Ruta del modulo de pedidos y proveedores
@app.route("/pedidos")
def pedidos():

    if "usuario_id" not in session:
        return redirect("/login")

    tienda_id = session["tienda_id"]

    datos_pedidos = obtener_pedidos(tienda_id)

    datos_proveedores = obtener_proveedores(tienda_id)

    return render_template(
        "pedidos.html",
        pedidos=datos_pedidos,
        proveedores=datos_proveedores,
        modulo="pedidos"
    )


# Devuelve todos los productos del inventario de la tienda actual
def obtener_inventario(tienda_id):

    try:

        res = requests.get(
            f"{SUPABASE_URL}/rest/v1/inventario",
            headers=HEADERS,
            params={
                "select": "*,proveedores(nombre)",
                "tienda_id": f"eq.{tienda_id}",
                "activo": "eq.true",
                "order": "nombre.asc"
            }
        )

        productos = []

        for row in res.json():

            precio_compra = row.get("precio_compra", 0) or 0
            precio_venta  = row.get("precio_venta", 0) or 0

            margen = round(
                ((precio_venta - precio_compra) / precio_compra) * 100
            ) if precio_compra > 0 else 0

            stock = row.get("stock", 0) or 0

            productos.append({
                "id": row.get("id"),
                "nombre": row.get("nombre", ""),
                "proveedor": row.get("proveedores", {}).get("nombre", "")
                    if row.get("proveedores") else "",
                "stock": stock,
                "stock_minimo": row.get("stock_minimo", 5),
                "precio_compra": formatear_cop(precio_compra),
                "precio_venta": formatear_cop(precio_venta),
                "margen": margen,
                "stock_bajo": stock <= row.get("stock_minimo", 5),
            })

        return productos

    except Exception:
        return []

# Ruta del modulo de inventario
@app.route("/inventario")
def inventario():

    if "usuario_id" not in session:
        return redirect("/login")

    tienda_id = session["tienda_id"]

    productos = obtener_inventario(tienda_id)

    proveedores = obtener_proveedores(tienda_id)

    total_productos = len(productos)

    stock_bajo = len([
        p for p in productos
        if p["stock_bajo"]
    ])

    alta_rotacion = len([
        p for p in productos
        if p["margen"] >= 25
    ])

    return render_template(
        "inventario.html",
        modulo="inventario",
        productos=productos,
        proveedores=proveedores,
        total_productos=total_productos,
        stock_bajo=stock_bajo,
        alta_rotacion=alta_rotacion
    )

# Guarda un producto nuevo en el inventario
@app.route("/guardar-producto", methods=["POST"])
def guardar_producto():
    try:
        data = request.json
        precio_compra = parse_num(data.get("precio_compra", 0))
        precio_venta  = parse_num(data.get("precio_venta", 0))
        payload = {
            "nombre":        data.get("nombre", "").strip(),
            "tienda_id": session["tienda_id"],
            "proveedor_id":  data.get("proveedor_id") or None,
            "stock":         int(data.get("stock", 0)),
            "stock_minimo":  int(data.get("stock_minimo", 5)),
            "precio_compra": precio_compra,
            "precio_venta":  precio_venta,
            "activo":        True,
        }
        res = requests.post(
            f"{SUPABASE_URL}/rest/v1/inventario",
            headers=HEADERS,
            json=payload
        )
        if res.status_code not in (200, 201):
            return jsonify({"ok": False, "error": res.text}), 500
        return jsonify({"ok": True, "producto": res.json()[0]})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

# Actualiza el stock de un producto
@app.route("/actualizar-stock", methods=["POST"])
def actualizar_stock():

    if "usuario_id" not in session:
        return jsonify({
            "ok": False,
            "error": "Sesion no valida"
        }), 401

    try:

        data = request.json

        product_id = data.get("id")

        delta = int(data.get("delta", 0))

        tienda_id = session["tienda_id"]

        # Buscar producto SOLO de la tienda actual
        res_get = requests.get(
            f"{SUPABASE_URL}/rest/v1/inventario",
            headers=HEADERS,
            params={
                "id": f"eq.{product_id}",
                "tienda_id": f"eq.{tienda_id}",
                "select": "stock"
            }
        )

        productos = res_get.json()

        if len(productos) == 0:
            return jsonify({
                "ok": False,
                "error": "Producto no encontrado"
            }), 404

        stock_actual = productos[0].get("stock", 0)

        nuevo_stock = max(
            0,
            stock_actual + delta
        )

        res = requests.patch(
            f"{SUPABASE_URL}/rest/v1/inventario?id=eq.{product_id}",
            headers=HEADERS,
            json={
                "stock": nuevo_stock
            }
        )

        if res.status_code not in (200, 201, 204):

            return jsonify({
                "ok": False,
                "error": res.text
            }), 500

        return jsonify({
            "ok": True,
            "stock": nuevo_stock
        })

    except Exception as e:

        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500


# Ruta del modulo de analisis y dashboard
@app.route("/analisis")
def analisis():

    if "usuario_id" not in session:
        return redirect("/login")

    return render_template(
        "analisis.html",
        modulo="analisis"
    )


# Guarda los datos del formulario de ventas en Supabase
# Guarda los datos del formulario de ventas en Supabase
@app.route("/guardar-venta", methods=["POST"])
def guardar_venta():

    if "usuario_id" not in session:
        return jsonify({
            "ok": False,
            "error": "Sesión no válida"
        }), 401

    try:

        data = request.json

        fecha = data.get("fecha", "")

        nequi = parse_num(data.get("nequi", 0))
        daviplata = parse_num(data.get("daviplata", 0))
        efectivo = parse_num(data.get("efectivo", 0))
        fiado = parse_num(data.get("fiado", 0))

        total = nequi + daviplata + efectivo + fiado

        payload = {
            "fecha": fecha,
            "tienda_id": session["tienda_id"],
            "nequi": nequi,
            "daviplata": daviplata,
            "efectivo": efectivo,
            "fiado": fiado,
            "total": total,
        }

        res = requests.post(
            f"{SUPABASE_URL}/rest/v1/ventas",
            headers=HEADERS,
            json=payload
        )

        if res.status_code not in (200, 201):

            return jsonify({
                "ok": False,
                "error": res.text
            }), 500

        return jsonify({
            "ok": True,
            "fecha": fecha,
            "nequi": formatear_cop(nequi),
            "daviplata": formatear_cop(daviplata),
            "efectivo": formatear_cop(efectivo),
            "fiado": formatear_cop(fiado),
            "total": formatear_cop(total),
        })

    except Exception as e:

        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500


# Guarda un proveedor nuevo en Supabase
@app.route("/guardar-proveedor", methods=["POST"])
def guardar_proveedor():
    try:
        data = request.json
        payload = {
            "nombre": data.get("nombre", "").strip(),
            "tienda_id": session["tienda_id"],
            "telefono": data.get("telefono", "").strip(),
            "categoria": data.get("categoria", "normal"),
            "activo": True,
        }

        res = requests.post(
            f"{SUPABASE_URL}/rest/v1/proveedores",
            headers=HEADERS,
            json=payload
        )

        if res.status_code not in (200, 201):
            return jsonify({"ok": False, "error": res.text}), 500

        return jsonify({"ok": True, "proveedor": res.json()[0]})

    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


# Guarda un pedido completo con sus items en Supabase
@app.route("/guardar-pedido", methods=["POST"])
def guardar_pedido():

    if "usuario_id" not in session:
        return jsonify({
            "ok": False,
            "error": "Sesion no valida"
        }), 401

    try:

        data = request.json

        fecha = data.get("fecha", "")
        tienda_id = session["tienda_id"]

        proveedor_id = data.get("proveedor_id")
        pagado_con = data.get("pagado_con", "")
        notas = data.get("notas", "")
        items = data.get("items", [])

        total = sum(
            parse_num(item.get("subtotal", 0))
            for item in items
        )

        # Guardar cabecera del pedido
        pedido_payload = {
            "fecha": fecha,
            "tienda_id": tienda_id,
            "proveedor_id": proveedor_id,
            "total": total,
            "pagado_con": pagado_con,
            "notas": notas,
        }

        res_pedido = requests.post(
            f"{SUPABASE_URL}/rest/v1/pedidos",
            headers=HEADERS,
            json=pedido_payload
        )

        if res_pedido.status_code not in (200, 201):
            return jsonify({
                "ok": False,
                "error": res_pedido.text
            }), 500

        pedido_id = res_pedido.json()[0]["id"]

        # Guardar cada item del pedido
        for item in items:

            precio_compra = parse_num(
                item.get("precio_compra", 0)
            )

            iva = parse_num(
                item.get("iva", 0)
            )

            precio_compra_final = parse_num(
                item.get("precio_compra_final", 0)
            )

            precio_venta = parse_num(
                item.get("precio_venta", 0)
            )

            cantidad = int(
                item.get("cantidad", 1)
            )

            subtotal = precio_compra_final * cantidad

            item_payload = {
                "pedido_id": pedido_id,
                "producto_nombre": item.get("producto_nombre", ""),
                "cantidad": cantidad,
                "precio_compra": precio_compra,
                "iva": iva,
                "precio_compra_final": precio_compra_final,
                "precio_venta": precio_venta,
                "subtotal": subtotal,
            }

            requests.post(
                f"{SUPABASE_URL}/rest/v1/pedido_items",
                headers=HEADERS,
                json=item_payload
            )

            # =========================================
            # OBTENER INVENTARIO UNA SOLA VEZ
            # =========================================

            res_inv = requests.get(
                f"{SUPABASE_URL}/rest/v1/inventario",
                headers=HEADERS,
                params={
                    "select": "id,stock,nombre",
                    "tienda_id": f"eq.{tienda_id}",
                    "activo": "eq.true"
                }
            )

            inventario = res_inv.json()

            # Crear mapa rápido por nombre
            inventario_map = {
                p.get("nombre", "").strip().lower(): p
                for p in inventario
            }

            # =========================================
            # ACTUALIZAR STOCK
            # =========================================

            for item in items:

                nombre = item.get(
                    "producto_nombre",
                    ""
                ).strip().lower()

                cantidad = int(
                    item.get("cantidad", 1)
                )

                producto = inventario_map.get(nombre)

                if producto:
                    nuevo_stock = (
                            producto.get("stock", 0) + cantidad
                    )

                    requests.patch(
                        f"{SUPABASE_URL}/rest/v1/inventario?id=eq.{producto['id']}",
                        headers=HEADERS,
                        json={
                            "stock": nuevo_stock
                        }
                    )

        return jsonify({
            "ok": True,
            "pedido_id": pedido_id,
            "total": formatear_cop(total)
        })

    except Exception as e:

        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False)