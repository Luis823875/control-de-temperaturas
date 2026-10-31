import io
import mysql.connector
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
import streamlit as st


# Configuración de la conexión a MySQL (Compatible con Aiven Cloud y Local)
def conectar_db():
  if "mysql" in st.secrets:
    return mysql.connector.connect(
        host=st.secrets["mysql"]["host"],
        user=st.secrets["mysql"]["user"],
        password=st.secrets["mysql"]["password"],
        database=st.secrets["mysql"]["database"],
        port=int(st.secrets["mysql"]["port"]),
        ssl_disabled=False,
    )
  else:
    # Conexión local en tu PC
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="Luis2024$",
        database="db_monitoreo",
    )


# Configuración de la página web
st.set_page_config(
    page_title="Monitoreo Data Center", page_icon="📊", layout="centered"
)

# Manejo de sesión simple
if "autenticado" not in st.session_state:
  st.session_state["autenticado"] = False

# Pantalla de Login
if not st.session_state["autenticado"]:
  st.title("🔐 Iniciar Sesión - Monitoreo")
  usuario = st.text_input("Usuario")
  password = st.text_input("Contraseña", type="password")

  if st.button("Ingresar"):
    if usuario == "admin" and password == "1234":
      st.session_state["autenticado"] = True
      st.rerun()
    else:
      st.error("Usuario o contraseña incorrectos")

else:
  st.title("🌡️ Panel de Monitoreo Ambiental - Data Center")
  st.write("Datos en tiempo real obtenidos desde el ESP32 y guardados en MySQL.")

  if st.button("Cerrar Sesión"):
    st.session_state["autenticado"] = False
    st.rerun()

  st.divider()

  try:
    conexion = conectar_db()
    cursor = conexion.cursor(dictionary=True)
    cursor.execute(
        "SELECT * FROM lecturas ORDER BY fecha_registro DESC LIMIT 15"
    )
    lecturas = cursor.fetchall()
    conexion.close()

    if lecturas:
      ultimo = lecturas[0]
      col1, col2 = st.columns(2)
      col1.metric("Temperatura Actual", f"{ultimo['temperatura']} °C")
      col2.metric("Humedad Actual", f"{ultimo['humedad']} %")

      st.subheader("📋 Últimos Registros Guardados")
      st.dataframe(lecturas, use_container_width=True)

      # --- Generador de PDF Profesional ---
      def generar_pdf_profesional():
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

        styles = getSampleStyleSheet()

        # Estilos personalizados
        titulo_estilo = ParagraphStyle(
            "TituloReporte",
            parent=styles["Heading1"],
            fontSize=18,
            textColor=colors.HexColor("#1f2937"),
            spaceAfter=6,
        )
        sub_estilo = ParagraphStyle(
            "SubReporte",
            parent=styles["Normal"],
            fontSize=10,
            textColor=colors.HexColor("#6b7280"),
            spaceAfter=20,
        )

        elementos.append(
            Paragraph("Reporte Técnico de Monitoreo Ambiental", titulo_estilo)
        )
        elementos.append(
            Paragraph(
                "Sistema IoT - Data Center | Universidad Privada del Norte",
                sub_estilo,
            )
        )

        # Preparar datos para la tabla formal de ReportLab
        data = [["ID", "Temperatura (°C)", "Humedad (%)", "Fecha y Hora"]]
        for row in lecturas:
          data.append([
              str(row["id"]),
              f"{row['temperatura']} °C",
              f"{row['humedad']} %",
              str(row["fecha_registro"]),
          ])

        # Crear tabla con diseño profesional
        tabla = Table(data, colWidths=[40, 120, 100, 260])
        tabla.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#007bff")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 10),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
                ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#f9fafb")),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d1d5db")),
                ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 1), (-1, -1), 9),
                ("TOPPADDING", (0, 1), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 1), (-1, -1), 6),
            ])
        )

        elementos.append(tabla)
        doc.build(elementos)
        buffer.seek(0)
        return buffer

      pdf_data = generar_pdf_profesional()

      st.download_button(
          label="📥 Descargar Reporte en PDF Profesional",
          data=pdf_data,
          file_name="reporte_tecnico_sensores.pdf",
          mime="application/pdf",
      )
    else:
      st.info("No hay lecturas registradas todavía en la base de datos.")

  except Exception as e:
    st.error(f"Error al conectar con la base de datos: {e}")