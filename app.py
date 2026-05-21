# Proyecto N-1 Automatizacion de Formularios a base de datos Excel
# Nicolas Becerra - 30/04/26
# Modulo Web - Flask backend con Supabase - Version 2.3

import os
import requests
from datetime import timedelta, datetime, timezone
from functools import wraps

from werkzeug.security import generate_password_hash, check_password_hash
from flask import Flask, render_template, request, jsonify, redirect, session


# ─────────────────────────────────────────
# TIMEZONE
# ─────────────────────────────────────────
COL_TZ = timezone(timedelta(hours=-5))

def hoy_colombia():
    return datetime.now(COL_TZ).date()


# ─────────────────────────────────────────
# APP
# ─────────────────────────────────────────
app = Flask(__name__)

IS_PROD = bool(os.environ.get("RAILWAY_ENVIRONMENT"))

app.config["SECRET_KEY"]                   = os.environ.get("SECRET_KEY", "dev_local_key")
app.config["SESSION_PERMANENT"]            = True
app.config["PERMANENT_SESSION_LIFETIME"]   = timedelta(days=7)
app.config["SESSION_COOKIE_HTTPONLY"]      = True
app.config["SESSION_REFRESH_EACH_REQUEST"] = True
app.config["SESSION_COOKIE_SAMESITE"]      = "None" if IS_PROD else "Lax"
app.config["SESSION_COOKIE_SECURE"]        = IS_PROD

@app.context_processor
def inject_session_vars():
    return {
        "rol":            session.get("rol", ""),
        "usuario_nombre": session.get("usuario_nombre", ""),
        "tienda_id":      session.get("tienda_id"),
    }


# ─────────────────────────────────────────
# SUPABASE
# ─────────────────────────────────────────
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://brumjdswhdzkoftmxjmx.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImJydW1qZHN3aGR6a29mdG14am14Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3Nzc1NjYzNDQsImV4cCI6MjA5MzE0MjM0NH0.YNypTWAsfcDxDrTmwlObEfPspnlHwyKHDx2t5yKXDEg")

HEADERS = {
    "apikey":        SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type":  "application/json",
    "Prefer":        "return=representation",
}


