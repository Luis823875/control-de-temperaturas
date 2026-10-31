import serial
import mysql.connector

# Configuración del puerto serial (COM3)
puerto_serial = serial.Serial('COM3', 115200, timeout=1)

# Conexión a tu base de datos MySQL (ajusta el usuario y contraseña si usas otros)
conexion = mysql.connector.connect(
    host="localhost",
    user="root",          # Cambia esto por tu usuario de MySQL si es diferente
    password="Luis2024$", # Cambia esto por tu contraseña de MySQL
    database="db_monitoreo"
)
cursor = conexion.cursor()

print("Escuchando puerto serie y guardando en MySQL...")

while True:
    linea = puerto_serial.readline().decode('utf-8').strip()
    if linea:
        # Verificamos que la línea traiga el texto del ESP32
        if "Dato recibido:" in linea:
            try:
                # Extraemos la parte numérica (ej: "30.40,67.10")
                datos_limpios = linea.replace("Dato recibido: ", "").strip()
                temp_str, hum_str = datos_limpios.split(",")
                
                temperatura = float(temp_str)
                humedad = float(hum_str)
                
                # Insertar en la tabla 'lecturas'
                sql = "INSERT INTO lecturas (temperatura, humedad) VALUES (%s, %s)"
                valores = (temperatura, humedad)
                cursor.execute(sql, valores)
                conexion.commit()
                
                print(f"Guardado en MySQL -> Temp: {temperatura}°C | Humedad: {humedad}%")
            except Exception as e:
                print(f"Error al procesar la línea: {linea} -> {e}")