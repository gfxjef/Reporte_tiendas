# Añadir estas funciones adicionales
def generar_graficos_semanales(df, fecha_inicio, fecha_fin):
    try:
        colores = ['#2A5C8F', '#30A5BF', '#F2B705', '#F25C05']
        
        # Gráfico 1: Ventas por día de la semana
        plt.figure(figsize=(10, 6))
        df['Dia_Semana'] = df['Timestamp'].dt.day_name()
        ventas_diarias = df.groupby('Dia_Semana')['Precio'].sum().reindex([
            'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'
        ])
        sns.barplot(x=ventas_diarias.index, y=ventas_diarias.values, palette=colores)
        plt.title(f'Ventas por Día de la Semana\n{fecha_inicio} a {fecha_fin}', fontsize=14)
        plt.xlabel('Día de la semana')
        plt.ylabel('Total Ventas (S/.)')
        plt.xticks(rotation=45)
        plt.tight_layout()
        plt.savefig('ventas_semanales.png')
        plt.close()
        logger.info("Gráfico 'ventas_semanales.png' generado correctamente.")
        
        # Gráfico 2: Comparación de sedes
        plt.figure(figsize=(10, 6))
        ventas_sedes = df.groupby('Sede')['Precio'].sum().sort_values(ascending=False)
        sns.barplot(x=ventas_sedes.values, y=ventas_sedes.index, palette=colores, orient='h')
        plt.title('Ventas por Sede', fontsize=14)
        plt.xlabel('Total Ventas (S/.)')
        plt.tight_layout()
        plt.savefig('ventas_sedes.png')
        plt.close()
        logger.info("Gráfico 'ventas_sedes.png' generado correctamente.")
        
        # Gráfico 3: Evolución diaria de ventas
        plt.figure(figsize=(12, 6))
        df['Fecha'] = df['Timestamp'].dt.date
        ventas_diarias_line = df.groupby('Fecha')['Precio'].sum()
        sns.lineplot(x=ventas_diarias_line.index, y=ventas_diarias_line.values, 
                    marker='o', color=colores[0], linewidth=2.5)
        plt.title('Evolución Diaria de Ventas', fontsize=14)
        plt.xlabel('Fecha')
        plt.ylabel('Total Ventas (S/.)')
        plt.xticks(rotation=45)
        plt.tight_layout()
        plt.savefig('evolucion_diaria.png')
        plt.close()
        logger.info("Gráfico 'evolucion_diaria.png' generado correctamente.")
    except Exception as e:
        logger.error(f"Error al generar gráficos semanales: {str(e)}")
        raise

