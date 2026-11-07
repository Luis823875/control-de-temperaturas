from datetime import datetime
import io
import time
import pywhatkit as kit
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
import serial
import serial.tools.list_ports
import streamlit as st

# ==========================================
# CONFIGURACIÓN GENERAL Y DETECCIÓN AUTOMÁTICA
# ==========================================
st.set_page_config(
    page_title="Centro de Datos - Monitoreo Ambiental", layout="wide"
)

st.title("🖥️ Centro de Datos con Alertas y Auditoría Crítica")
st.markdown("Monitoreo en tiempo real de Temperatura y Humedad (DHT22)")

BAUDIOS = 115200
NUMERO_CELULAR = "+51924203754"  # Tu número configurado
LIMITE_TEMPERATURA = 30.0  # Límite crítico para disparar la alerta

TIEMPO_ESPERA_ALERTA = 300
if "ultima_alerta" not in st.session_state:
  st.session_state.ultima_alerta = 0


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
# FUNCIÓN PARA GENERAR PDF CON REPORTLAB
# ==========================================


def generar_pdf(temp, hum):
  buffer = io.BytesIO()
  p = canvas.Canvas(buffer, pagesize=letter)

  # Cabecera del Reporte
  p.drawString(
      50, 750, "REPORTE DE AUDITORÍA - CENTRO DE DATOS (SISTEMA CICSA)"
  )
  p.drawString(50, 735, "=" * 60)
  p.drawString(
      50, 710, f"Fecha y Hora: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
  )
  p.drawString(50, 685, f"Temperatura Registrada: {temp} °C")
  p.drawString(50, 660, f"Humedad Relativa: {hum} %")

  if temp > LIMITE_TEMPERATURA:
    p.drawString(
        50,
        635,
        "Estado del Sistema: ⚠️ ALERTA CRÍTICA (Superó los 30.0 °C)",
    )
  else:
    p.drawString(50, 635, "Estado del Sistema: ✅ Niveles Estables")

  p.showPage()
  p.save()
  buffer.seek(0)
  return buffer.getvalue()


# ==========================================
# DISEÑO DE LA INTERFAZ EN STREAMLIT
# ==========================================
col1, col2 = st.columns(2)

with col1:
  st.subheader("Estado Actual del Sensor")
  metric_temp = st.empty()
  metric_hum = st.empty()

with col2:
  st.subheader("Registro de Alertas y Estado del Sistema")
  alerta_box = st.empty()

  # Espacio reservado para el botón de descarga en PDF
  st.markdown("### Exportar Datos")
  pdf_placeholder = st.empty()

# ==========================================
# MANEJO DE CONEXIÓN SERIAL PERSISTENTE
# ==========================================
puerto_encontrado = detectar_puerto_arduino()

if not puerto_encontrado:
  st.error(
      "❌ No se encontró ningún Arduino conectado. Por favor, verifica el cable"
      " USB."
  )
else:
  st.info(f"🔍 Arduino detectado automáticamente en el puerto: {puerto_encontrado}")

  # Abrir el puerto UNA SOLA VEZ y guardarlo en session_state para que el Arduino no se reinicie
  if "ser" not in st.session_state or not st.session_state.ser.is_open:
    try:
      st.session_state.ser = serial.Serial(
          puerto_encontrado, BAUDIOS, timeout=2
      )
      time.sleep(2)  # Pausa inicial para estabilizar
    except Exception as ex:
      st.error(f"Error al abrir el puerto serie: {ex}")

  # Leer datos si la conexión está activa
  if "ser" in st.session_state and st.session_state.ser.is_open:
    try:
      linea = st.session_state.ser.readline().decode("utf-8").strip()

      if linea and "," in linea:
        partes = linea.split(",")
        t = float(partes[0])
        h = float(partes[1])

        # Actualizar métricas en la interfaz
        metric_temp.metric(label="Temperatura (DHT22)", value=f"{t} °C")
        metric_hum.metric(label="Humedad Relativa", value=f"{h} %")

        # Generar el PDF en memoria con los datos actuales
        pdf_bytes = generar_pdf(t, h)
        pdf_placeholder.download_button(
            label="📄 Descargar Reporte en PDF",
            data=pdf_bytes,
            file_name=f"reporte_centro_datos_{datetime.now().strftime('%H%M%S')}.pdf",
            mime="application/pdf",
        )

        # Evaluar condición de alerta crítica
        if t > LIMITE_TEMPERATURA:
          alerta_box.error(
              f"⚠️ ¡TEMPERATURA CRÍTICA! ({t} °C) - Enviando notificación"
              " WhatsApp..."
          )
          enviar_alerta_whatsapp(t)
        else:
          alerta_box.success("✅ Sistema Operativo - Niveles Estables")

    except ValueError:
      pass

    # Refrescar la interfaz suavemente cada segundo sin cerrar el puerto
    time.sleep(1)
    st.rerun()