# ─────────────────────────────────────────
# DECORADORES DE SEGURIDAD
# ─────────────────────────────────────────
def login_requerido(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "usuario_id" not in session:
            if request.is_json:
                return jsonify({"ok": False, "error": "Sesión no válida"}), 401
            return redirect("/login")
        return f(*args, **kwargs)
    return wrapper


def rol_requerido(*roles):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if "usuario_id" not in session:
                if request.is_json:
                    return jsonify({"ok": False, "error": "Sesión no válida"}), 401
                return redirect("/login")
            if session.get("rol") not in roles:
                if request.is_json:
                    return jsonify({"ok": False, "error": "No tienes permiso para esto"}), 403
                return redirect("/inicio")
            return f(*args, **kwargs)
        return wrapper
    return decorator


# ─────────────────────────────────────────
# HELPERS SUPABASE
# ─────────────────────────────────────────
def sb_get(tabla, params):
    try:
        res = requests.get(f"{SUPABASE_URL}/rest/v1/{tabla}", headers=HEADERS, params=params)
        return res.json() if res.status_code == 200 else []
    except Exception:
        return []


def sb_post(tabla, payload):
    try:
        res = requests.post(f"{SUPABASE_URL}/rest/v1/{tabla}", headers=HEADERS, json=payload)
        ok  = res.status_code in (200, 201)
        return ok, res.json() if ok else res.text
    except Exception as e:
        return False, str(e)


def sb_patch(tabla, filtro, payload):
    try:
        res = requests.patch(f"{SUPABASE_URL}/rest/v1/{tabla}?{filtro}", headers=HEADERS, json=payload)
        ok  = res.status_code in (200, 201, 204)
        return ok, None if ok else res.text
    except Exception as e:
        return False, str(e)


def verificar_ownership(tabla, id_valor, tienda_id):
    rows = sb_get(tabla, {"id": f"eq.{id_valor}", "tienda_id": f"eq.{tienda_id}", "select": "id"})
    return len(rows) > 0


# ─────────────────────────────────────────
# HELPERS DE FORMATO
# ─────────────────────────────────────────
def formatear_cop(valor):
    return f"${valor:,.0f}".replace(",", ".")


def parse_num(texto):
    texto = str(texto).replace(".", "").replace(",", "").replace("$", "").strip()
    return int(texto) if texto else 0


# ─────────────────────────────────────────
# QUERIES
# ─────────────────────────────────────────
def obtener_cierres(tienda_id):
    """Historial de cierres de caja (tabla ventas)."""
    rows = sb_get("ventas", {
        "select":    "*",
        "tienda_id": f"eq.{tienda_id}",
        "order":     "created_at.desc",
    })
    return [{
        "fecha":     r.get("fecha", ""),
        "nequi":     formatear_cop(r.get("nequi", 0)),
        "daviplata": formatear_cop(r.get("daviplata", 0)),
        "efectivo":  formatear_cop(r.get("efectivo", 0)),
        "fiado":     formatear_cop(r.get("fiado", 0)),
        "total":     formatear_cop(r.get("total", 0)),
    } for r in rows]


def obtener_cierre_hoy(tienda_id):
    """Para vendedor: solo el cierre del día actual."""
    hoy  = str(hoy_colombia())
    rows = sb_get("ventas", {
        "select":    "*",
        "tienda_id": f"eq.{tienda_id}",
        "fecha":     f"eq.{hoy}",
    })
    if not rows:
        return None
    r = rows[0]
    return {
        "fecha":     r.get("fecha", ""),
        "nequi":     formatear_cop(r.get("nequi", 0)),
        "daviplata": formatear_cop(r.get("daviplata", 0)),
        "efectivo":  formatear_cop(r.get("efectivo", 0)),
        "fiado":     formatear_cop(r.get("fiado", 0)),
        "total":     formatear_cop(r.get("total", 0)),
    }


def obtener_proveedores(tienda_id):
    return sb_get("proveedores", {
        "select":    "*",
        "tienda_id": f"eq.{tienda_id}",
        "activo":    "eq.true",
        "order":     "nombre.asc",
    })


def obtener_pedidos(tienda_id):
    rows = sb_get("pedidos", {
        "select":    "*,proveedores(nombre)",
        "tienda_id": f"eq.{tienda_id}",
        "order":     "created_at.desc",
    })
    return [{
        "id":         r.get("id"),
        "fecha":      r.get("fecha", ""),
        "proveedor":  (r.get("proveedores") or {}).get("nombre", ""),
        "total":      formatear_cop(r.get("total", 0)),
        "pagado_con": r.get("pagado_con", ""),
        "notas":      r.get("notas", ""),
    } for r in rows]


def obtener_inventario(tienda_id, solo_basico=False):
    select = "id,nombre,stock,stock_minimo" if solo_basico else "*,proveedores(nombre)"
    rows   = sb_get("inventario", {
        "select":    select,
        "tienda_id": f"eq.{tienda_id}",
        "activo":    "eq.true",
        "order":     "nombre.asc",
    })

    if solo_basico:
        return [{
            "id":              r.get("id"),
            "nombre":          r.get("nombre", ""),
            "stock":           r.get("stock", 0) or 0,
            "stock_minimo":    r.get("stock_minimo", 5),
            "precio_venta":    formatear_cop(0),
            "precio_venta_raw": 0,
            "stock_bajo":      (r.get("stock", 0) or 0) <= r.get("stock_minimo", 5),
        } for r in rows]

    productos = []
    for r in rows:
        pc    = r.get("precio_compra", 0) or 0
        pv    = r.get("precio_venta", 0) or 0
        stock = r.get("stock", 0) or 0
        sm    = r.get("stock_minimo", 5)
        productos.append({
            "id":               r.get("id"),
            "nombre":           r.get("nombre", ""),
            "proveedor":        (r.get("proveedores") or {}).get("nombre", ""),
            "stock":            stock,
            "stock_minimo":     sm,
            "precio_compra":    formatear_cop(pc),
            "precio_venta":     formatear_cop(pv),
            "precio_venta_raw": pv,
            "margen":           round(((pv - pc) / pc) * 100) if pc > 0 else 0,
            "stock_bajo":       stock <= sm,
        })
    return productos


def obtener_datos_inicio(tienda_id):
    VACIO = {"total_hoy": 0, "nequi_hoy": 0, "daviplata_hoy": 0, "efectivo_hoy": 0, "semana": [], "stock_bajo": 0, "total_productos": 0}
    try:
        # Ventas
        rows = sb_get("ventas", {
            "select":    "*",
            "tienda_id": f"eq.{tienda_id}",
            "order":     "fecha.desc",
            "limit":     "30",
        })
        hoy       = hoy_colombia()
        venta_hoy = next((r for r in rows if str(r.get("fecha", ""))[:10] == str(hoy)), None)
        DIAS      = ["Lun", "Mar", "Mie", "Jue", "Vie", "Sab", "Dom"]
        semana    = []
        for i in range(6, -1, -1):
            dia = hoy - timedelta(days=i)
            r   = next((x for x in rows if str(x.get("fecha", ""))[:10] == str(dia)), None)
            semana.append({
                "dia":       DIAS[dia.weekday()],
                "fecha":     str(dia),
                "total":     r.get("total", 0) if r else 0,
                "nequi":     r.get("nequi", 0) if r else 0,
                "daviplata": r.get("daviplata", 0) if r else 0,
                "efectivo":  r.get("efectivo", 0) if r else 0,
                "es_hoy":    dia == hoy,
            })
            
        # Inventario (Insights para el dashboard)
        inventario = sb_get("inventario", {
            "select":    "id,stock,stock_minimo",
            "tienda_id": f"eq.{tienda_id}",
            "activo":    "eq.true"
        })
        
        stock_bajo = sum(1 for p in inventario if (p.get("stock") or 0) <= p.get("stock_minimo", 5))
        total_productos = len(inventario)

        return {
            "total_hoy":     venta_hoy.get("total", 0) if venta_hoy else 0,
            "nequi_hoy":     venta_hoy.get("nequi", 0) if venta_hoy else 0,
            "daviplata_hoy": venta_hoy.get("daviplata", 0) if venta_hoy else 0,
            "efectivo_hoy":  venta_hoy.get("efectivo", 0) if venta_hoy else 0,
            "semana":        semana,
            "stock_bajo":    stock_bajo,
            "total_productos": total_productos,
        }
    except Exception as e:
        print("ERROR EN INICIO:", e)
        return VACIO


# ─────────────────────────────────────────
# RUTAS: AUTH
# ─────────────────────────────────────────
@app.route("/", methods=["GET", "POST"])
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        telefono = request.form.get("telefono", "").strip()
        password = request.form.get("password", "")
        try:
            usuarios = sb_get("usuarios", {
                "telefono": f"eq.{telefono}",
                "activo":   "eq.true",
                "select":   "*",
            })
            if not usuarios or not check_password_hash(usuarios[0]["password"], password):
                return render_template("login.html", error="Número o contraseña incorrectos")

            u = usuarios[0]
            session.permanent         = True
            session["usuario_id"]     = u["id"]
            session["tienda_id"]      = u["tienda_id"]
            session["usuario_nombre"] = u["nombre"]
            session["rol"]            = u["rol"]

            return redirect("/inicio")
        except Exception as e:
            return render_template("login.html", error=str(e))

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


@app.route("/registro")
def registro():
    return render_template("registro.html")


@app.route("/crear-cuenta", methods=["POST"])
def crear_cuenta():
    try:
        data          = request.json
        nombre_tienda = data.get("nombre_tienda", "").strip()
        nombre_admin  = data.get("nombre_admin", "").strip()
        telefono      = data.get("telefono", "").strip()
        correo        = data.get("correo", "").strip().lower()
        password      = data.get("password", "")
        confirmar     = data.get("confirmar", "")

        if not all([nombre_tienda, nombre_admin, telefono, correo, password]):
            return jsonify({"ok": False, "error": "Todos los campos son obligatorios"})
        if password != confirmar:
            return jsonify({"ok": False, "error": "Las contraseñas no coinciden"})
        if sb_get("usuarios", {"telefono": f"eq.{telefono}", "select": "id"}):
            return jsonify({"ok": False, "error": "Ese número ya está registrado"})
        if sb_get("usuarios", {"correo": f"eq.{correo}", "select": "id"}):
            return jsonify({"ok": False, "error": "Ese correo ya está registrado"})

        ok, tienda = sb_post("tiendas", {"nombre": nombre_tienda})
        if not ok:
            return jsonify({"ok": False, "error": tienda})

        ok, usuario = sb_post("usuarios", {
            "nombre":    nombre_admin,
            "telefono":  telefono,
            "correo":    correo,
            "password":  generate_password_hash(password),
            "rol":       "dueno",
            "tienda_id": tienda[0]["id"],
            "activo":    True,
        })
        if not ok:
            return jsonify({"ok": False, "error": usuario})

        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})


