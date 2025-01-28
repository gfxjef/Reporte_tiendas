import os
import smtplib
import mysql.connector
import seaborn as sns
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
from flask import Flask, jsonify, request
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from email.mime.application import MIMEApplication
import pandas as pd
import logging

# Configuración de Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuración de Flask
app = Flask(__name__)

sns.set(style="whitegrid")

# Configuración de la Base de Datos
DB_CONFIG = {
    'user': os.environ.get('MYSQL_USER'),
    'password': os.environ.get('MYSQL_PASSWORD'),
    'host': os.environ.get('MYSQL_HOST'),
    'database': os.environ.get('MYSQL_DATABASE'),
    'port': int(os.environ.get('MYSQL_PORT', 3306))
}

# Configuración de Correo Electrónico
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SENDER_EMAIL = os.environ.get('EMAIL_USER')
SENDER_PASSWORD = os.environ.get('EMAIL_PASSWORD')

# **Direcciones de Correo Destinatarias**
RECEIVER_EMAILS = ["gfxjef@gmail.com", "max.campor@gmail.com", "milazcyn@gmail.com", "camachoteofilo1958@gmail.com"]

def generar_graficos(df, fecha_reporte):
    try:
        # Configurar tema de colores
        colores = ['#2A5C8F', '#30A5BF', '#F2B705', '#F25C05']
        
        # Gráfico 1: Evolución horaria de ventas
        plt.figure(figsize=(10, 6))
        df['Hora'] = df['Timestamp'].dt.hour
        ventas_horarias = df.groupby('Hora')['Precio'].sum()
        sns.lineplot(x=ventas_horarias.index, y=ventas_horarias.values, 
                    marker='o', color=colores[0], linewidth=2.5)
        plt.title(f'Ventas por Hora - {fecha_reporte}', fontsize=14)
        plt.xlabel('Hora del día')
        plt.ylabel('Total Ventas (S/.)')
        plt.xticks(range(0, 24))
        plt.tight_layout()
        plt.savefig('ventas_horarias.png')
        plt.close()
        logger.info("Gráfico 'ventas_horarias.png' generado correctamente.")
        
        # Gráfico 2: Métodos de pago
        plt.figure(figsize=(8, 8))
        metodos_pago = df['Modo de Venta'].value_counts()
        plt.pie(metodos_pago, labels=metodos_pago.index, autopct='%1.1f%%',
               colors=colores, startangle=90, textprops={'color':'w'})
        plt.title('Distribución de Métodos de Pago', fontsize=14)
        plt.savefig('metodos_pago.png')
        plt.close()
        logger.info("Gráfico 'metodos_pago.png' generado correctamente.")
        
        # Gráfico 3: Top 5 productos
        plt.figure(figsize=(10, 6))
        top_productos = df.groupby('SKU')['Cantidad'].sum().nlargest(5)
        sns.barplot(x=top_productos.values, y=top_productos.index, 
                   palette=colores, orient='h')
        plt.title('Top 5 Productos Más Vendidos', fontsize=14)
        plt.xlabel('Unidades Vendidas')
        plt.tight_layout()
        plt.savefig('top_productos.png')
        plt.close()
        logger.info("Gráfico 'top_productos.png' generado correctamente.")
    except Exception as e:
        logger.error(f"Error al generar gráficos: {str(e)}")
        raise

def crear_cuerpo_email(analisis, fecha_reporte):
    return f"""
    <html>
      <head>
        <style>
          body {{ font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; color: #333; }}
          .container {{ max-width: 800px; margin: 0 auto; padding: 20px; }}
          .header {{ background-color: #2A5C8F; padding: 20px; color: white; text-align: center; }}
          .metric-card {{ 
              background: white; 
              border-radius: 10px; 
              padding: 20px; 
              margin: 10px; 
              box-shadow: 0 4px 6px rgba(0,0,0,0.1);
              display: inline-block;
              width: 45%;
          }}
          .metric-value {{ 
              font-size: 24px; 
              color: #2A5C8F; 
              font-weight: bold;
              margin: 10px 0;
          }}
          .chart {{ 
              margin: 20px 0; 
              border-radius: 10px;
              overflow: hidden;
          }}
          .footer {{ 
              background-color: #f5f5f5; 
              padding: 15px; 
              text-align: center; 
              font-size: 12px;
              margin-top: 20px;
          }}
        </style>
      </head>
      <body>
        <div class="container">
          <div class="header">
            <h1>Reporte Diario de Ventas</h1>
            <h3>{fecha_reporte}</h3>
          </div>
          
          <div style="text-align: center; margin: 20px 0;">
            <div class="metric-card">
              <div>Total Ventas</div>
              <div class="metric-value">S/. {analisis['total_ventas']:,.2f}</div>
            </div>
            <div class="metric-card">
              <div>Unidades Vendidas</div>
              <div class="metric-value">{analisis['total_unidades']}</div>
            </div>
          </div>
          
          <h2>Análisis Visual</h2>
          <div class="chart">
            <img src="cid:ventas_horarias.png" style="width: 100%;">
          </div>
          
          <div style="display: flex; gap: 20px; margin: 20px 0;">
            <div style="flex: 1;">
              <img src="cid:metodos_pago.png" style="width: 100%;">
            </div>
            <div style="flex: 1;">
              <img src="cid:top_productos.png" style="width: 100%;">
            </div>
          </div>
          
          <h2>Hallazgos Clave</h2>
          <ul style="background: #f9f9f9; padding: 20px; border-radius: 10px;">
            <li>El método de pago más utilizado fue: {analisis['modo_venta_comun']}</li>
            <li>La sede con mayor performance: {analisis['sede_mas_ventas']}</li>
            <li>Producto estrella: {analisis['top_producto']}</li>
          </ul>
          
          <div class="footer">
            <p>Este reporte fue generado automáticamente - {fecha_reporte}</p>
            <p>© 2024 Tu Empresa - Todos los derechos reservados</p>
          </div>
        </div>
      </body>
    </html>
    """

