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

# Estilo global para gráficos con Seaborn y Matplotlib
sns.set(style="whitegrid", context="talk", palette="deep")
plt.rcParams.update({
    'axes.titlesize': 18,
    'axes.labelsize': 16,
    'xtick.labelsize': 14,
    'ytick.labelsize': 14,
    'font.family': 'sans-serif',
    'font.sans-serif': ['Segoe UI', 'Tahoma', 'DejaVu Sans', 'Verdana']
})

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

# Direcciones de Correo Destinatarias
RECEIVER_EMAILS = [
    "gfxjef@gmail.com", "camachoteofilo1958@gmail.com",
    "max.campor@gmail.com", "milazcyn@gmail.com"
]

######################################
# FUNCIONES PARA REPORTES DIARIOS
######################################

def generar_graficos(df, fecha_reporte):
    """
    Genera gráficos diarios: ventas horarias, distribución de métodos de pago,
    top 5 productos y desglose por sedes.
    """
    try:
        colores = ['#2A5C8F', '#30A5BF', '#F2B705', '#F25C05']
        
        # 1. Evolución horaria de ventas
        plt.figure(figsize=(10, 6))
        df['Hora'] = df['Timestamp'].dt.hour
        ventas_horarias = df.groupby('Hora')['Precio'].sum()
        ax = sns.lineplot(x=ventas_horarias.index, y=ventas_horarias.values,
                          marker='o', color=colores[0], linewidth=2.5)
        ax.set_title(f'Ventas por Hora - {fecha_reporte}', fontsize=18, weight='bold')
        ax.set_xlabel('Hora del día')
        ax.set_ylabel('Total Ventas (S/.)')
        ax.set_xticks(range(0, 24))
        plt.tight_layout()
        plt.savefig('ventas_horarias.png')
        plt.close()
        logger.info("Gráfico 'ventas_horarias.png' generado correctamente.")

        # 2. Distribución de métodos de pago
        plt.figure(figsize=(8, 8))
        metodos_pago = df['Modo de Venta'].value_counts()
        patches, texts, autotexts = plt.pie(metodos_pago, labels=metodos_pago.index,
                                            autopct='%1.1f%%', colors=colores, startangle=90,
                                            textprops={'fontsize': 14})
        plt.setp(texts, color='gray')
        plt.setp(autotexts, color='white', weight='bold', fontsize=14)
        plt.title('Distribución de Métodos de Pago', fontsize=18, weight='bold')
        plt.tight_layout()
        plt.savefig('metodos_pago.png')
        plt.close()
        logger.info("Gráfico 'metodos_pago.png' generado correctamente.")

        # 3. Top 5 productos más vendidos
        plt.figure(figsize=(10, 6))
        top_productos = df.groupby('SKU')['Cantidad'].sum().nlargest(5)
        ax = sns.barplot(x=top_productos.values, y=top_productos.index, palette=colores)
        ax.set_title('Top 5 Productos Más Vendidos', fontsize=18, weight='bold')
        ax.set_xlabel('Unidades Vendidas')
        plt.tight_layout()
        plt.savefig('top_productos.png')
        plt.close()
        logger.info("Gráfico 'top_productos.png' generado correctamente.")

        # 4. Desglose de ventas por sedes
        plt.figure(figsize=(10, 6))
        ventas_sedes = df.groupby('Sede')['Precio'].sum().sort_values(ascending=False)
        ax = sns.barplot(x=ventas_sedes.values, y=ventas_sedes.index, palette=colores)
        ax.set_title('Ventas por Sede', fontsize=18, weight='bold')
        ax.set_xlabel('Total Ventas (S/.)')
        plt.tight_layout()
        plt.savefig('ventas_sedes.png')
        plt.close()
        logger.info("Gráfico 'ventas_sedes.png' generado correctamente.")

    except Exception as e:
        logger.error(f"Error al generar gráficos diarios: {str(e)}")
        raise

def generar_analisis(df):
    """
    Genera un análisis de ventas diario con métricas globales y por sedes.
    """
    try:
        analisis = {
            'total_ventas': df['Precio'].sum(),
            'total_unidades': df['Cantidad'].sum(),
            'venta_promedio': df['Precio'].mean(),
            'top_producto': df['SKU'].mode()[0],
            'modo_venta_comun': df['Modo de Venta'].mode()[0],
            'sede_mas_ventas': df.groupby('Sede')['Precio'].sum().idxmax(),
            'detalle_sedes': df.groupby('Sede').agg({
                'Precio': 'sum',
                'Cantidad': 'sum'
            }).reset_index().to_dict(orient='records')
        }
        logger.info("Análisis de ventas diario generado correctamente.")
        return analisis
    except Exception as e:
        logger.error(f"Error al generar análisis diario: {str(e)}")
        raise