# ─────────────────────────────────────────
# RUTAS: USUARIOS
# ─────────────────────────────────────────
@app.route("/usuarios")
@rol_requerido("dueno", "admin")
def usuarios():
    tienda_id = session["tienda_id"]
    lista     = sb_get("usuarios", {
        "select":    "id,nombre,telefono,correo,rol,activo",
        "tienda_id": f"eq.{tienda_id}",
        "order":     "nombre.asc",
    })
    return render_template("usuarios.html", usuarios=lista, modulo="usuarios")


@app.route("/crear-usuario", methods=["POST"])
@rol_requerido("dueno", "admin")
def crear_usuario():
    try:
        data      = request.json
        tienda_id = session["tienda_id"]
        rol       = data.get("rol", "vendedor")

        if session["rol"] == "admin" and rol in ("dueno", "admin"):
            return jsonify({"ok": False, "error": "No tienes permiso para crear ese rol"}), 403

        telefono = data.get("telefono", "").strip()
        correo   = data.get("correo", "").strip().lower()
        password = data.get("password", "")

        if not password:
            return jsonify({"ok": False, "error": "Debes asignar una contraseña temporal"})
        if sb_get("usuarios", {"telefono": f"eq.{telefono}", "select": "id"}):
            return jsonify({"ok": False, "error": "Ese número ya está registrado"})
        if correo and sb_get("usuarios", {"correo": f"eq.{correo}", "select": "id"}):
            return jsonify({"ok": False, "error": "Ese correo ya está registrado"})

        ok, res = sb_post("usuarios", {
            "nombre":    data.get("nombre", "").strip(),
            "telefono":  telefono,
            "correo":    correo,
            "password":  generate_password_hash(password),
            "rol":       rol,
            "tienda_id": tienda_id,
            "activo":    True,
        })
        if not ok:
            return jsonify({"ok": False, "error": res}), 500

        return jsonify({"ok": True, "usuario": res[0]})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/desactivar-usuario", methods=["POST"])
