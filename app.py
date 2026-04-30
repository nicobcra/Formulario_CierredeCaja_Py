#Proyecto N-1 Automatizacion de Formularios a base de datos Excel
#Nicolas Becerra - 30/04/26
#Modulo Web - Flask backend con Supabase

from flask import Flask, render_template, request, jsonify
import requests
import os

app = Flask(__name__)

# Credenciales Supabase
SUPABASE_URL  = "https://brumjdswhdzkoftmxjmx.supabase.co"
SUPABASE_KEY  = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImJydW1qZHN3aGR6a29mdG14am14Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3Nzc1NjYzNDQsImV4cCI6MjA5MzE0MjM0NH0.YNypTWAsfcDxDrTmwlObEfPspnlHwyKHDx2t5yKXDEg"
TABLA         = "ventas"

# Headers que van en cada peticion a Supabase
HEADERS = {
    "apikey":        SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type":  "application/json",
    "Prefer":        "return=representation",
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
            f"{SUPABASE_URL}/rest/v1/{TABLA}",
            headers=HEADERS,
            params={"select": "*", "order": "created_at.desc"}
        )
        ventas = []
        for row in res.json():
            ventas.append({
                "fecha":     row.get("fecha", ""),
                "nequi":     formatear_cop(row.get("nequi", 0)),
                "daviplata": formatear_cop(row.get("daviplata", 0)),
                "efectivo":  formatear_cop(row.get("efectivo", 0)),
                "fiado":     formatear_cop(row.get("fiado", 0)),
                "total":     formatear_cop(row.get("total", 0)),
            })
        return ventas
    except Exception:
        return []

# Ruta principal que carga el formulario y el historial
@app.route("/")
def index():
    ventas = obtener_ventas()
    return render_template("index.html", ventas=ventas)

# Guarda los datos del formulario en Supabase
@app.route("/guardar", methods=["POST"])
def guardar_venta():
    try:
        data      = request.json
        fecha     = data.get("fecha", "")
        nequi     = parse_num(data.get("nequi", 0))
        daviplata = parse_num(data.get("daviplata", 0))
        efectivo  = parse_num(data.get("efectivo", 0))
        fiado     = parse_num(data.get("fiado", 0))
        total     = nequi + daviplata + efectivo + fiado

        payload = {
            "fecha":     fecha,
            "nequi":     nequi,
            "daviplata": daviplata,
            "efectivo":  efectivo,
            "fiado":     fiado,
            "total":     total,
        }

        res = requests.post(
            f"{SUPABASE_URL}/rest/v1/{TABLA}",
            headers=HEADERS,
            json=payload
        )

        if res.status_code not in (200, 201):
            return jsonify({"ok": False, "error": res.text}), 500

        return jsonify({
            "ok":        True,
            "fecha":     fecha,
            "nequi":     formatear_cop(nequi),
            "daviplata": formatear_cop(daviplata),
            "efectivo":  formatear_cop(efectivo),
            "fiado":     formatear_cop(fiado),
            "total":     formatear_cop(total),
        })

    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)