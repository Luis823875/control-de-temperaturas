from datetime import datetime
import time
import pywhatkit as kit
import serial
import serial.tools.list_ports
import streamlit as st


# CONFIGURACIÓN GENERAL Y DETECCIÓN AUTOMÁTICA

st.set_page_config(
    page_title="Centro de Datos - Monitoreo Ambiental", layout="wide"
)

st.title("🖥️ Centro de Datos con Alertas y Auditoría Crítica")
st.markdown("Monitoreo en tiempo real de Temperatura y Humedad (DHT22)")

BAUDIOS = 115200
NUMERO_CELULAR = (
    "+51924203754"  # Reemplaza con tu número incluyendo código de país
)
LIMITE_TEMPERATURA = 30.0  # Límite crítico para disparar la alerta

TIEMPO_ESPERA_ALERTA = 300
if "ultima_alerta" not in st.session_state:
  st.session_state.ultima_alerta = 0


def detectar_puerto_arduino():
  """Busca automáticamente el puerto COM donde está conectado el Arduino."""
  puertos = serial.tools.list_ports.comports()
  for puerto in puertos:
    # Comprueba si el dispositivo conectado es un Arduino o un conversor serial común (CH340/CP210x)
    descripcion = puerto.description.lower()
    if (
        "arduino" in descripcion
        or "ch340" in descripcion
        or "usb-serial" in descripcion
        or "usb serial" in descripcion
    ):
      return puerto.device
  # Si no encuentra por descripción, devuelve el primer puerto disponible que encuentre
  if puertos:
    return puertos[0].device
  return None



# FUNCIÓN DE ALERTA POR WHATSAPP



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



# DISEÑO DE LA INTERFAZ EN STREAMLIT

col1, col2 = st.columns(2)

with col1:
  st.subheader("Estado Actual del Sensor")
  metric_temp = st.empty()
  metric_hum = st.empty()

with col2:
  st.subheader("Registro de Alertas y Estado del Sistema")
  alerta_box = st.empty()


# BUCLE DE LECTURA AUTOMÁTICA

puerto_encontrado = detectar_puerto_arduino()

if not puerto_encontrado:
  st.error(
      "❌ No se encontró ningún Arduino conectado. Por favor, verifica el cable"
      " USB."
  )
else:
  st.info(f"🔍 Arduino detectado automáticamente en el puerto: {puerto_encontrado}")
  try:
    ser = serial.Serial(puerto_encontrado, BAUDIOS, timeout=1)
    time.sleep(2)  # Pausa para estabilizar la conexión

    while True:
      if ser.in_waiting > 0:
        linea = ser.readline().decode("utf-8").strip()

        if "," in linea:
          try:
            partes = linea.split(",")
            t = float(partes[0])
            h = float(partes[1])

            # Actualizar métricas en la interfaz
            metric_temp.metric(label="Temperatura (DHT22)", value=f"{t} °C")
            metric_hum.metric(label="Humedad Relativa", value=f"{h} %")

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

      time.sleep(0.5)

  except Exception as ex:
    st.warning(f"Error en la comunicación serial: {ex}")