@rol_requerido("dueno", "admin")
def desactivar_usuario():
    try:
        data       = request.json
        usuario_id = data.get("id")
        tienda_id  = session["tienda_id"]

        if str(usuario_id) == str(session["usuario_id"]):
            return jsonify({"ok": False, "error": "No puedes desactivarte a ti mismo"}), 400

        if not verificar_ownership("usuarios", usuario_id, tienda_id):
            return jsonify({"ok": False, "error": "Usuario no encontrado"}), 404

        ok, err = sb_patch("usuarios", f"id=eq.{usuario_id}", {"activo": False})
        if not ok:
            return jsonify({"ok": False, "error": err}), 500

        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


# ─────────────────────────────────────────
# RUTAS: PÁGINAS
# ─────────────────────────────────────────
@app.route("/inicio")
@login_requerido
def inicio():
    tienda_id = session["tienda_id"]
    datos     = obtener_datos_inicio(tienda_id)
    tiendas   = sb_get("tiendas", {"id": f"eq.{tienda_id}", "select": "nombre"})
    tienda    = tiendas[0] if tiendas else {"nombre": "Mi tienda"}
    return render_template("inicio.html",
        modulo="inicio",
        datos=datos,
        tienda=tienda,
    )


@app.route("/ventas")
@login_requerido
def ventas():
    """Nueva sección: punto de venta / facturación."""
    tienda_id   = session["tienda_id"]
    rol         = session.get("rol", "")
    solo_basico = rol == "vendedor"
    productos   = obtener_inventario(tienda_id, solo_basico=solo_basico)
    return render_template("ventas.html",
        modulo="ventas",
        productos=productos,
    )


