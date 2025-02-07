import os
import smtplib
import mysql.connector
import plotly.express as px  # Usaremos Plotly para las gráficas
import matplotlib.pyplot as plt
import seaborn as sns
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

# Estilo global para gráficos con Seaborn y Matplotlib (se mantiene para otros usos si fuera necesario)
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
RECEIVER_EMAILS = ["gfxjef@gmail.com", "camachoteofilo1958@gmail.com", "max.campor@gmail.com", "milazcyn@gmail.com"]

######################################
# FUNCIONES PARA REPORTES DIARIOS
######################################

def generar_graficos(df, fecha_reporte):
    """
    Genera gráficos diarios utilizando Plotly:
      1. Evolución horaria de ventas.
      2. Distribución de métodos de pago.
      3. Top 5 productos más vendidos.
      4. Desglose de ventas por sedes.
    """
    try:
        colores = ['#2A5C8F', '#30A5BF', '#F2B705', '#F25C05']
        
        # 1. Evolución horaria de ventas
        df['Hora'] = df['Timestamp'].dt.hour
        ventas_horarias = df.groupby('Hora', as_index=False)['Precio'].sum()
        fig = px.line(
            ventas_horarias, 
            x='Hora', 
            y='Precio', 
            markers=True,
            title=f'Ventas por Hora - {fecha_reporte}', 
            labels={'Hora': 'Hora del día', 'Precio': 'Total Ventas (S/.)'}
        )
        fig.update_traces(line=dict(color=colores[0], width=2.5))
        fig.update_layout(xaxis=dict(tickmode='linear', dtick=1))
        fig.write_image('ventas_horarias.png')
        logger.info("Gráfico 'ventas_horarias.png' generado correctamente.")

        # 2. Distribución de métodos de pago
        metodos_pago = df['Modo de Venta'].value_counts().reset_index()
        metodos_pago.columns = ['Modo de Venta', 'Count']
        fig = px.pie(
            metodos_pago, 
            names='Modo de Venta', 
            values='Count',
            title='Distribución de Métodos de Pago',
            color_discrete_sequence=colores
        )
        fig.update_traces(textposition='inside', textinfo='percent+label')
        fig.write_image('metodos_pago.png')
        logger.info("Gráfico 'metodos_pago.png' generado correctamente.")

        # 3. Top 5 productos más vendidos (Marca + Modelo + tamano)
        if 'Producto' not in df.columns:
            df['Producto'] = df['Marca'] + " " + df['Modelo'] + " " + df['tamano']
        top_productos = df.groupby('Producto', as_index=False)['Cantidad'].sum().nlargest(5, 'Cantidad')
        fig = px.bar(
            top_productos, 
            x='Cantidad', 
            y='Producto', 
            orientation='h',
            title='Top 5 Productos Más Vendidos',
            labels={'Cantidad': 'Unidades Vendidas'},
            color_discrete_sequence=colores
        )
        fig.update_layout(yaxis={'categoryorder':'total ascending'})
        fig.write_image('top_productos.png')
        logger.info("Gráfico 'top_productos.png' generado correctamente.")

        # 4. Desglose de ventas por sedes
        ventas_sedes = df.groupby('Sede', as_index=False)['Precio'].sum().sort_values(by='Precio', ascending=False)
        fig = px.bar(
            ventas_sedes, 
            x='Precio', 
            y='Sede', 
            orientation='h',
            title='Ventas por Sede',
            labels={'Precio': 'Total Ventas (S/.)'},
            color_discrete_sequence=colores
        )
        fig.write_image('ventas_sedes.png')
        logger.info("Gráfico 'ventas_sedes.png' generado correctamente.")

    except Exception as e:
        logger.error(f"Error al generar gráficos diarios: {str(e)}")
        raise