def crear_cuerpo_email(analisis, fecha_reporte):
    """
    Crea el cuerpo HTML del correo diario, incluyendo métricas principales y
    un desglose por sedes en forma de tabla.
    """
    # Generar filas de tabla para cada sede
    filas_sedes = ""
    for sede in analisis['detalle_sedes']:
        filas_sedes += f"""
        <tr>
            <td style="padding:8px; border:1px solid #ddd;">{sede['Sede']}</td>
            <td style="padding:8px; border:1px solid #ddd;">S/. {sede['Precio']:,.2f}</td>
            <td style="padding:8px; border:1px solid #ddd;">{sede['Cantidad']}</td>
        </tr>
        """

    cuerpo = f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <title>Reporte Diario de Ventas</title>
    </head>
    <body style="margin: 0; padding: 0; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f4f6f9;">
        <table cellpadding="0" cellspacing="0" border="0" width="100%" style="max-width:800px; margin:0 auto; background-color:#ffffff; border-radius:8px; overflow:hidden;">
            <!-- Header -->
            <tr>
                <td style="background: linear-gradient(135deg, #2A5C8F, #1a365f); padding:30px; text-align:center;">
                    <img src="cid:logo_empresa.png" alt="Logo Empresa" style="width:60px; height:60px; margin-bottom:10px;">
                    <h1 style="color:#ffffff; margin:0; font-size:28px;">📈 Reporte Diario de Ventas</h1>
                    <p style="color:#ffffff; margin:5px 0 0; font-size:16px;">{fecha_reporte}</p>
                </td>
            </tr>
            <!-- Métricas Globales -->
            <tr>
                <td style="padding:20px;">
                    <table width="100%" cellpadding="0" cellspacing="0">
                        <tr>
                            <td style="padding:10px; text-align:center;">
                                <div style="background:#f8f9fa; border-radius:8px; padding:20px; box-shadow:0 2px 4px rgba(0,0,0,0.1);">
                                    <img src="cid:icono_ventas.png" alt="Total Ventas" style="width:40px; height:40px;">
                                    <h2 style="color:#2A5C8F; margin:10px 0 0;">S/. {analisis['total_ventas']:,.2f}</h2>
                                    <p style="color:#555;">Total Ventas</p>
                                </div>
                            </td>
                            <td style="padding:10px; text-align:center;">
                                <div style="background:#f8f9fa; border-radius:8px; padding:20px; box-shadow:0 2px 4px rgba(0,0,0,0.1);">
                                    <img src="cid:icono_unidades.png" alt="Unidades Vendidas" style="width:40px; height:40px;">
                                    <h2 style="color:#2A5C8F; margin:10px 0 0;">{analisis['total_unidades']}</h2>
                                    <p style="color:#555;">Unidades Vendidas</p>
                                </div>
                            </td>
                        </tr>
                    </table>
                </td>
            </tr>
            <!-- Desglose por Sedes -->
            <tr>
                <td style="padding:20px;">
                    <h2 style="color:#2A5C8F; border-bottom:2px solid #2A5C8F; padding-bottom:10px;">Resumen por Sede</h2>
                    <table width="100%" style="border-collapse:collapse; margin-top:10px;">
                        <tr>
                            <th style="padding:8px; background:#2A5C8F; color:#ffffff; border:1px solid #ddd;">Sede</th>
                            <th style="padding:8px; background:#2A5C8F; color:#ffffff; border:1px solid #ddd;">Ventas</th>
                            <th style="padding:8px; background:#2A5C8F; color:#ffffff; border:1px solid #ddd;">Unidades</th>
                        </tr>
                        {filas_sedes}
                    </table>
                </td>
            </tr>
            <!-- Sección de Gráficos -->
            <tr>
                <td style="padding:20px;">
                    <h2 style="color:#2A5C8F;">Análisis Visual</h2>
                    <table width="100%" cellpadding="10">
                        <tr>
                            <td><img src="cid:ventas_horarias.png" alt="Ventas Horarias" style="width:100%; border-radius:8px; box-shadow:0 2px 4px rgba(0,0,0,0.1);"></td>
                        </tr>
                        <tr>
                            <td><img src="cid:metodos_pago.png" alt="Métodos de Pago" style="width:100%; border-radius:8px; box-shadow:0 2px 4px rgba(0,0,0,0.1);"></td>
                        </tr>
                        <tr>
                            <td><img src="cid:top_productos.png" alt="Top Productos" style="width:100%; border-radius:8px; box-shadow:0 2px 4px rgba(0,0,0,0.1);"></td>
                        </tr>
                        <tr>
                            <td><img src="cid:ventas_sedes.png" alt="Ventas por Sede" style="width:100%; border-radius:8px; box-shadow:0 2px 4px rgba(0,0,0,0.1);"></td>
                        </tr>
                    </table>
                </td>
            </tr>
            <!-- Hallazgos Clave -->
            <tr>
                <td style="padding:20px; background:#f8f9fa;">
                    <h2 style="color:#2A5C8F;">🔍 Hallazgos Clave</h2>
                    <ul style="color:#555; font-size:16px;">
                        <li><strong>Método de venta predominante:</strong> {analisis['modo_venta_comun']}</li>
                        <li><strong>Sede con mayores ventas:</strong> {analisis['sede_mas_ventas']}</li>
                        <li><strong>Producto líder:</strong> {analisis['top_producto']}</li>
                    </ul>
                </td>
            </tr>
            <!-- Footer -->
            <tr>
                <td style="background: linear-gradient(135deg, #2A5C8F, #1a365f); padding:20px; text-align:center;">
                    <p style="color:#ffffff; font-size:14px; margin:0;">🔒 Reporte generado automáticamente - {fecha_reporte}</p>
                    <p style="color:#ffffff; font-size:12px; margin:5px 0 0;">© 2024 Tu Empresa | Todos los derechos reservados</p>
                </td>
            </tr>
        </table>
    </body>
    </html>
    """
    return cuerpo

def enviar_email(analisis, df, fecha_reporte):
    """
    Envía el correo diario adjuntando gráficos y un CSV con el detalle de ventas.
    """
    try:
        msg = MIMEMultipart()
        msg['Subject'] = f"📊 Reporte Ventas Diarias - {fecha_reporte}"
        msg['From'] = SENDER_EMAIL
        msg['To'] = ", ".join(RECEIVER_EMAILS)
        
        # Generar gráficos diarios
        generar_graficos(df, fecha_reporte)
        
        # Cuerpo HTML
        body = crear_cuerpo_email(analisis, fecha_reporte)
        msg.attach(MIMEText(body, 'html'))
        
        # Adjuntar imágenes
        imagenes = ['ventas_horarias.png', 'metodos_pago.png', 'top_productos.png', 'ventas_sedes.png']
        for imagen in imagenes:
            with open(imagen, 'rb') as img:
                image = MIMEImage(img.read(), name=os.path.basename(imagen))
                image.add_header('Content-ID', f'<{imagen}>')
                msg.attach(image)
        
        # Adjuntar CSV con detalle de ventas
        csv_file = df.to_csv(index=False)
        adjunto = MIMEApplication(csv_file)
        adjunto.add_header('Content-Disposition', 'attachment', 
                           filename=f"detalle_ventas_{fecha_reporte.replace('/', '-')}.csv")
        msg.attach(adjunto)
        
        # Enviar email
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.sendmail(SENDER_EMAIL, RECEIVER_EMAILS, msg.as_string())
            logger.info("Email diario enviado exitosamente.")
        
        # Limpieza de archivos gráficos temporales
        for imagen in imagenes:
            if os.path.exists(imagen):
                os.remove(imagen)
                logger.info(f"Archivo {imagen} eliminado.")
    except Exception as e:
        logger.error(f"Error al enviar email diario: {str(e)}")
        raise

def obtener_datos_ventas():
    """
    Extrae los datos de ventas del día anterior desde la base de datos.
    """
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        query = """
            SELECT * FROM ventas_totales_2024 
            WHERE DATE(`Timestamp`) = CURDATE() - INTERVAL 1 DAY
        """
        df = pd.read_sql(query, conn, parse_dates=['Timestamp'])
        conn.close()
        logger.info("Datos diarios obtenidos correctamente.")
        return df
    except Exception as e:
        logger.error(f"Error al obtener datos diarios: {str(e)}")
        raise

@app.route('/generate_report', methods=['POST'])
def generate_report():
    """
    Endpoint para generar y enviar el reporte diario de ventas.
    """
    try:
        auth_token = request.headers.get('Authorization')
        if not auth_token or auth_token != os.environ.get('API_TOKEN'):
            logger.warning("Solicitud no autorizada.")
            return jsonify({"error": "Unauthorized"}), 401

        df_ventas = obtener_datos_ventas()
        if not df_ventas.empty:
            analisis = generar_analisis(df_ventas)
            fecha_reporte = (datetime.now() - timedelta(days=1)).strftime('%d/%m/%Y')
            enviar_email(analisis, df_ventas, fecha_reporte)
            return jsonify({"message": "Reporte diario generado y enviado exitosamente."}), 200
        else:
            logger.info("No hay ventas para el período analizado.")
            return jsonify({"message": "No hay ventas para el período analizado."}), 200
    except Exception as e:
        logger.error(f"Error en la generación del reporte diario: {str(e)}")
        return jsonify({"error": str(e)}), 500

######################################
# FUNCIONES PARA REPORTES SEMANALES
######################################

def generar_graficos_semanales(df, fecha_inicio, fecha_fin):
    """
    Genera gráficos semanales: ventas por día de la semana, comparación por sedes
    y evolución diaria.
    """
    try:
        colores = ['#2A5C8F', '#30A5BF', '#F2B705', '#F25C05']
        
        # 1. Ventas por día de la semana
        plt.figure(figsize=(10, 6))
        df['Dia_Semana'] = df['Timestamp'].dt.day_name()
        # Reordenar según la secuencia habitual
        dias_orden = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        ventas_diarias = df.groupby('Dia_Semana')['Precio'].sum().reindex(dias_orden)
        ax = sns.barplot(x=ventas_diarias.index, y=ventas_diarias.values, palette=colores)
        ax.set_title(f'Ventas por Día de la Semana\n{fecha_inicio} a {fecha_fin}', fontsize=18, weight='bold')
        ax.set_xlabel('Día de la semana')
        ax.set_ylabel('Total Ventas (S/.)')
        plt.xticks(rotation=45)
        plt.tight_layout()
        plt.savefig('ventas_semanales.png')
        plt.close()
        logger.info("Gráfico 'ventas_semanales.png' generado correctamente.")
        
        # 2. Comparación de ventas por sedes
        plt.figure(figsize=(10, 6))
        ventas_sedes = df.groupby('Sede')['Precio'].sum().sort_values(ascending=False)
        ax = sns.barplot(x=ventas_sedes.values, y=ventas_sedes.index, palette=colores)
        ax.set_title('Ventas por Sede', fontsize=18, weight='bold')
        ax.set_xlabel('Total Ventas (S/.)')
        plt.tight_layout()
        plt.savefig('ventas_sedes.png')
        plt.close()
        logger.info("Gráfico 'ventas_sedes.png' generado correctamente.")
        
        # 3. Evolución diaria de ventas
        plt.figure(figsize=(12, 6))
        df['Fecha'] = df['Timestamp'].dt.date
        ventas_diarias_line = df.groupby('Fecha')['Precio'].sum()
        ax = sns.lineplot(x=list(ventas_diarias_line.index), y=ventas_diarias_line.values,
                          marker='o', color=colores[0], linewidth=2.5)
        ax.set_title('Evolución Diaria de Ventas', fontsize=18, weight='bold')
        ax.set_xlabel('Fecha')
        ax.set_ylabel('Total Ventas (S/.)')
        plt.xticks(rotation=45)
        plt.tight_layout()
        plt.savefig('evolucion_diaria.png')
        plt.close()
        logger.info("Gráfico 'evolucion_diaria.png' generado correctamente.")
    except Exception as e:
        logger.error(f"Error al generar gráficos semanales: {str(e)}")
        raise

def generar_analisis_semanal(df, df_semana_anterior=None):
    """
    Genera un análisis semanal con métricas globales y comparativas, si se
    dispone de datos de la semana anterior.
    """
    try:
        ventas_por_dia = df.groupby(df['Timestamp'].dt.date)['Precio'].sum()
        analisis = {
            'total_ventas': df['Precio'].sum(),
            'total_unidades': df['Cantidad'].sum(),
            'venta_promedio_diaria': ventas_por_dia.mean(),
            'dia_max_ventas': ventas_por_dia.idxmax().strftime('%d/%m/%Y'),
            'max_venta_dia': ventas_por_dia.max(),
            'sede_mas_ventas': df.groupby('Sede')['Precio'].sum().idxmax(),
            'ventas_sede_lider': df.groupby('Sede')['Precio'].sum().max(),
            'top_producto': df.groupby('SKU')['Cantidad'].sum().idxmax(),
            'unidades_top_producto': df.groupby('SKU')['Cantidad'].sum().max(),
            'crecimiento_semanal': 0  # Implementar comparación con semana anterior si se requiere
        }
        logger.info("Análisis semanal generado correctamente.")
        return analisis
    except Exception as e:
        logger.error(f"Error al generar análisis semanal: {str(e)}")
        raise

def crear_cuerpo_email_semanal(analisis, fecha_inicio, fecha_fin):
    """
    Crea el cuerpo HTML del correo semanal, incluyendo métricas principales,
    evolución diaria y hallazgos destacados.
    """
    cuerpo = f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <title>Reporte Semanal de Ventas</title>
    </head>
    <body style="font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color:#f4f6f9; margin:0; padding:0;">
        <div style="max-width:800px; margin:20px auto; background-color:#ffffff; border-radius:8px; overflow:hidden; box-shadow:0 2px 8px rgba(0,0,0,0.1);">
            <!-- Header -->
            <div style="background: linear-gradient(135deg, #2A5C8F, #1a365f); padding:30px; text-align:center;">
                <img src="cid:logo_empresa.png" alt="Logo Empresa" style="width:60px; height:60px; margin-bottom:10px;">
                <h1 style="color:#ffffff; margin:0; font-size:28px;">📆 Reporte Semanal de Ventas</h1>
                <p style="color:#ffffff; margin:5px 0 0; font-size:16px;">{fecha_inicio} - {fecha_fin}</p>
            </div>
            <!-- Métricas Globales -->
            <div style="padding:20px;">
                <table width="100%" cellpadding="10">
                    <tr>
                        <td style="text-align:center; background:#f8f9fa; border-radius:8px; box-shadow:0 2px 4px rgba(0,0,0,0.1);">
                            <h3 style="color:#2A5C8F; margin:0;">Total Ventas</h3>
                            <p style="font-size:24px; color:#333;">S/. {analisis['total_ventas']:,.2f}</p>
                        </td>
                        <td style="text-align:center; background:#f8f9fa; border-radius:8px; box-shadow:0 2px 4px rgba(0,0,0,0.1);">
                            <h3 style="color:#2A5C8F; margin:0;">Unidades Vendidas</h3>
                            <p style="font-size:24px; color:#333;">{analisis['total_unidades']}</p>
                        </td>
                    </tr>
                </table>
            </div>
            <!-- Sección de Gráficos -->
            <div style="padding:20px;">
                <h2 style="color:#2A5C8F; margin-bottom:15px;">Análisis Visual</h2>
                <div style="margin-bottom:20px;">
                    <img src="cid:ventas_semanales.png" alt="Ventas Semanales" style="width:100%; border-radius:8px; box-shadow:0 2px 4px rgba(0,0,0,0.1);">
                </div>
                <div style="margin-bottom:20px;">
                    <img src="cid:ventas_sedes.png" alt="Ventas por Sede" style="width:100%; border-radius:8px; box-shadow:0 2px 4px rgba(0,0,0,0.1);">
                </div>
                <div>
                    <img src="cid:evolucion_diaria.png" alt="Evolución Diaria" style="width:100%; border-radius:8px; box-shadow:0 2px 4px rgba(0,0,0,0.1);">
                </div>
            </div>
            <!-- Hallazgos Destacados -->
            <div style="padding:20px; background:#f8f9fa;">
                <h2 style="color:#2A5C8F;">🔍 Hallazgos Destacados</h2>
                <ul style="color:#555; font-size:16px;">
                    <li><strong>Día de mayor venta:</strong> {analisis['dia_max_ventas']} (S/. {analisis['max_venta_dia']:,.2f})</li>
                    <li><strong>Sede líder:</strong> {analisis['sede_mas_ventas']} (S/. {analisis['ventas_sede_lider']:,.2f})</li>
                    <li><strong>Producto más vendido:</strong> {analisis['top_producto']} ({analisis['unidades_top_producto']} unidades)</li>
                    <li><strong>Crecimiento vs semana anterior:</strong> {analisis['crecimiento_semanal']}%</li>
                </ul>
            </div>
            <!-- Footer -->
            <div style="background: linear-gradient(135deg, #2A5C8F, #1a365f); padding:20px; text-align:center;">
                <p style="color:#ffffff; font-size:14px; margin:0;">🔒 Reporte generado automáticamente - {fecha_fin}</p>
                <p style="color:#ffffff; font-size:12px; margin:5px 0 0;">© 2024 Tu Empresa | Todos los derechos reservados</p>
            </div>
        </div>
    </body>
    </html>
    """
    return cuerpo