@app.route("/cierre")
@login_requerido
def cierre():
    """Cierre de caja (lo que antes era /ventas)."""
    tienda_id = session["tienda_id"]
    rol       = session.get("rol", "")

    if rol == "vendedor":
        cierre_hoy = obtener_cierre_hoy(tienda_id)
        return render_template("cierre.html",
            ventas=[cierre_hoy] if cierre_hoy else [],
            solo_hoy=True,
            modulo="cierre",
        )

    return render_template("cierre.html",
        ventas=obtener_cierres(tienda_id),
        solo_hoy=False,
        modulo="cierre",
    )


@app.route("/pedidos")
@rol_requerido("dueno", "admin")
def pedidos():
    tienda_id = session["tienda_id"]
    return render_template("pedidos.html",
        pedidos=obtener_pedidos(tienda_id),
        proveedores=obtener_proveedores(tienda_id),
        modulo="pedidos",
    )


@app.route("/inventario")
@login_requerido
def inventario():
    tienda_id   = session["tienda_id"]
    rol         = session.get("rol", "")
    solo_basico = rol == "vendedor"
    productos   = obtener_inventario(tienda_id, solo_basico=solo_basico)

    return render_template("inventario.html",
        modulo="inventario",
        productos=productos,
        proveedores=[] if solo_basico else obtener_proveedores(tienda_id),
        total_productos=len(productos),
        stock_bajo=sum(1 for p in productos if p["stock_bajo"]),
        alta_rotacion=sum(1 for p in productos if not solo_basico and p.get("margen", 0) >= 25),
        solo_basico=solo_basico,
    )


@app.route("/analisis")
@rol_requerido("dueno", "admin")
def analisis():
    return render_template("analisis.html", modulo="analisis")


# ─────────────────────────────────────────
# RUTAS: API — VENTAS POS
# ─────────────────────────────────────────
@app.route("/registrar-venta", methods=["POST"])
@login_requerido
def registrar_venta():
    """Registra una venta del POS en ventas_productos + venta_items y descuenta stock."""
    try:
        data      = request.json
        tienda_id = session["tienda_id"]
        metodo    = data.get("metodo", "")
        total     = data.get("total", 0)
        items     = data.get("items", [])
        ahora     = datetime.now(COL_TZ)

        # 1. Cabecera
        ok, res = sb_post("ventas_productos", {
            "tienda_id":   tienda_id,
            "metodo_pago": metodo,
            "total":       total,
        })
        if not ok:
            return jsonify({"ok": False, "error": res}), 500

        venta_id = res[0]["id"]

        # 2. Traer inventario una sola vez
        inventario = sb_get("inventario", {
            "select":    "id,stock",
            "tienda_id": f"eq.{tienda_id}",
            "activo":    "eq.true",
        })
        inv_map = {p["id"]: p for p in inventario}

        # 3. Guardar items y descontar stock
        for item in items:
            sb_post("venta_items", {
                "venta_id":        venta_id,
                "producto_id":     item.get("producto_id"),
                "cantidad":        item.get("cantidad"),
                "precio_unitario": item.get("precio"),
                "subtotal":        item.get("subtotal"),
            })
            prod = inv_map.get(item.get("producto_id"))
            if prod:
                nuevo = max(0, prod["stock"] - item.get("cantidad", 1))
                sb_patch("inventario", f"id=eq.{prod['id']}", {"stock": nuevo})

        resumen = ", ".join(f'{i["nombre"]} x{i["cantidad"]}' for i in items)
        return jsonify({
            "ok":     True,
            "total":  total,
            "hora":   ahora.strftime("%H:%M"),
            "metodo": metodo,
            "resumen": resumen,
        })
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

