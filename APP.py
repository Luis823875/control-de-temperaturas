import datetime
import io
import threading
import time
import mysql.connector
import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
import serial.tools.list_ports
import streamlit as st

# ==========================================
# 1. FUNCIÓN DE LECTURA SERIAL EN SEGUNDO PLANO
# ==========================================


def obtener_puerto_automatico():
  puertos = list(serial.tools.list_ports.comports())
  for puerto in puertos:
    desc = puerto.description.lower()
    if (
        "arduino" in desc
        or "ch340" in desc
        or "cp210x" in desc
        or "usb-serial" in desc
    ):
      return puerto.device
  if puertos:
    return puertos[0].device
  return None


def background_reader():
  """Hilo en segundo plano para leer del Arduino y guardar en Aiven"""
  while True:
    try:
      conexion = mysql.connector.connect(
          host="data-center-data-center.l.aivencloud.com",
          port=12378,
          user="avnadmin",
          password="AVNS_DzxpEWnJIXz1PbKi3Ck",
          database="defaultdb",
          ssl_disabled=True,
      )
      cursor = conexion.cursor()

      puerto = obtener_puerto_automatico()
      if not puerto:
        time.sleep(3)
        continue

      ser = serial.Serial(puerto, 115200, timeout=2)
      time.sleep(2)

      while True:
        linea = ser.readline().decode("utf-8", errors="ignore").strip()
        if "Dato recibido:" in linea:
          try:
            partes = linea.split("Dato recibido:")[1].split(",")
            t = float(partes[0].strip())
            h = float(partes[1].strip())

            # Forzamos la hora actual de Perú (-5 horas si el servidor guarda UTC)
            sql = "INSERT INTO lecturas (temperatura, humedad, fecha_registro) VALUES (%s, %s, NOW() - INTERVAL 5 HOUR)"
            cursor.execute(sql, (t, h))
            conexion.commit()
          except Exception:
            pass
        time.sleep(1)
    except Exception:
      time.sleep(5)


if "hilo_iniciado" not in st.session_state:
  st.session_state["hilo_iniciado"] = True
  t_thread = threading.Thread(target=background_reader, daemon=True)
  t_thread.start()


# ==========================================
# 2. CONFIGURACIÓN DE LA INTERFAZ STREAMLIT
# ==========================================
st.set_page_config(
    page_title="Monitoreo IoT - CICSA", page_icon="📊", layout="wide"
)

st.title("📊 Centro de Monitoreo IoT - CICSA")
st.markdown(
    "Sistema automatizado: Lectura de sensor DHT22, almacenamiento en Aiven"
    " MySQL y generación de reportes en PDF."
)
st.markdown("---")

try:
  conn_ui = mysql.connector.connect(
      host="data-center-data-center.l.aivencloud.com",
      port=12378,
      user="avnadmin",
      password="AVNS_DzxpEWnJIXz1PbKi3Ck",
      database="defaultdb",
      ssl_disabled=True,
  )
  cursor_ui = conn_ui.cursor()
  # Ajustamos la consulta para restar 5 horas directamente si el servidor está en UTC
  cursor_ui.execute(
      "SELECT id, temperatura, humedad, fecha_registro FROM lecturas ORDER BY id"
      " DESC LIMIT 15"
  )
  registros = cursor_ui.fetchall()
except Exception as e:
  st.error(f"Error de conexión a la base de datos: {e}")
  registros = []


def generar_pdf_bytes(registros, prom_temp, prom_hum):
  buffer = io.BytesIO()
  doc = SimpleDocTemplate(
      buffer,
      pagesize=letter,
      rightMargin=36,
      leftMargin=36,
      topMargin=36,
      bottomMargin=36,
  )
  elementos = []

  styles = getSampleStyleSheet()
  titulo_style = ParagraphStyle(
      "TituloEmpresa",
      parent=styles["Heading1"],
      fontName="Helvetica-Bold",
      fontSize=13,
      textColor=colors.black,
      spaceAfter=4,
  )
  sub_style = ParagraphStyle(
      "SubTitulo",
      parent=styles["Normal"],
      fontName="Helvetica",
      fontSize=10,
      textColor=colors.HexColor("#595959"),
      spaceAfter=15,
  )

  elementos.append(Paragraph("EMPRESA: CICSA", titulo_style))
  elementos.append(
      Paragraph(
          f"Reporte de Monitoreo IoT (Sensor DHT22) — Generado el"
          f" {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
          sub_style,
      )
  )
  elementos.append(Spacer(1, 10))

  data_tabla = [["ID", "Temperatura (°C)", "Humedad (%)", "Fecha y Hora"]]
  for reg in registros:
    # Ajustar visualmente la hora restando 5 horas si viene de UTC
    fecha_Peru = reg[3] - datetime.timedelta(hours=5) if reg[3] else reg[3]
    data_tabla.append(
        [str(reg[0]), f"{reg[1]:.1f} °C", f"{reg[2]:.1f} %", str(fecha_Peru)]
    )

  data_tabla.append(
      ["Promedio", f"{prom_temp:.1f} °C", f"{prom_hum:.1f} %", "-"]
  )

  tabla = Table(data_tabla, colWidths=[50, 115, 115, 220])
  tabla.setStyle(
      TableStyle([
          ("BACKGROUND", (0, 0), (-1, 0), colors.black),
          ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
          ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
          ("FONTSIZE", (0, 0), (-1, 0), 10),
          ("ALIGN", (0, 0), (-1, -1), "CENTER"),
          ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
          ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
          ("TOPPADDING", (0, 0), (-1, -1), 6),
          ("GRID", (0, 0), (-1, -2), 0.5, colors.HexColor("#CCCCCC")),
          ("LINEABOVE", (0, -1), (-1, -1), 1, colors.black),
          ("LINEBELOW", (0, -1), (-1, -1), 1.5, colors.black),
          ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
          ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#F2F2F2")),
      ])
  )

  elementos.append(tabla)
  doc.build(elementos)
  buffer.seek(0)
  return buffer.getvalue()


if registros:
  temps = [r[1] for r in registros]
  hums = [r[2] for r in registros]
  prom_temp = sum(temps) / len(temps)
  prom_hum = sum(hums) / len(hums)

  col1, col2 = st.columns(2)
  col1.metric("Temperatura Actual", f"{temps[0]:.1f} °C")
  col2.metric("Humedad Actual", f"{hums[0]:.1f} %")

  st.subheader("📋 Últimos Registros Guardados")

  # Creamos una copia para mostrar la hora ajustada en la tabla web
  registros_ajustados = []
  for r in registros:
    f_peru = r[3] - datetime.timedelta(hours=5) if r[3] else r[3]
    registros_ajustados.append((r[0], r[1], r[2], f_peru))

  df = pd.DataFrame(
      registros_ajustados,
      columns=["ID", "Temperatura (°C)", "Humedad (%)", "Fecha y Hora"],
  )
  st.dataframe(df, use_container_width=True)

  st.markdown("### Generar Reporte Formal")

  pdf_bytes = generar_pdf_bytes(registros, prom_temp, prom_hum)

  st.download_button(
      label="📥 Descargar Reporte en PDF (CICSA)",
      data=pdf_bytes,
      file_name="reporte_cicsa.pdf",
      mime="application/pdf",
  )
else:
  st.warning(
      "Conectando al sensor o esperando registros en la base de datos..."
  )