def obtener_datos_ventas():
    try:
        # Conexión a la base de datos
        conn = mysql.connector.connect(**DB_CONFIG)
        query = f"""
            SELECT * FROM ventas_totales_2024 
            WHERE DATE(`Timestamp`) = CURDATE() - INTERVAL 1 DAY
        """
        df = pd.read_sql(query, conn, parse_dates=['Timestamp'])
        conn.close()
        logger.info("Datos de ventas obtenidos correctamente.")
        return df
    except Exception as e:
        logger.error(f"Error al obtener datos de ventas: {str(e)}")
        raise

def generar_analisis(df):
    try:
        # Cálculos principales
        analisis = {
            'total_ventas': df['Precio'].sum(),
            'total_unidades': df['Cantidad'].sum(),
            'venta_promedio': df['Precio'].mean(),
            'top_producto': df['SKU'].mode()[0],
            'modo_venta_comun': df['Modo de Venta'].mode()[0],
            'sede_mas_ventas': df['Sede'].mode()[0]
        }
        logger.info("Análisis de ventas generado correctamente.")
        return analisis
    except Exception as e:
        logger.error(f"Error al generar análisis: {str(e)}")
        raise

def enviar_email(analisis, df, fecha_reporte):
    try:
        msg = MIMEMultipart()
        msg['Subject'] = f"📊 Reporte Ventas Diarias - {fecha_reporte}"
        msg['From'] = SENDER_EMAIL
        msg['To'] = ", ".join(RECEIVER_EMAILS)
        
        # Generar gráficos
        generar_graficos(df, fecha_reporte)
        
        # Cuerpo HTML
        body = crear_cuerpo_email(analisis, fecha_reporte)
        msg.attach(MIMEText(body, 'html'))
        
        # Adjuntar imágenes
        for imagen in ['ventas_horarias.png', 'metodos_pago.png', 'top_productos.png']:
            with open(imagen, 'rb') as img:
                img_data = img.read()
                image = MIMEImage(img_data, name=os.path.basename(imagen))
                image.add_header('Content-ID', f'<{imagen}>')
                msg.attach(image)
        
        # Adjuntar CSV
        csv_file = df.to_csv(index=False)
        adjunto = MIMEApplication(csv_file)
        adjunto.add_header('Content-Disposition', 'attachment', 
                          filename=f"detalle_ventas_{fecha_reporte}.csv")
        msg.attach(adjunto)
        
        # Enviar email
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.sendmail(SENDER_EMAIL, RECEIVER_EMAILS, msg.as_string())
            logger.info("Email enviado exitosamente.")
        
        # Limpieza de archivos temporales
        for imagen in ['ventas_horarias.png', 'metodos_pago.png', 'top_productos.png']:
            if os.path.exists(imagen):
                os.remove(imagen)
                logger.info(f"Archivo {imagen} eliminado.")
    except Exception as e:
        logger.error(f"Error al enviar email: {str(e)}")
        raise

@app.route('/generate_report', methods=['POST'])
def generate_report():
    """
    Endpoint para generar y enviar el reporte de ventas.
    """
    try:
        # Autenticación básica (opcional)
        auth_token = request.headers.get('Authorization')
        if not auth_token or auth_token != os.environ.get('API_TOKEN'):
            logger.warning("Solicitud no autorizada.")
            return jsonify({"error": "Unauthorized"}), 401

        df_ventas = obtener_datos_ventas()
        if not df_ventas.empty:
            analisis = generar_analisis(df_ventas)
            fecha_reporte = (datetime.now() - timedelta(days=1)).strftime('%d/%m/%Y')
            enviar_email(analisis, df_ventas, fecha_reporte)
            return jsonify({"message": "Reporte generado y enviado exitosamente."}), 200
        else:
            logger.info("No hay ventas para el período analizado.")
            return jsonify({"message": "No hay ventas para el período analizado."}), 200
    except Exception as e:
        logger.error(f"Error en la generación del reporte: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/', methods=['GET'])
def home():
    return "Servicio de Reporte de Ventas Activo."

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)