# ─────────────────────────────────────────
# RUTAS: API — CIERRE DE CAJA
# ─────────────────────────────────────────
@app.route("/guardar-venta", methods=["POST"])
@login_requerido
def guardar_venta():
    """Guarda el cierre de caja diario en la tabla ventas."""
    try:
        data      = request.json
        tienda_id = session["tienda_id"]
        nequi     = parse_num(data.get("nequi", 0))
        daviplata = parse_num(data.get("daviplata", 0))
        efectivo  = parse_num(data.get("efectivo", 0))
        fiado     = parse_num(data.get("fiado", 0))
        total     = nequi + daviplata + efectivo + fiado
        fecha     = data.get("fecha", "")

        if session.get("rol") == "vendedor" and fecha != str(hoy_colombia()):
            return jsonify({"ok": False, "error": "Solo puedes registrar ventas del día de hoy"}), 403

        ok, res = sb_post("ventas", {
            "fecha": fecha, "tienda_id": tienda_id,
            "nequi": nequi, "daviplata": daviplata,
            "efectivo": efectivo, "fiado": fiado, "total": total,
        })
        if not ok:
            return jsonify({"ok": False, "error": res}), 500

        return jsonify({
            "ok": True, "fecha": fecha,
            "nequi":     formatear_cop(nequi),
            "daviplata": formatear_cop(daviplata),
            "efectivo":  formatear_cop(efectivo),
            "fiado":     formatear_cop(fiado),
            "total":     formatear_cop(total),
        })
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


# ─────────────────────────────────────────
# RUTAS: API — RESTO (solo admin/dueno)
# ─────────────────────────────────────────
@app.route("/guardar-proveedor", methods=["POST"])
@rol_requerido("dueno", "admin")
def guardar_proveedor():
    try:
        data = request.json
        ok, res = sb_post("proveedores", {
            "nombre":    data.get("nombre", "").strip(),
            "tienda_id": session["tienda_id"],
            "telefono":  data.get("telefono", "").strip(),
            "categoria": data.get("categoria", "normal"),
            "activo":    True,
            "tipo_proveedor": data.get("tipo_proveedor", "otro"),
            "dias_visita": data.get("dias_visita", []),
            "dias_entrega": data.get("dias_entrega", []),
            "frecuencia_visita": data.get("frecuencia_visita", "semanal"),
            "tiempo_entrega_dias": int(data.get("tiempo_entrega_dias") or 0),
            "horario_visita": data.get("horario_visita", "").strip(),
            "acepta_credito": bool(data.get("acepta_credito", False)),
            "dias_credito": int(data.get("dias_credito") or 0),
            "observaciones": data.get("observaciones", "").strip(),
        })
        if not ok:
            return jsonify({"ok": False, "error": res}), 500
        return jsonify({"ok": True, "proveedor": res[0]})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/guardar-producto", methods=["POST"])
