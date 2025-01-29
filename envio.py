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
RECEIVER_EMAILS = ["gfxjef@gmail.com", "gfxjef@gmail.com", "gfxjef@gmail.com", "gfxjef@gmail.com"]

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
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Reporte Diario de Ventas</title>
    </head>
    <body style="margin: 0; padding: 0; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #ffffff;">
        <table cellpadding="0" cellspacing="0" border="0" width="100%" style="max-width: 800px; margin: 0 auto;">
            <!-- Header -->
            <tr>
                <td style="background: linear-gradient(135deg, #2A5C8F, #1a365f); padding: 30px 20px; text-align: center; border-radius: 12px 12px 0 0;">
                    <img src="cid:logo_empresa.png" alt="Logo Empresa" style="width: 50px; height: 50px; margin-bottom: 10px;">
                    <h1 style="margin: 0; color: #ffffff; font-size: 28px; font-weight: 600;">📈 Reporte Diario de Ventas</h1>
                    <p style="margin: 5px 0 0; color: #ffffff; font-size: 16px;">{fecha_reporte}</p>
                </td>
            </tr>
            
            <!-- Métricas -->
            <tr>
                <td style="padding: 20px;">
                    <table width="100%" cellpadding="0" cellspacing="0" border="0">
                        <tr>
                            <td width="50%" style="padding: 10px;">
                                <table width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color: #f8f9fa; border-radius: 10px; padding: 20px; box-shadow: 0 3px 6px rgba(0,0,0,0.1);">
                                    <tr>
                                        <td style="text-align: center;">
                                            <img src="cid:icono_ventas.png" alt="Total Ventas" style="width: 30px; height: 30px; margin-bottom: 10px;">
                                            <h2 style="margin: 0; color: #2A5C8F; font-size: 24px;">S/. {analisis['total_ventas']:,.2f}</h2>
                                            <p style="margin: 5px 0 0; color: #555555; font-size: 16px;">Total Ventas</p>
                                        </td>
                                    </tr>
                                </table>
                            </td>
                            <td width="50%" style="padding: 10px;">
                                <table width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color: #f8f9fa; border-radius: 10px; padding: 20px; box-shadow: 0 3px 6px rgba(0,0,0,0.1);">
                                    <tr>
                                        <td style="text-align: center;">
                                            <img src="cid:icono_unidades.png" alt="Unidades Vendidas" style="width: 30px; height: 30px; margin-bottom: 10px;">
                                            <h2 style="margin: 0; color: #2A5C8F; font-size: 24px;">{analisis['total_unidades']}</h2>
                                            <p style="margin: 5px 0 0; color: #555555; font-size: 16px;">Unidades Vendidas</p>
                                        </td>
                                    </tr>
                                </table>
                            </td>
                        </tr>
                    </table>
                </td>
            </tr>
            
            <!-- Sección de Gráficos -->
            <tr>
                <td style="padding: 20px;">
                    <h2 style="color: #2A5C8F; font-size: 22px; margin-bottom: 15px;">Análisis Visual</h2>
                    <table width="100%" cellpadding="0" cellspacing="0" border="0">
                        <tr>
                            <td style="padding-bottom: 20px;">
                                <img src="cid:ventas_horarias.png" alt="Ventas Horarias" style="width: 100%; border-radius: 8px; box-shadow: 0 3px 6px rgba(0,0,0,0.1);">
                            </td>
                        </tr>
                        <tr>
                            <td style="padding-bottom: 20px;">
                                <img src="cid:metodos_pago.png" alt="Métodos de Pago" style="width: 100%; border-radius: 8px; box-shadow: 0 3px 6px rgba(0,0,0,0.1);">
                            </td>
                        </tr>
                        <tr>
                            <td>
                                <img src="cid:top_productos.png" alt="Top Productos" style="width: 100%; border-radius: 8px; box-shadow: 0 3px 6px rgba(0,0,0,0.1);">
                            </td>
                        </tr>
                    </table>
                </td>
            </tr>
            
            <!-- Hallazgos Clave -->
            <tr>
                <td style="padding: 20px;">
                    <h2 style="color: #2A5C8F; font-size: 22px; margin-bottom: 15px;">🔍 Hallazgos Clave</h2>
                    <table width="100%" cellpadding="0" cellspacing="0" border="0">
                        <tr>
                            <td style="background-color: #f8f9fa; padding: 15px; border-radius: 8px; margin-bottom: 10px;">
                                <p style="margin: 0; color: #555555; font-size: 16px;"><strong>Método de pago predominante:</strong> {analisis['modo_venta_comun']}</p>
                            </td>
                        </tr>
                        <tr>
                            <td style="background-color: #f8f9fa; padding: 15px; border-radius: 8px; margin-bottom: 10px;">
                                <p style="margin: 0; color: #555555; font-size: 16px;"><strong>Sede destacada:</strong> {analisis['sede_mas_ventas']}</p>
                            </td>
                        </tr>
                        <tr>
                            <td style="background-color: #f8f9fa; padding: 15px; border-radius: 8px;">
                                <p style="margin: 0; color: #555555; font-size: 16px;"><strong>Producto líder:</strong> {analisis['top_producto']}</p>
                            </td>
                        </tr>
                    </table>
                </td>
            </tr>
            
            <!-- Footer -->
            <tr>
                <td style="background: linear-gradient(135deg, #2A5C8F, #1a365f); padding: 20px; text-align: center; border-radius: 0 0 12px 12px; color: #ffffff;">
                    <p style="margin: 0; font-size: 14px;">🔒 Reporte generado automáticamente - {fecha_reporte}</p>
                    <p style="margin: 5px 0 0; font-size: 12px;">© 2024 Tu Empresa | Todos los derechos reservados</p>
                </td>
            </tr>
        </table>
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