def generar_analisis(df):
    """
    Genera un análisis de ventas diario con métricas globales y por sedes.
    """
    try:
        if 'Producto' not in df.columns:
            df['Producto'] = df['Marca'] + " " + df['Modelo'] + " " + df['tamano']
            
        analisis = {
            'total_ventas': df['Precio'].sum(),
            'total_unidades': df['Cantidad'].sum(),
            'venta_promedio': df['Precio'].mean(),
            'top_producto': df['Producto'].mode()[0],
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
    Crea el cuerpo HTML del correo diario.
    """
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
            <tr>
                <td style="background: linear-gradient(135deg, #2A5C8F, #1a365f); padding:30px; text-align:center;">
                    <img src="cid:logo_empresa.png" alt="Logo Empresa" style="width:60px; height:60px; margin-bottom:10px;">
                    <h1 style="color:#ffffff; margin:0; font-size:28px;">📈 Reporte Diario de Ventas</h1>
                    <p style="color:#ffffff; margin:5px 0 0; font-size:16px;">{fecha_reporte}</p>
                </td>
            </tr>
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
        
        # Generar gráficos diarios con Plotly
        generar_graficos(df, fecha_reporte)
        
        # Cuerpo HTML del email
        body = crear_cuerpo_email(analisis, fecha_reporte)
        msg.attach(MIMEText(body, 'html'))
        
        # Adjuntar imágenes generadas
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
        
        # Eliminar archivos gráficos temporales
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
    Genera gráficos semanales utilizando Plotly:
      1. Ventas por día de la semana desglosadas por sede.
      2. Distribución de ventas por sede (gráfico de torta).
      3. Evolución diaria de ventas.
      4. Top 10 Productos Más Vendidos.
    """
    try:
        colores = ['#2A5C8F', '#30A5BF', '#F2B705', '#F25C05', '#7D3C98', '#27AE60']
        
        # Filtrar datos para la última semana completa
        last_monday, last_sunday = get_last_week_range()
        df_last_week = df[df['Timestamp'].dt.date.between(last_monday.date(), last_sunday.date())]
        
        # 1. Ventas por día de la semana por Sede
        dias_abreviados = {
            'Monday': 'Lun',
            'Tuesday': 'Mar',
            'Wednesday': 'Mier',
            'Thursday': 'Juev',
            'Friday': 'Vier',
            'Saturday': 'Sab',
            'Sunday': 'Dom'
        }
        df_last_week['Dia_Ingles'] = df_last_week['Timestamp'].dt.day_name()
        df_last_week['Dia_Abreviado'] = df_last_week['Dia_Ingles'].map(dias_abreviados)
        orden_dias = ['Lun', 'Mar', 'Mier', 'Juev', 'Vier', 'Sab', 'Dom']
        ventas_dia_sede = df_last_week.groupby(['Dia_Abreviado', 'Sede'], as_index=False)['Precio'].sum()
        ventas_dia_sede['Dia_Abreviado'] = pd.Categorical(ventas_dia_sede['Dia_Abreviado'], categories=orden_dias, ordered=True)
        fig = px.bar(
            ventas_dia_sede, 
            x='Dia_Abreviado', 
            y='Precio', 
            color='Sede', 
            barmode='group',
            title='Ventas por Día de la Semana y por Sede',
            labels={'Precio': 'Total Ventas (S/.)', 'Dia_Abreviado': 'Día de la Semana'},
            color_discrete_sequence=colores
        )
        fig.write_image('ventas_dia_sede.png')
        logger.info("Gráfico 'ventas_dia_sede.png' generado correctamente.")

        # 2. Distribución de ventas por Sede (Gráfico de torta)
        ventas_sedes = df_last_week.groupby('Sede', as_index=False)['Precio'].sum()
        fig = px.pie(
            ventas_sedes, 
            names='Sede', 
            values='Precio',
            title='Distribución de Ventas por Sede',
            color_discrete_sequence=colores[:len(ventas_sedes)]
        )
        fig.update_traces(textposition='inside', textinfo='percent+label')
        fig.write_image('ventas_sedes.png')
        logger.info("Gráfico 'ventas_sedes.png' generado correctamente.")

        # 3. Evolución diaria de ventas
        df_last_week['Fecha'] = df_last_week['Timestamp'].dt.date
        ventas_diarias = df_last_week.groupby('Fecha', as_index=False)['Precio'].sum()
        fig = px.line(
            ventas_diarias, 
            x='Fecha', 
            y='Precio', 
            markers=True,
            title='Evolución Diaria de Ventas',
            labels={'Fecha': 'Fecha', 'Precio': 'Total Ventas (S/.)'},
            color_discrete_sequence=[colores[0]]
        )
        fig.write_image('evolucion_diaria.png')
        logger.info("Gráfico 'evolucion_diaria.png' generado correctamente.")

        # 4. Top 10 Productos Más Vendidos
        if 'Producto' not in df_last_week.columns:
            df_last_week['Producto'] = df_last_week['Marca'] + " " + df_last_week['Modelo'] + " " + df_last_week['tamano']
        top10 = df_last_week.groupby('Producto', as_index=False)['Cantidad'].sum().nlargest(10, 'Cantidad')
        fig = px.bar(
            top10, 
            x='Cantidad', 
            y='Producto', 
            orientation='h',
            title='Top 10 Productos Más Vendidos',
            labels={'Cantidad': 'Unidades Vendidas'},
            color_discrete_sequence=colores[:len(top10)]
        )
        fig.update_layout(yaxis={'categoryorder':'total ascending'})
        fig.write_image('top10_productos.png')
        logger.info("Gráfico 'top10_productos.png' generado correctamente.")

    except Exception as e:
        logger.error(f"Error al generar gráficos semanales: {str(e)}")
        raise

def generar_analisis_semanal(df, df_semana_anterior=None):
    """
    Genera un análisis semanal con métricas globales y comparativas.
    """
    try:
        if 'Producto' not in df.columns:
            df['Producto'] = df['Marca'] + " " + df['Modelo'] + " " + df['tamano']
        
        ventas_por_dia = df.groupby(df['Timestamp'].dt.date)['Precio'].sum()
        crecimiento = generar_grafico_evolucion_semanal(df)
        
        analisis = {
            'total_ventas': df[df['Timestamp'].dt.date.between(*get_last_week_range_dates())]['Precio'].sum(),
            'total_unidades': df[df['Timestamp'].dt.date.between(*get_last_week_range_dates())]['Cantidad'].sum(),
            'venta_promedio_diaria': ventas_por_dia.mean(),
            'dia_max_ventas': ventas_por_dia.idxmax().strftime('%d/%m/%Y'),
            'max_venta_dia': ventas_por_dia.max(),
            'sede_mas_ventas': df.groupby('Sede')['Precio'].sum().idxmax(),
            'ventas_sede_lider': df.groupby('Sede')['Precio'].sum().max(),
            'top_producto': df.groupby('Producto')['Cantidad'].sum().idxmax(),
            'unidades_top_producto': df.groupby('Producto')['Cantidad'].sum().max(),
            'crecimiento_semanal': round(crecimiento, 2)
        }
        logger.info("Análisis semanal generado correctamente.")
        return analisis
    except Exception as e:
        logger.error(f"Error al generar análisis semanal: {str(e)}")
        raise

def get_last_week_range_dates():
    last_monday, last_sunday = get_last_week_range()
    return last_monday.date(), last_sunday.date()

def crear_cuerpo_email_semanal(analisis, fecha_inicio, fecha_fin):
    cuerpo = f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <title>Reporte Semanal de Ventas</title>
    </head>
    <body style="font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color:#f4f6f9; margin:0; padding:0;">
        <div style="max-width:800px; margin:20px auto; background-color:#ffffff; border-radius:8px; overflow:hidden; box-shadow:0 2px 8px rgba(0,0,0,0.1);">
            <div style="background: linear-gradient(135deg, #2A5C8F, #1a365f); padding:30px; text-align:center;">
                <img src="cid:logo_empresa.png" alt="Logo Empresa" style="width:60px; height:60px; margin-bottom:10px;">
                <h1 style="color:#ffffff; margin:0; font-size:28px;">📆 Reporte Semanal de Ventas</h1>
                <p style="color:#ffffff; margin:5px 0 0; font-size:16px;">{fecha_inicio} - {fecha_fin}</p>
            </div>
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
            <div style="padding:20px;">
                <h2 style="color:#2A5C8F; margin-bottom:15px;">Análisis Visual</h2>
                <div style="margin-bottom:20px;">
                    <img src="cid:ventas_dia_sede.png" alt="Ventas por Día y Sede" style="width:100%; border-radius:8px; box-shadow:0 2px 4px rgba(0,0,0,0.1);">
                </div>
                <div style="margin-bottom:20px;">
                    <img src="cid:ventas_sedes.png" alt="Distribución de Ventas por Sede" style="width:100%; border-radius:8px; box-shadow:0 2px 4px rgba(0,0,0,0.1);">
                </div>
                <div style="margin-bottom:20px;">
                    <img src="cid:evolucion_diaria.png" alt="Evolución Diaria de Ventas" style="width:100%; border-radius:8px; box-shadow:0 2px 4px rgba(0,0,0,0.1);">
                </div>
                <div style="margin-bottom:20px;">
                    <img src="cid:evolucion_semanal.png" alt="Evolución Semanal de Ventas" style="width:100%; border-radius:8px; box-shadow:0 2px 4px rgba(0,0,0,0.1);">
                </div>
                <div>
                    <img src="cid:top10_productos.png" alt="Top 10 Productos Más Vendidos" style="width:100%; border-radius:8px; box-shadow:0 2px 4px rgba(0,0,0,0.1);">
                </div>
            </div>
            <div style="padding:20px; background:#f8f9fa;">
                <h2 style="color:#2A5C8F;">🔍 Hallazgos Destacados</h2>
                <ul style="color:#555; font-size:16px;">
                    <li><strong>Día con mayor venta:</strong> {analisis['dia_max_ventas']} (S/. {analisis['max_venta_dia']:,.2f})</li>
                    <li><strong>Sede líder:</strong> {analisis['sede_mas_ventas']} (S/. {analisis['ventas_sede_lider']:,.2f})</li>
                    <li><strong>Nombre del producto:</strong> {analisis['top_producto']} ({analisis['unidades_top_producto']} unidades)</li>
                    <li><strong>Crecimiento vs semana anterior:</strong> {analisis['crecimiento_semanal']}%</li>
                </ul>
            </div>
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
    try:
        msg = MIMEMultipart()
        msg['Subject'] = f"📈 Reporte Semanal de Ventas - {fecha_inicio} a {fecha_fin}"
        msg['From'] = SENDER_EMAIL
        msg['To'] = ", ".join(RECEIVER_EMAILS)
        
        generar_graficos_semanales(df, fecha_inicio, fecha_fin)
        growth = generar_grafico_evolucion_semanal(df)
        
        body = crear_cuerpo_email_semanal(analisis, fecha_inicio, fecha_fin)
        msg.attach(MIMEText(body, 'html'))
        
        imagenes = [
            'ventas_dia_sede.png', 
            'ventas_sedes.png', 
            'evolucion_diaria.png', 
            'evolucion_semanal.png',
            'top10_productos.png'
        ]
        for imagen in imagenes:
            with open(imagen, 'rb') as img:
                image = MIMEImage(img.read(), name=os.path.basename(imagen))
                image.add_header('Content-ID', f'<{imagen}>')
                msg.attach(image)
        
        csv_file = df.to_csv(index=False)
        adjunto = MIMEApplication(csv_file)
        adjunto.add_header('Content-Disposition', 'attachment', 
                           filename=f"detalle_ventas_{fecha_inicio.replace('/', '-')}_a_{fecha_fin.replace('/', '-')}.csv")
        msg.attach(adjunto)
        
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.sendmail(SENDER_EMAIL, RECEIVER_EMAILS, msg.as_string())
            logger.info("Email semanal enviado exitosamente.")
        
        for imagen in imagenes:
            if os.path.exists(imagen):
                os.remove(imagen)
    except Exception as e:
        logger.error(f"Error al enviar email semanal: {str(e)}")
        raise

def obtener_datos_semanales():
    """
    Extrae los datos de ventas para abarcar desde el lunes de la semana anterior
    hasta el domingo de la última semana completa.
    """
    try:
        last_monday, last_sunday = get_last_week_range()
        prev_monday, _ = get_previous_week_range(last_monday, last_sunday)
        fecha_inicio_query = prev_monday.strftime('%Y-%m-%d')
        fecha_fin_query = last_sunday.strftime('%Y-%m-%d')
        
        conn = mysql.connector.connect(**DB_CONFIG)
        query = """
            SELECT * FROM ventas_totales_2024 
            WHERE DATE(`Timestamp`) BETWEEN %s AND %s
        """
        df = pd.read_sql(query, conn, parse_dates=['Timestamp'], params=(fecha_inicio_query, fecha_fin_query))
        conn.close()
        logger.info("Datos semanales obtenidos correctamente.")
        return df
    except Exception as e:
        logger.error(f"Error al obtener datos semanales: {str(e)}")
        raise

@app.route('/reporte_semanal', methods=['POST'])
def generate_weekly_report():
    try:
        auth_token = request.headers.get('Authorization')
        if not auth_token or auth_token != os.environ.get('API_TOKEN'):
            return jsonify({"error": "Unauthorized"}), 401

        df_ventas = obtener_datos_semanales()
        if not df_ventas.empty:
            last_monday, last_sunday = get_last_week_range()
            fecha_inicio_email = last_monday.strftime('%d/%m/%Y')
            fecha_fin_email = last_sunday.strftime('%d/%m/%Y')
            
            analisis = generar_analisis_semanal(df_ventas)
            enviar_email_semanal(analisis, df_ventas, fecha_inicio_email, fecha_fin_email)
            
            return jsonify({
                "message": "Reporte semanal generado y enviado exitosamente.",
                "periodo": f"{fecha_inicio_email} - {fecha_fin_email}"
            }), 200
        else:
            return jsonify({"message": "No hay datos para el período solicitado."}), 200
    except Exception as e:
        logger.error(f"Error en reporte semanal: {str(e)}")
        return jsonify({"error": str(e)}), 500

def get_last_week_range():
    """
    Calcula el rango completo de la última semana (último lunes hasta el domingo anterior).
    """
    today = datetime.now()
    monday_this_week = today - timedelta(days=today.weekday())
    last_monday = monday_this_week - timedelta(days=7)
    last_sunday = monday_this_week - timedelta(days=1)
    return last_monday, last_sunday
    
def get_previous_week_range(last_monday, last_sunday):
    """
    Calcula el rango de la semana anterior al rango dado.
    """
    prev_monday = last_monday - timedelta(days=7)
    prev_sunday = last_sunday - timedelta(days=7)
    return prev_monday, prev_sunday

def generar_grafico_evolucion_semanal(df):
    """
    Genera un gráfico de barras comparando el total de ventas de la última semana contra la semana anterior.
    Calcula el crecimiento porcentual y exporta la imagen con Plotly.
    """
    last_monday, last_sunday = get_last_week_range()
    prev_monday, prev_sunday = get_previous_week_range(last_monday, last_sunday)
    
    df_last = df[(df['Timestamp'].dt.date >= last_monday.date()) & (df['Timestamp'].dt.date <= last_sunday.date())]
    df_prev = df[(df['Timestamp'].dt.date >= prev_monday.date()) & (df['Timestamp'].dt.date <= prev_sunday.date())]
    
    total_last = df_last['Precio'].sum()
    total_prev = df_prev['Precio'].sum()
    
    if total_prev != 0:
        growth = ((total_last - total_prev) / total_prev) * 100
    else:
        growth = 0
    
    semanas = ['Semana Anterior', 'Última Semana']
    totales = [total_prev, total_last]
    
    fig = px.bar(
        x=semanas, 
        y=totales, 
        color=semanas,
        title='Evolución Semanal de Ventas',
        labels={'x': 'Semana', 'y': 'Total Ventas (S/.)'},
        color_discrete_map={'Semana Anterior': '#7D3C98', 'Última Semana': '#27AE60'}
    )
    fig.update_traces(text=[f"S/ {total_prev:,.2f}", f"S/ {total_last:,.2f}"], textposition='outside')
    fig.write_image('evolucion_semanal.png')
    logger.info("Gráfico 'evolucion_semanal.png' generado correctamente.")
    
    return growth

@app.route('/', methods=['GET'])
def home():
    return "Servicio de Reporte de Ventas Activo."

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)