@rol_requerido("dueno", "admin")
def guardar_producto():
    try:
        data         = request.json
        tienda_id    = session["tienda_id"]
        proveedor_id = data.get("proveedor_id")

        if proveedor_id and not verificar_ownership("proveedores", proveedor_id, tienda_id):
            return jsonify({"ok": False, "error": "Proveedor no válido"}), 403

        ok, res = sb_post("inventario", {
            "nombre":        data.get("nombre", "").strip(),
            "tienda_id":     tienda_id,
            "proveedor_id":  proveedor_id or None,
            "stock":         int(data.get("stock", 0)),
            "stock_minimo":  int(data.get("stock_minimo", 5)),
            "precio_compra": parse_num(data.get("precio_compra", 0)),
            "precio_venta":  parse_num(data.get("precio_venta", 0)),
            "activo":        True,
        })
        if not ok:
            return jsonify({"ok": False, "error": res}), 500
        return jsonify({"ok": True, "producto": res[0]})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/actualizar-stock", methods=["POST"])
@rol_requerido("dueno", "admin")
def actualizar_stock():
    try:
        data       = request.json
        product_id = data.get("id")
        tienda_id  = session["tienda_id"]

        productos = sb_get("inventario", {
            "id":        f"eq.{product_id}",
            "tienda_id": f"eq.{tienda_id}",
            "select":    "stock",
        })
        if not productos:
            return jsonify({"ok": False, "error": "Producto no encontrado"}), 404

        nuevo_stock = max(0, productos[0].get("stock", 0) + int(data.get("delta", 0)))
        ok, err = sb_patch("inventario", f"id=eq.{product_id}", {"stock": nuevo_stock})
        if not ok:
            return jsonify({"ok": False, "error": err}), 500

        return jsonify({"ok": True, "stock": nuevo_stock})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/guardar-pedido", methods=["POST"])
@rol_requerido("dueno", "admin")
def guardar_pedido():
    try:
        data         = request.json
        tienda_id    = session["tienda_id"]
        items        = data.get("items", [])
        total        = sum(parse_num(i.get("subtotal", 0)) for i in items)
        proveedor_id = data.get("proveedor_id")

        if proveedor_id and not verificar_ownership("proveedores", proveedor_id, tienda_id):
            return jsonify({"ok": False, "error": "Proveedor no válido"}), 403

        ok, pedido = sb_post("pedidos", {
            "fecha":        data.get("fecha", ""),
            "tienda_id":    tienda_id,
            "proveedor_id": proveedor_id,
            "total":        total,
            "pagado_con":   data.get("pagado_con", ""),
            "notas":        data.get("notas", ""),
        })
        if not ok:
            return jsonify({"ok": False, "error": pedido}), 500

        pedido_id = pedido[0]["id"]

        for item in items:
            pc_final = parse_num(item.get("precio_compra_final", 0))
            cantidad = int(item.get("cantidad", 1))
            sb_post("pedido_items", {
                "pedido_id":           pedido_id,
                "producto_nombre":     item.get("producto_nombre", ""),
                "cantidad":            cantidad,
                "precio_compra":       parse_num(item.get("precio_compra", 0)),
                "iva":                 parse_num(item.get("iva", 0)),
                "precio_compra_final": pc_final,
                "precio_venta":        parse_num(item.get("precio_venta", 0)),
                "subtotal":            pc_final * cantidad,
            })

        inventario = sb_get("inventario", {
            "select":    "id,stock,nombre",
            "tienda_id": f"eq.{tienda_id}",
            "activo":    "eq.true",
        })
        inv_map = {p.get("nombre", "").strip().lower(): p for p in inventario}

        for item in items:
            nombre   = item.get("producto_nombre", "").strip().lower()
            cantidad = int(item.get("cantidad", 1))
            producto = inv_map.get(nombre)
            if producto:
                sb_patch("inventario", f"id=eq.{producto['id']}",
                         {"stock": producto.get("stock", 0) + cantidad})

        return jsonify({"ok": True, "pedido_id": pedido_id, "total": formatear_cop(total)})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


# ─────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=not IS_PROD)