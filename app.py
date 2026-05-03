# Proyecto N-1 Automatizacion de Formularios a base de datos Excel
# Nicolas Becerra - 30/04/26
# Modulo Web - Flask backend con Supabase - Version 2.0

from flask import Flask, render_template, request, jsonify
from datetime import date, timedelta
import requests
import os

app = Flask(__name__)

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
            params={"select": "*", "order": "created_at.desc"}
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


# Devuelve todos los proveedores activos ordenados por nombre
def obtener_proveedores():
    try:
        res = requests.get(
            f"{SUPABASE_URL}/rest/v1/proveedores",
            headers=HEADERS,
            params={"select": "*", "activo": "eq.true", "order": "nombre.asc"}
        )
        return res.json()
    except Exception:
        return []


# Devuelve todos los pedidos con su proveedor asociado
def obtener_pedidos():
    try:
        res = requests.get(
            f"{SUPABASE_URL}/rest/v1/pedidos",
            headers=HEADERS,
            params={"select": "*,proveedores(nombre)", "order": "created_at.desc"}
        )
        pedidos = []
        for row in res.json():
            pedidos.append({
                "id": row.get("id"),
                "fecha": row.get("fecha", ""),
                "proveedor": row.get("proveedores", {}).get("nombre", "") if row.get("proveedores") else "",
                "total": formatear_cop(row.get("total", 0)),
                "pagado_con": row.get("pagado_con", ""),
                "notas": row.get("notas", ""),
            })
        return pedidos
    except Exception:
        return []


# Obtiene ventas de hoy y de los ultimos 7 dias para el dashboard de inicio
def obtener_datos_inicio():
    try:
        res = requests.get(
            f"{SUPABASE_URL}/rest/v1/ventas",
            headers=HEADERS,
            params={"select": "*", "order": "fecha.desc", "limit": "30"}
        )
        rows = res.json()
        hoy = date.today()

        # Ventas de hoy
        venta_hoy = next((r for r in rows if str(r.get("fecha", ""))[:10] == str(hoy)), None)
        total_hoy = venta_hoy.get("total", 0) if venta_hoy else 0
        nequi_hoy = venta_hoy.get("nequi", 0) if venta_hoy else 0
        daviplata_hoy = venta_hoy.get("daviplata", 0) if venta_hoy else 0
        efectivo_hoy = venta_hoy.get("efectivo", 0) if venta_hoy else 0

        # Ventas de los ultimos 7 dias para la grafica
        dias_semana = ["Lun", "Mar", "Mie", "Jue", "Vie", "Sab", "Dom"]
        semana = []
        for i in range(6, 0, -1):
            dia = hoy - timedelta(days=i)
            row = next((r for r in rows if str(r.get("fecha", ""))[:10] == str(dia)), None)
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
    except Exception:
        return {
            "total_hoy": 0,
            "nequi_hoy": 0,
            "daviplata_hoy": 0,
            "efectivo_hoy": 0,
            "semana": [],
        }


# Ruta principal - pagina de inicio con resumen del dia
@app.route("/")
def inicio():
    datos = obtener_datos_inicio()
    return render_template("inicio.html", modulo="inicio", datos=datos)


# Ruta del modulo de ventas diarias
@app.route("/ventas")
def ventas():
    datos = obtener_ventas()
    return render_template("ventas.html", ventas=datos, modulo="ventas")


# Ruta del modulo de pedidos y proveedores
@app.route("/pedidos")
def pedidos():
    datos_pedidos = obtener_pedidos()
    datos_proveedores = obtener_proveedores()
    return render_template("pedidos.html", pedidos=datos_pedidos, proveedores=datos_proveedores, modulo="pedidos")


# Ruta del modulo de inventario
@app.route("/inventario")
def inventario():
    return render_template("inventario.html", modulo="inventario")


# Ruta del modulo de analisis y dashboard
@app.route("/analisis")
def analisis():
    return render_template("analisis.html", modulo="analisis")


# Guarda los datos del formulario de ventas en Supabase
@app.route("/guardar-venta", methods=["POST"])
def guardar_venta():
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
            return jsonify({"ok": False, "error": res.text}), 500

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
        return jsonify({"ok": False, "error": str(e)}), 500


# Guarda un proveedor nuevo en Supabase
@app.route("/guardar-proveedor", methods=["POST"])
def guardar_proveedor():
    try:
        data = request.json
        payload = {
            "nombre": data.get("nombre", "").strip(),
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
    try:
        data = request.json
        fecha = data.get("fecha", "")
        proveedor_id = data.get("proveedor_id")
        pagado_con = data.get("pagado_con", "")
        notas = data.get("notas", "")
        items = data.get("items", [])
        total = sum(parse_num(item.get("subtotal", 0)) for item in items)

        # Guardar cabecera del pedido
        pedido_payload = {
            "fecha": fecha,
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
            return jsonify({"ok": False, "error": res_pedido.text}), 500

        pedido_id = res_pedido.json()[0]["id"]

        # Guardar cada item del pedido
        for item in items:
            precio_compra = parse_num(item.get("precio_compra", 0))
            iva = parse_num(item.get("iva", 0))
            precio_compra_final = parse_num(item.get("precio_compra_final", 0))
            precio_venta = parse_num(item.get("precio_venta", 0))
            cantidad = int(item.get("cantidad", 1))
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

        return jsonify({"ok": True, "pedido_id": pedido_id, "total": formatear_cop(total)})

    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)