def crear_cuerpo_email_semanal(analisis, fecha_inicio, fecha_fin):
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>Reporte Semanal de Ventas</title>
    </head>
    <body style="font-family: Arial, sans-serif;">
        <div style="max-width: 800px; margin: 0 auto; padding: 20px;">
            <h1 style="color: #2A5C8F; text-align: center;">📆 Reporte Semanal de Ventas</h1>
            <h3 style="text-align: center; color: #555;">{fecha_inicio} al {fecha_fin}</h3>
            
            <div style="background-color: #f8f9fa; padding: 20px; border-radius: 10px; margin: 20px 0;">
                <h2 style="color: #2A5C8F;">Métricas Principales</h2>
                <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 15px;">
                    <div style="background-color: white; padding: 15px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                        <h3 style="margin: 0; color: #30A5BF;">Total Ventas</h3>
                        <p style="font-size: 24px; margin: 10px 0; color: #333;">S/. {analisis['total_ventas']:,.2f}</p>
                    </div>
                    <div style="background-color: white; padding: 15px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                        <h3 style="margin: 0; color: #30A5BF;">Unidades Vendidas</h3>
                        <p style="font-size: 24px; margin: 10px 0; color: #333;">{analisis['total_unidades']}</p>
                    </div>
                </div>
            </div>

            <div style="margin: 20px 0;">
                <h2 style="color: #2A5C8F;">Análisis Visual</h2>
                <img src="cid:ventas_semanales.png" alt="Ventas Semanales" style="width: 100%; margin-bottom: 20px; border-radius: 8px;">
                <img src="cid:ventas_sedes.png" alt="Ventas por Sede" style="width: 100%; margin-bottom: 20px; border-radius: 8px;">
                <img src="cid:evolucion_diaria.png" alt="Evolución Diaria" style="width: 100%; border-radius: 8px;">
            </div>

            <div style="background-color: #f8f9fa; padding: 20px; border-radius: 10px; margin-top: 20px;">
                <h2 style="color: #2A5C8F;">🔍 Hallazgos Destacados</h2>
                <ul>
                    <li>Día de mayor venta: {analisis['dia_max_ventas']} (S/. {analisis['max_venta_dia']:,.2f})</li>
                    <li>Sede líder: {analisis['sede_mas_ventas']} (S/. {analisis['ventas_sede_lider']:,.2f})</li>
                    <li>Producto más vendido: {analisis['top_producto']} ({analisis['unidades_top_producto']} unidades)</li>
                    <li>Crecimiento vs semana anterior: {analisis['crecimiento_semanal']}%</li>
                </ul>
            </div>
        </div>
    </body>
    </html>
    """

def obtener_datos_semanales():
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

def generar_analisis_semanal(df, df_semana_anterior=None):
    try:
        analisis = {
            'total_ventas': df['Precio'].sum(),
            'total_unidades': df['Cantidad'].sum(),
            'venta_promedio_diaria': df.groupby(df['Timestamp'].dt.date)['Precio'].sum().mean(),
            'dia_max_ventas': df['Timestamp'].dt.date.value_counts().idxmax().strftime('%d/%m/%Y'),
            'max_venta_dia': df.groupby(df['Timestamp'].dt.date)['Precio'].sum().max(),
            'sede_mas_ventas': df.groupby('Sede')['Precio'].sum().idxmax(),
            'ventas_sede_lider': df.groupby('Sede')['Precio'].sum().max(),
            'top_producto': df.groupby('SKU')['Cantidad'].sum().idxmax(),
            'unidades_top_producto': df.groupby('SKU')['Cantidad'].sum().max(),
            'crecimiento_semanal': 0  # Se puede implementar comparación con semana anterior
        }
        logger.info("Análisis semanal generado correctamente.")
        return analisis
    except Exception as e:
        logger.error(f"Error al generar análisis semanal: {str(e)}")
        raise

def enviar_email_semanal(analisis, df, fecha_inicio, fecha_fin):
    try:
        msg = MIMEMultipart()
        msg['Subject'] = f"📈 Reporte Semanal de Ventas - {fecha_inicio} a {fecha_fin}"
        msg['From'] = SENDER_EMAIL
        msg['To'] = ", ".join(RECEIVER_EMAILS)
        
        generar_graficos_semanales(df, fecha_inicio, fecha_fin)
        
        body = crear_cuerpo_email_semanal(analisis, fecha_inicio, fecha_fin)
        msg.attach(MIMEText(body, 'html'))
        
        for imagen in ['ventas_semanales.png', 'ventas_sedes.png', 'evolucion_diaria.png']:
            with open(imagen, 'rb') as img:
                image = MIMEImage(img.read(), name=imagen)
                image.add_header('Content-ID', f'<{imagen}>')
                msg.attach(image)
        
        csv_file = df.to_csv(index=False)
        adjunto = MIMEApplication(csv_file)
        adjunto.add_header('Content-Disposition', 'attachment', 
                         filename=f"detalle_ventas_{fecha_inicio}_a_{fecha_fin}.csv")
        msg.attach(adjunto)
        
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.sendmail(SENDER_EMAIL, RECEIVER_EMAILS, msg.as_string())
            logger.info("Email semanal enviado exitosamente.")
        
        for imagen in ['ventas_semanales.png', 'ventas_sedes.png', 'evolucion_diaria.png']:
            if os.path.exists(imagen):
                os.remove(imagen)
    except Exception as e:
        logger.error(f"Error al enviar email semanal: {str(e)}")
        raise

@app.route('/reporte_semanal', methods=['POST'])
def generate_weekly_report():
    """
    Endpoint para generar y enviar el reporte semanal de ventas
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