def enviar_email_semanal(analisis, df, fecha_inicio, fecha_fin):
    """
    Envía el correo semanal adjuntando gráficos y un CSV con el detalle de ventas.
    """
    try:
        msg = MIMEMultipart()
        msg['Subject'] = f"📈 Reporte Semanal de Ventas - {fecha_inicio} a {fecha_fin}"
        msg['From'] = SENDER_EMAIL
        msg['To'] = ", ".join(RECEIVER_EMAILS)
        
        # Generar gráficos semanales
        generar_graficos_semanales(df, fecha_inicio, fecha_fin)
        
        # Cuerpo HTML
        body = crear_cuerpo_email_semanal(analisis, fecha_inicio, fecha_fin)
        msg.attach(MIMEText(body, 'html'))
        
        # Adjuntar imágenes de los gráficos semanales
        imagenes = ['ventas_semanales.png', 'ventas_sedes.png', 'evolucion_diaria.png']
        for imagen in imagenes:
            with open(imagen, 'rb') as img:
                image = MIMEImage(img.read(), name=imagen)
                image.add_header('Content-ID', f'<{imagen}>')
                msg.attach(image)
        
        # Adjuntar CSV con detalle de ventas semanales
        csv_file = df.to_csv(index=False)
        adjunto = MIMEApplication(csv_file)
        adjunto.add_header('Content-Disposition', 'attachment', 
                           filename=f"detalle_ventas_{fecha_inicio.replace('/', '-')}_a_{fecha_fin.replace('/', '-')}.csv")
        msg.attach(adjunto)
        
        # Enviar email
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.sendmail(SENDER_EMAIL, RECEIVER_EMAILS, msg.as_string())
            logger.info("Email semanal enviado exitosamente.")
        
        # Limpieza de imágenes temporales
        for imagen in imagenes:
            if os.path.exists(imagen):
                os.remove(imagen)
    except Exception as e:
        logger.error(f"Error al enviar email semanal: {str(e)}")
        raise

