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
# FUNCIÓN PARA GENERAR PDF PROFESIONAL
# ==========================================


def generar_pdf(temp, hum):
  buffer = io.BytesIO()
  doc = SimpleDocTemplate(
      buffer,
      pagesize=letter,
      rightMargin=40,
      leftMargin=40,
      topMargin=40,
      bottomMargin=40,
  )
  elementos = []
  estilos = getSampleStyleSheet()

  titulo_estilo = ParagraphStyle(
      "TituloReporte",
      parent=estilos["Heading1"],
      fontSize=16,
      textColor=colors.HexColor("#1A365D"),
      spaceAfter=10,
  )
  sub_estilo = ParagraphStyle(
      "SubTitulo",
      parent=estilos["Normal"],
      fontSize=10,
      textColor=colors.HexColor("#4A5568"),
      spaceAfter=20,
  )

  elementos.append(
      Paragraph("REPORTE DE AUDITORÍA - CENTRO DE DATOS (SISTEMA CICSA)", titulo_estilo)
  )
  elementos.append(
      Paragraph(
          f"Fecha y Hora de Emisión: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
          sub_estilo,
      )
  )
  elementos.append(Spacer(1, 10))

  data = [
      ["Parámetro de Control", "Valor Registrado", "Estado del Sistema"],
      [
          "Temperatura (DHT22)",
          f"{temp} °C",
          (
              "⚠️ CRÍTICO"
              if temp > LIMITE_TEMPERATURA
              else "✅ ESTABLE"
          ),
      ],
      ["Humedad Relativa", f"{hum} %", "✅ ÓPTIMO"],
  ]

  tabla = Table(data, colWidths=[200, 150, 150])
  tabla.setStyle(
      TableStyle([
          ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2B6CB0")),
          ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
          ("ALIGN", (0, 0), (-1, -1), "CENTER"),
          ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
          ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
          ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#F7FAFC")),
          ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E0")),
          ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
          ("FONTSIZE", (0, 1), (-1, -1), 10),
          ("TOPPADDING", (0, 1), (-1, -1), 6),
          ("BOTTOMPADDING", (0, 1), (-1, -1), 6),
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
  # Abrir puerto de manera persistente
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

        # Registrar en el historial para la tabla
        nuevo_registro = {
            "Temperatura (°C)": t,
            "Humedad (%)": h,
            "Fecha y Hora": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        st.session_state.historial.insert(0, nuevo_registro)
        if len(st.session_state.historial) > 20:
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

# TABLA DE ÚLTIMOS REGISTROS GUARDADOS
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

t = st.session_state.temp_actual
h = st.session_state.hum_actual

pdf_bytes = generar_pdf(t, h)
st.download_button(
    label="📥 Descargar Reporte en PDF Profesional",
    data=pdf_bytes,
    file_name=f"reporte_centro_datos_{datetime.now().strftime('%H%M%S')}.pdf",
    mime="application/pdf",
)

# Evaluar alertas
if t > LIMITE_TEMPERATURA:
  st.error(
      f"⚠️ ¡TEMPERATURA CRÍTICA! ({t} °C) - Enviando notificación WhatsApp..."
  )
  enviar_alerta_whatsapp(t)
else:
  st.success("✅ Sistema Operativo - Niveles Estables")

# Esperar 30 segundos antes de refrescar automáticamente
time.sleep(30)
st.rerun()