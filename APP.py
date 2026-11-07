from datetime import datetime
import io
import time
import pandas as pd
import pywhatkit as kit
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
import serial
import serial.tools.list_ports
import streamlit as st

# ==========================================
# CONFIGURACIÓN GENERAL Y DETECCIÓN AUTOMÁTICA
# ==========================================
st.set_page_config(
    page_title="Monitoreo IoT - CICSA", layout="wide"
)

st.title("🖥️ Centro de Datos con Alertas y Auditoría Crítica")
st.markdown("Monitoreo en tiempo real de Temperatura y Humedad (DHT22)")

BAUDIOS = 115200
NUMERO_CELULAR = "+51924203754"  # Tu número configurado
LIMITE_TEMPERATURA = 30.0  # Límite crítico para disparar la alerta

TIEMPO_ESPERA_ALERTA = 300
if "ultima_alerta" not in st.session_state:
  st.session_state.ultima_alerta = 0

# Inicializar memoria para valores y el historial de la tabla
if "temp_actual" not in st.session_state:
  st.session_state.temp_actual = 0.0
if "hum_actual" not in st.session_state:
  st.session_state.hum_actual = 0.0
if "historial" not in st.session_state:
  st.session_state.historial = []


def detectar_puerto_arduino():
  """Busca automáticamente el puerto COM donde está conectado el Arduino."""
  puertos = serial.tools.list_ports.comports()
  for puerto in puertos:
    descripcion = puerto.description.lower()
    if (
        "arduino" in descripcion
        or "ch340" in descripcion
        or "usb-serial" in descripcion
        or "usb serial" in descripcion
    ):
      return puerto.device
  if puertos:
    return puertos[0].device
  return None


# ==========================================
# FUNCIÓN DE ALERTA POR WHATSAPP
# ==========================================


def enviar_alerta_whatsapp(temp_actual):
  tiempo_actual = time.time()
  if tiempo_actual - st.session_state.ultima_alerta > TIEMPO_ESPERA_ALERTA:
    mensaje = (
        f"🚨 ¡ALERTA CRÍTICA EN EL CENTRO DE DATOS! 🚨\nTemperatura alta"
        f" detectada: {temp_actual}°C"
    )
    try:
      kit.sendwhatmsg_instantly(
          NUMERO_CELULAR, mensaje, wait_time=10, tab_close=True
      )
      st.session_state.ultima_alerta = tiempo_actual
      print("¡Alerta de WhatsApp enviada con éxito!")
    except Exception as e:
      print(f"Error al enviar WhatsApp: {e}")


# ==========================================
# FUNCIÓN PARA GENERAR PDF CON EL FORMATO DE TABLA EXACTO
# ==========================================


def generar_pdf(historial_registros):
  buffer = io.BytesIO()
  doc = SimpleDocTemplate(
      buffer,
      pagesize=letter,
      rightMargin=30,
      leftMargin=30,
      topMargin=30,
      bottomMargin=30,
  )
  elementos = []
  estilos = getSampleStyleSheet()

  titulo_estilo = ParagraphStyle(
      "EmpresaTitulo",
      parent=estilos["Heading1"],
      fontSize=14,
      fontName="Helvetica-Bold",
      textColor=colors.HexColor("#000000"),
      spaceAfter=4,
  )
  sub_estilo = ParagraphStyle(
      "SubEmpresa",
      parent=estilos["Normal"],
      fontSize=9,
      fontName="Helvetica",
      textColor=colors.HexColor("#555555"),
      spaceAfter=15,
  )

  elementos.append(Paragraph("EMPRESA: CICSA", titulo_estilo))
  elementos.append(
      Paragraph(
          f"Reporte de Monitoreo IoT (Sensor DHT22) — Generado el"
          f" {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
          sub_estilo,
      )
  )

  # Construir los datos de la tabla con los registros reales del historial
  data = [["ID", "Temperatura (°C)", "Humedad (%)", "Fecha y Hora"]]

  if historial_registros:
    total_t = 0
    total_h = 0
    cantidad = len(historial_registros)

    for i, reg in enumerate(historial_registros):
      id_val = cantidad - i
      t_val = reg["Temperatura (°C)"]
      h_val = reg["Humedad (%)"]
      f_val = reg["Fecha y Hora"]

      total_t += t_val
      total_h += h_val

      data.append([str(id_val), f"{t_val} °C", f"{h_val} %", str(f_val)])

    # Fila de promedio final
    prom_t = round(total_t / cantidad, 1)
    prom_h = round(total_h / cantidad, 1)
    data.append(["Promedio", f"{prom_t} °C", f"{prom_h} %", "-"])
  else:
    data.append(["1", "0.0 °C", "0.0 %", datetime.now().strftime("%Y-%m-%d %H:%M:%S")])
    data.append(["Promedio", "0.0 °C", "0.0 %", "-"])

  tabla = Table(data, colWidths=[50, 130, 130, 230])
  tabla.setStyle(
      TableStyle([
          ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#111111")),
          ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
          ("ALIGN", (0, 0), (-1, -1), "CENTER"),
          ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
          ("FONTSIZE", (0, 0), (-1, 0), 9),
          ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
          ("TOPPADDING", (0, 0), (-1, 0), 6),
          ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#E2E8F0")),
          ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
          ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CCCCCC")),
          ("FONTNAME", (0, 1), (-1, -2), "Helvetica"),
          ("FONTSIZE", (0, 1), (-1, -1), 8.5),
          ("TOPPADDING", (0, 1), (-1, -1), 4),
          ("BOTTOMPADDING", (0, 1), (-1, -1), 4),
      ])
  )

  elementos.append(tabla)
  doc.build(elementos)
  buffer.seek(0)
  return buffer.getvalue()