def obtener_datos_semanales():
    """
    Extrae los datos de ventas de los últimos 7 días (excluyendo el día actual) de la base de datos.
    """
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        query = """
            SELECT * FROM ventas_totales_2024 
            WHERE DATE(`Timestamp`) BETWEEN CURDATE() - INTERVAL 7 DAY AND CURDATE() - INTERVAL 1 DAY
        """
        df = pd.read_sql(query, conn, parse_dates=['Timestamp'])
        conn.close()
        logger.info("Datos semanales obtenidos correctamente.")
        return df
    except Exception as e:
        logger.error(f"Error al obtener datos semanales: {str(e)}")
        raise

@app.route('/reporte_semanal', methods=['POST'])
def generate_weekly_report():
    """
    Endpoint para generar y enviar el reporte semanal de ventas.
    """
    try:
        auth_token = request.headers.get('Authorization')
        if not auth_token or auth_token != os.environ.get('API_TOKEN'):
            return jsonify({"error": "Unauthorized"}), 401

        df_ventas = obtener_datos_semanales()
        if not df_ventas.empty:
            fecha_fin = (datetime.now() - timedelta(days=1)).strftime('%d/%m/%Y')
            fecha_inicio = (datetime.now() - timedelta(days=7)).strftime('%d/%m/%Y')
            
            analisis = generar_analisis_semanal(df_ventas)
            enviar_email_semanal(analisis, df_ventas, fecha_inicio, fecha_fin)
            
            return jsonify({
                "message": "Reporte semanal generado y enviado exitosamente.",
                "periodo": f"{fecha_inicio} - {fecha_fin}"
            }), 200
        else:
            return jsonify({"message": "No hay datos para el período solicitado."}), 200
    except Exception as e:
        logger.error(f"Error en reporte semanal: {str(e)}")
        return jsonify({"error": str(e)}), 500

######################################
# ENDPOINTS ADICIONALES Y HOME
######################################

@app.route('/', methods=['GET'])
def home():
    return "Servicio de Reporte de Ventas Activo."

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)
