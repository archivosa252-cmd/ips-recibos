from flask import Flask, render_template, request
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
import os
from datetime import datetime
import base64
import pickle

# ==============================
# GOOGLE DRIVE OAUTH
# ==============================
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

app = Flask(__name__)

SCOPES = ['https://www.googleapis.com/auth/drive.file']

# ==============================
# OBTENER SERVICIO DRIVE (SE EJECUTA SOLO CUANDO SE NECESITA)
# ==============================
def obtener_servicio_drive():
    token_base64 = os.environ.get("TOKEN_PICKLE")

    if not token_base64:
        print("⚠️ TOKEN_PICKLE no configurado en Render")
        return None

    try:
        token_bytes = base64.b64decode(token_base64)
        creds = pickle.loads(token_bytes)

        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())

        return build('drive', 'v3', credentials=creds)

    except Exception as e:
        print("❌ Error creando servicio Drive:", e)
        return None


# ==============================
# CREAR O OBTENER CARPETA
# ==============================
def obtener_o_crear_carpeta(drive_service, nombre_carpeta):
    query = f"name='{nombre_carpeta}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
    resultados = drive_service.files().list(q=query, spaces='drive').execute()
    items = resultados.get('files', [])

    if items:
        return items[0]['id']
    else:
        metadata = {
            'name': nombre_carpeta,
            'mimeType': 'application/vnd.google-apps.folder'
        }
        carpeta = drive_service.files().create(body=metadata, fields='id').execute()
        return carpeta['id']


# ==============================
# RUTA PRINCIPAL
# ==============================
@app.route('/')
def formulario():
    return render_template('formulario.html')


# ==============================
# GENERAR PDF
# ==============================
@app.route('/generar', methods=['POST'])
def generar_pdf():

    drive_service = obtener_servicio_drive()

    nombre = request.form['nombre']
    documento = request.form['documento']
    servicio = request.form['servicio']
    modalidad = request.form['modalidad']
    firma_base64 = request.form['firma_base64']

    if not os.path.exists("temp"):
        os.makedirs("temp")

    fecha_actual = datetime.now().strftime('%d/%m/%Y')
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')

    archivo_pdf = f"temp/recibo_{documento}_{timestamp}.pdf"
    archivo_firma = f"temp/firma_{timestamp}.png"

    # Guardar firma
    if firma_base64:
        firma_data = firma_base64.split(",")[1]
        with open(archivo_firma, "wb") as f:
            f.write(base64.b64decode(firma_data))

    # Crear PDF
    doc = SimpleDocTemplate(archivo_pdf, pagesize=letter)
    elementos = []
    estilos = getSampleStyleSheet()

    estilo_normal = ParagraphStyle(
        'normal',
        parent=estilos['Normal'],
        fontSize=12.5,
        leading=16
    )

    encabezado_path = "static/encabezado.png"
    if os.path.exists(encabezado_path):
        elementos.append(Image(encabezado_path, width=6*inch, height=1.8*inch))
        elementos.append(Spacer(1, 30))

    domicilio = "( X )" if modalidad == "Domicilio" else "(   )"
    ips = "( X )" if modalidad == "Recibido en IPS" else "(   )"

    texto = f"""
    Por medio de la presente certifico que el usuario: {nombre}
    identificado con documento: {documento}
    ha recibido el servicio de: {servicio}
    prestado de manera: {domicilio} domicilio   {ips} IPS.

    Firmo a satisfacción.
    """

    elementos.append(Paragraph(texto.replace("\n", "<br/>"), estilo_normal))
    elementos.append(Spacer(1, 40))

    if os.path.exists(archivo_firma):
        elementos.append(Image(archivo_firma, width=2.8*inch, height=1.2*inch))
        elementos.append(Spacer(1, 10))

    elementos.append(Paragraph("__________________________________________", estilo_normal))
    elementos.append(Spacer(1, 10))
    elementos.append(Paragraph(f"Fecha: {fecha_actual}", estilo_normal))

    doc.build(elementos)

    # ==============================
    # SUBIR A DRIVE (SI ESTÁ DISPONIBLE)
    # ==============================
    if drive_service:
        try:
            carpeta_id = obtener_o_crear_carpeta(drive_service, "RECIBOS_IPS_AUTOMATICO")

            file_metadata = {
                'name': os.path.basename(archivo_pdf),
                'parents': [carpeta_id]
            }

            media = MediaFileUpload(archivo_pdf, mimetype='application/pdf')

            drive_service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id'
            ).execute()

            return "PDF generado y guardado en Drive correctamente ✅"

        except Exception as e:
            print("❌ Error subiendo a Drive:", e)
            return "PDF generado, pero hubo un error al subir a Drive ⚠️"

    else:
        return "PDF generado, pero Drive no está configurado ⚠️"


# ==============================
# CONFIGURACIÓN RENDER
# ==============================
if __name__ == '__main__':
    app.run(
        host='0.0.0.0',
        port=int(os.environ.get("PORT", 10000))
    )