# ==========================================
# CONEXIÓN SERIAL Y LECTURA
# ==========================================
puerto_encontrado = detectar_puerto_arduino()

if not puerto_encontrado:
  st.error(
      "❌ No se encontró ningún Arduino conectado. Por favor, verifica el cable"
      " USB."
  )
else:
  if "ser" not in st.session_state or not st.session_state.ser.is_open:
    try:
      st.session_state.ser = serial.Serial(
          puerto_encontrado, BAUDIOS, timeout=1
      )
      time.sleep(2)
    except Exception as ex:
      st.error(f"Error al abrir el puerto serie: {ex}")

  if "ser" in st.session_state and st.session_state.ser.is_open:
    try:
      linea = st.session_state.ser.readline().decode("utf-8").strip()
      if linea and "," in linea:
        partes = linea.split(",")
        t = float(partes[0])
        h = float(partes[1])
        st.session_state.temp_actual = t
        st.session_state.hum_actual = h

        nuevo_registro = {
            "Temperatura (°C)": t,
            "Humedad (%)": h,
            "Fecha y Hora": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        st.session_state.historial.insert(0, nuevo_registro)
        if len(st.session_state.historial) > 50:
          st.session_state.historial.pop()
    except Exception:
      pass

# ==========================================
# DISEÑO DE LA INTERFAZ EN STREAMLIT
# ==========================================
col1, col2 = st.columns(2)

with col1:
  st.metric(
      label="Temperatura Actual",
      value=f"{st.session_state.temp_actual} °C",
  )

with col2:
  st.metric(label="Humedad Actual", value=f"{st.session_state.hum_actual} %")

st.markdown("---")

st.subheader("📄 Últimos Registros Guardados")
if st.session_state.historial:
  df_historial = pd.DataFrame(st.session_state.historial)
  df_historial.insert(
      0, "ID", range(len(df_historial), 0, -1)
  )
  st.dataframe(df_historial, use_container_width=True, hide_index=True)
else:
  st.info("Esperando lecturas del puerto serie...")

st.markdown("---")
st.subheader("Generar Reporte Formal")

# Generar el PDF pasándole todo el historial acumulado
pdf_bytes = generar_pdf(st.session_state.historial)
st.download_button(
    label="📥 Descargar Reporte en PDF Profesional",
    data=pdf_bytes,
    file_name=f"reporte_cicsa_{datetime.now().strftime('%H%M%S')}.pdf",
    mime="application/pdf",
)

t = st.session_state.temp_actual
if t > LIMITE_TEMPERATURA:
  st.error(
      f"⚠️ ¡TEMPERATURA CRÍTICA! ({t} °C) - Enviando notificación WhatsApp..."
  )
  enviar_alerta_whatsapp(t)
else:
  st.success("✅ Sistema Operativo - Niveles Estables")

time.sleep(30)
st.rerun()