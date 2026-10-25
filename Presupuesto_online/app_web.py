import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from fpdf import FPDF
import datetime
import os
import smtplib
from email.message import EmailMessage
import json
import pandas as pd
import time

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Miranda Service", page_icon="🌿", layout="wide")

# --- DATOS DE CONFIGURACIÓN ---
CORREO_PAPA = "MirandaServiceOficial@gmail.com"
DIRECCION_PAPA_1 = "980 Dixie Line Rd"
DIRECCION_PAPA_2 = "Newark, DE 19713"
TELEFONO_PAPA = "(302) 602-9250"
SITIO_WEB = "www.mirandaservice.com"

try:
    PASSWORD_APP_GMAIL = st.secrets["gmail_password"]
except Exception:
    PASSWORD_APP_GMAIL = "yanwkulxewxpnccg"

DIRECTORIO_ACTUAL = os.path.dirname(os.path.abspath(__file__))
PLANTILLA_IMG = os.path.join(DIRECTORIO_ACTUAL, "plantilla_nueva.png")

# --- CONEXIÓN Y CREACIÓN AUTÓNOMA DE BASES DE DATOS (CON CACHÉ) ---
@st.cache_resource(ttl=3000)
def inicializar_base_datos():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    if "google_creds_json" in st.secrets:
        creds_dict = json.loads(st.secrets["google_creds_json"])
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    else:
        creds = ServiceAccountCredentials.from_json_keyfile_name("credenciales.json", scope)
    
    client = gspread.authorize(creds)
    db = client.open("Miranda_DB")
    
    def obtener_o_crear_hoja(nombre, filas, columnas, encabezados):
        try:
            hoja = db.worksheet(nombre)
        except gspread.exceptions.WorksheetNotFound:
            hoja = db.add_worksheet(title=nombre, rows=filas, cols=columnas)
        
        if not hoja.get_all_values():
            hoja.append_row(encabezados)
        return hoja

    h_cli = obtener_o_crear_hoja("Clientes", "100", "4", ["Nombre", "Correo", "Direccion", "Telefono"])
    h_srv = obtener_o_crear_hoja("Servicios", "50", "2", ["Servicio", "Precio"])
    h_fac = obtener_o_crear_hoja("Facturas", "1000", "7", ["Folio", "Cliente", "Fecha", "Vencimiento", "Total", "Estado", "Archivo"])
    h_tra = obtener_o_crear_hoja("Trabajos", "1000", "7", ["ID", "Cliente", "Fecha", "Servicio", "Cantidad", "Precio", "Estado"])
    
    return db, h_cli, h_srv, h_fac, h_tra

try:
    db, hoja_clientes, hoja_servicios, hoja_facturas, hoja_trabajos = inicializar_base_datos()
except Exception as e:
    st.error(f"error de conexión: {e}")
    st.stop()

# --- FUNCIONES DE LECTURA Y LIMPIEZA (CON CACHÉ DINÁMICO) ---
def limpiar_registros(registros):
    """Elimina espacios extra en los nombres de las columnas de Google Sheets."""
    limpios = []
    for fila in registros:
        limpios.append({str(k).strip(): v for k, v in fila.items()})
    return limpios

@st.cache_data(ttl=60)
def obtener_clientes():
    for intento in range(3):
        try:
            registros = limpiar_registros(hoja_clientes.get_all_records())
            return {
                str(f.get('Nombre', '')).strip(): {
                    'correo': str(f.get('Correo', '')).strip(),
                    'direccion': str(f.get('Direccion', '')).strip(),
                    'telefono': str(f.get('Telefono', '')).strip()
                }
                for f in registros if str(f.get('Nombre', '')).strip()
            }
        except Exception:
            time.sleep(2)
    return {}

@st.cache_data(ttl=60)
def obtener_servicios():
    for intento in range(3):
        try:
            registros = limpiar_registros(hoja_servicios.get_all_records())
            return {
                str(f.get('Servicio', '')).strip(): float(f.get('Precio', 0) or 0)
                for f in registros if str(f.get('Servicio', '')).strip()
            }
        except Exception:
            time.sleep(2)
    return {}

@st.cache_data(ttl=60)
def obtener_facturas_records():
    for intento in range(3):
        try:
            return limpiar_registros(hoja_facturas.get_all_records())
        except Exception:
            time.sleep(2)
    return []

@st.cache_data(ttl=60)
def obtener_trabajos():
    for intento in range(3):
        try:
            return limpiar_registros(hoja_trabajos.get_all_records())
        except Exception:
            time.sleep(2)
    return []

clientes_db = obtener_clientes()
servicios_db = obtener_servicios()

if "num_precio_reg" not in st.session_state:
    if servicios_db:
        primer_srv = list(servicios_db.keys())[0]
        st.session_state["num_precio_reg"] = float(servicios_db.get(primer_srv, 0.0))
    else:
        st.session_state["num_precio_reg"] = 0.0

# --- INTERFAZ PRINCIPAL ---
st.title("🌿 MIRANDA SERVICE ERP")
tab1, tab2, tab3, tab4 = st.tabs(["🗓️ REGISTRO SEMANAL", "🧾 FACTURAR MES", "📊 FINANZAS", "🗂️ DIRECTORIO"])

# --- PESTAÑA 1: REGISTRO SEMANAL ---
with tab1:
    st.header("AÑADIR NUEVO TRABAJO")
    if clientes_db:
        def actualizar_precio_sugerido():
            servicio_actual = st.session_state.select_serv_reg
            st.session_state.num_precio_reg = float(servicios_db.get(servicio_actual, 0.0))

        c_reg = st.selectbox("Seleccionar Cliente", list(clientes_db.keys()), key="select_cli_reg")
        f_reg = st.date_input("Fecha del Servicio", datetime.date.today(), key="date_reg", format="MM/DD/YYYY")
        
        c1, c2, c3 = st.columns([3, 1, 1])
        with c1:
            s_reg = st.selectbox("Servicio Realizado", list(servicios_db.keys()), key="select_serv_reg", on_change=actualizar_precio_sugerido)
        with c2:
            cant_reg = st.number_input("Cantidad", min_value=1, step=1, key="num_cant_reg")
        with c3:
            p_reg = st.number_input("Precio Unitario ($)", min_value=0.0, key="num_precio_reg")
        
        if st.button("💾 GUARDAR TRABAJO", type="primary", width="stretch"):
            id_trabajo = str(int(time.time()))
            fecha_formateada = f_reg.strftime("%m/%d/%Y")
            hoja_trabajos.append_row([id_trabajo, str(c_reg).strip(), fecha_formateada, str(s_reg).strip(), cant_reg, p_reg, "Pendiente"])
            obtener_trabajos.clear()
            st.success(f"trabajo guardado exitosamente para {c_reg}.")
            time.sleep(1)
            st.rerun()
                
        st.divider()
        st.subheader("TRABAJOS ACUMULADOS (SIN FACTURAR)")
        st.info("💡 instrucción: edita directamente en la tabla (doble clic) o selecciona una fila a la izquierda y pulsa el icono de papelera para borrarla. al terminar pulsa el botón guardar.")
        
        todos_los_trabajos = obtener_trabajos()
        if todos_los_trabajos:
            df_total = pd.DataFrame(todos_los_trabajos)
            df_total.columns = df_total.columns.str.strip()
            
            df_p = df_total[df_total['Estado'].astype(str).str.strip() == 'Pendiente'].copy()
            df_f_hist = df_total[df_total['Estado'].astype(str).str.strip() != 'Pendiente'].copy()

            if not df_p.empty:
                df_p['ID'] = df_p['ID'].astype(str)
                df_p['Cliente'] = df_p['Cliente'].astype(str).str.strip()
                df_p['Servicio'] = df_p['Servicio'].astype(str).str.strip()
                df_p['Estado'] = df_p['Estado'].astype(str).str.strip()
                df_p['Fecha'] = pd.to_datetime(df_p['Fecha'], errors='coerce').dt.date
                df_p['Cantidad'] = pd.to_numeric(df_p['Cantidad'], errors='coerce').fillna(1).astype(int)
                df_p['Precio'] = pd.to_numeric(df_p['Precio'], errors='coerce').fillna(0.0).astype(float)
                
                lista_clientes_limpia = [str(k).strip() for k in clientes_db.keys()]
                lista_servicios_limpia = [str(k).strip() for k in servicios_db.keys()]

                df_p_editado = st.data_editor(
                    df_p,
                    num_rows="dynamic",
                    width="stretch",
                    key="editor_trabajos_pendientes",
                    column_config={
                        "ID": st.column_config.TextColumn("ID", disabled=True),
                        "Estado": st.column_config.TextColumn("Estado", disabled=True, default="Pendiente"),
                        "Cliente": st.column_config.SelectboxColumn(
                            "Cliente",
                            options=lista_clientes_limpia,
                            required=True
                        ),
                        "Fecha": st.column_config.DateColumn("Fecha", format="MM/DD/YYYY"),
                        "Servicio": st.column_config.SelectboxColumn(
                            "Servicio",
                            options=lista_servicios_limpia
                        ),
                        "Cantidad": st.column_config.NumberColumn("Cantidad", min_value=1),
                        "Precio": st.column_config.NumberColumn("Precio", min_value=0.0)
                    }
                )
                
                if st.button("💾 GUARDAR CAMBIOS EN TABLA", type="secondary", width="stretch"):
                    df_p_editado['Fecha'] = pd.to_datetime(df_p_editado['Fecha'], errors='coerce').dt.strftime('%m/%d/%Y').fillna("")
                    df_p_editado['Estado'] = df_p_editado['Estado'].fillna("Pendiente").replace("", "Pendiente")
                    df_p_editado['ID'] = df_p_editado['ID'].fillna(str(int(time.time()))).replace("", str(int(time.time())))
                    df_final_subida = pd.concat([df_f_hist, df_p_editado], ignore_index=True)
                    
                    hoja_trabajos.clear()
                    headers = ["ID", "Cliente", "Fecha", "Servicio", "Cantidad", "Precio", "Estado"]
                    df_final_subida = df_final_subida.reindex(columns=headers, fill_value="")
                    data_rows = df_final_subida.fillna("").astype(str).values.tolist()
                    hoja_trabajos.append_rows([headers] + data_rows)
                    
                    obtener_trabajos.clear()
                    st.success("¡registros actualizados correctamente!")
                    time.sleep(1)
                    st.rerun()
            else:
                st.info("no hay trabajos pendientes.")
        else:
            st.info("no hay trabajos registrados.")
    else:
        st.warning("añade clientes en el directorio primero.")

# --- PESTAÑA 2: GENERACIÓN DE FACTURA ---
with tab2:
    st.header("GENERAR FACTURA CONSOLIDADA")
    trabajos_para_facturar = obtener_trabajos()
    
    if trabajos_para_facturar:
        df_tf = pd.DataFrame(trabajos_para_facturar)
        df_tf.columns = df_tf.columns.str.strip()
        df_pendientes_f = df_tf[df_tf['Estado'].astype(str).str.strip() == 'Pendiente'].copy()
        
        if not df_pendientes_f.empty:
            df_pendientes_f['Cliente_Str'] = df_pendientes_f['Cliente'].astype(str).str.strip()
            clientes_pendientes = df_pendientes_f['Cliente_Str'].unique().tolist()
            c_fac = st.selectbox("Seleccionar Cliente a Facturar", clientes_pendientes)
            c_fac_str = str(c_fac).strip()
            
            trabajos_cliente = df_pendientes_f[df_pendientes_f['Cliente_Str'] == c_fac_str].copy()
            trabajos_cliente['Fecha'] = trabajos_cliente['Fecha'].astype(str)
            trabajos_cliente['Servicio'] = trabajos_cliente['Servicio'].astype(str)
            trabajos_cliente['Cantidad'] = pd.to_numeric(trabajos_cliente['Cantidad'], errors='coerce').fillna(0)
            trabajos_cliente['Precio'] = pd.to_numeric(trabajos_cliente['Precio'], errors='coerce').fillna(0.0)
            trabajos_cliente['TotalFila'] = trabajos_cliente['Cantidad'] * trabajos_cliente['Precio']
            
            st.write(f"### Trabajos acumulados de {c_fac_str}")
            st.dataframe(
                trabajos_cliente[['Fecha', 'Servicio', 'Cantidad', 'Precio', 'TotalFila']],
                hide_index=True,
                width="stretch"
            )
            
            subtotal_mes = float(trabajos_cliente['TotalFila'].sum())
            
            col_t1, col_t2 = st.columns([2, 1])
            with col_t2:
                desc_val = st.number_input("Discount ($)", min_value=0.0, key="desc_mes")
                total_due = subtotal_mes - desc_val
                st.subheader(f"Total Due: ${total_due:,.2f}")
            
            with col_t1:
                st.write("### Payment Information")
                zelle_info = st.text_input("Zelle Email/Phone", "(302) 602-9250")
                cash_check = st.checkbox("Accept Cash/Check", value=True)

            st.divider()
            st.write("### 🔒 CONFIRMACIÓN DE SEGURIDAD")
            frase_secreta = st.text_input("escriba: ELESVAN MI HIJO FAVORITO", placeholder="escribe aquí...")
            
            boton_activado = (frase_secreta.strip() == "ELESVAN MI HIJO FAVORITO")
            
            if st.button("🚀 EMITIR FACTURA MENSUAL", type="primary", width="stretch", disabled=not boton_activado):
                with st.spinner("Creando PDF y enviando correo..."):
                    folio = f"FAC-{len(hoja_facturas.get_all_values()):04d}"
                    f_emision = datetime.date.today()
                    f_venc = f_emision + datetime.timedelta(days=5)
                    
                    datos_cli = clientes_db.get(c_fac_str, {})
                    cor_cli = str(datos_cli.get('correo', '')).strip()
                    dir_cli = str(datos_cli.get('direccion', '')).strip()
                    tel_cli = str(datos_cli.get('telefono', '')).strip()
                    
                    pdf = FPDF()
                    pdf.add_page()
                    if os.path.exists(PLANTILLA_IMG):
                        pdf.image(PLANTILLA_IMG, x=0, y=0, w=210, h=297)
                    
                    blue = (0, 102, 204)
                    pdf.set_font("Helvetica", 'B', 14); pdf.set_text_color(*blue)
                    pdf.text(120, 25, "MIRANDA SERVICE")
                    pdf.set_font("Helvetica", '', 10); pdf.set_text_color(0, 0, 0)
                    pdf.text(120, 30, DIRECCION_PAPA_1); pdf.text(120, 35, DIRECCION_PAPA_2)
                    pdf.text(120, 40, f"Tel: {TELEFONO_PAPA}")
                    pdf.set_font("Helvetica", 'B', 10); pdf.set_text_color(*blue)
                    pdf.text(120, 45, f"Web: {SITIO_WEB}")

                    pdf.set_font("Helvetica", 'B', 11); pdf.set_text_color(*blue)
                    pdf.text(15, 60, "BILLED TO:")
                    pdf.text(120, 60, f"INVOICE #: {folio}")
                    pdf.set_font("Helvetica", 'B', 10); pdf.set_text_color(0, 0, 0)
                    pdf.text(15, 65, c_fac_str)
                    pdf.set_font("Helvetica", '', 9)
                    pdf.set_xy(15, 67); pdf.multi_cell(80, 4, f"{dir_cli}\nTel: {tel_cli}")

                    pdf.set_font("Helvetica", '', 10)
                    pdf.text(120, 65, f"Issued: {f_emision.strftime('%m/%d/%Y')}")
                    pdf.set_text_color(200, 0, 0); pdf.text(120, 70, f"Due Date: {f_venc.strftime('%m/%d/%Y')}")
                    pdf.set_text_color(0, 0, 0)

                    pdf.set_fill_color(*blue); pdf.set_text_color(255, 255, 255)
                    pdf.set_xy(10, 90)
                    pdf.cell(30, 8, "Date", 1, 0, 'C', True)
                    pdf.cell(75, 8, "Description", 1, 0, 'C', True)
                    pdf.cell(15, 8, "Qty", 1, 0, 'C', True)
                    pdf.cell(35, 8, "Unit Price", 1, 0, 'C', True)
                    pdf.cell(35, 8, "Amount", 1, 1, 'C', True)

                    pdf.set_text_color(0, 0, 0); pdf.set_font("Helvetica", '', 10)
                    for index, row in trabajos_cliente.iterrows():
                        pdf.set_x(10)
                        
                        fecha_val = pd.to_datetime(row['Fecha'], errors='coerce')
                        fecha_imprimir = fecha_val.strftime('%m/%d/%Y') if pd.notna(fecha_val) else str(row['Fecha'])
                        
                        pdf.cell(30, 7, fecha_imprimir, 1, 0, 'C')
                        pdf.cell(75, 7, f" {str(row['Servicio'])}", 1)
                        pdf.cell(15, 7, str(int(row['Cantidad'])), 1, 0, 'C')
                        pdf.cell(35, 7, f"${float(row['Precio']):,.2f}", 1, 0, 'C')
                        pdf.cell(35, 7, f"${float(row['TotalFila']):,.2f}", 1, 1, 'C')

                    ty = pdf.get_y() + 8
                    pdf.set_font("Helvetica", 'B', 10)
                    pdf.text(140, ty, "Subtotal:")
                    pdf.text(175, ty, f"${subtotal_mes:,.2f}")
                    pdf.text(140, ty + 7, "Discount:")
                    pdf.set_text_color(200, 0, 0); pdf.text(175, ty + 7, f"-${desc_val:,.2f}")
                    
                    pdf.set_text_color(*blue); pdf.set_font("Helvetica", 'B', 13)
                    pdf.text(140, ty + 16, "TOTAL:")
                    pdf.text(175, ty + 16, f"${total_due:,.2f}")

                    pdf.set_font("Helvetica", 'B', 11); pdf.text(15, ty, "PAYMENT OPTIONS:")
                    pdf.set_text_color(0, 0, 0); pdf.set_font("Helvetica", '', 9)
                    pm_y = ty + 6
                    if zelle_info:
                        pdf.text(15, pm_y, f"Zelle: {zelle_info}")
                        pm_y += 5
                    if cash_check:
                        pdf.text(15, pm_y, "Check: Payable to Miranda Service / Cash Accepted")

                    fname = f"{folio}_{c_fac_str.replace(' ', '_')}.pdf"
                    pdf.output(fname)
                    
                    hoja_facturas.append_row([folio, c_fac_str, f_emision.strftime("%m/%d/%Y"), f_venc.strftime("%m/%d/%Y"), f"${total_due:,.2f}", "Pendiente", "Gmail Copy"])
                    
                    todas_filas_trabajos = hoja_trabajos.get_all_values()
                    for i, fila in enumerate(todas_filas_trabajos):
                        if i > 0 and len(fila) >= 7 and str(fila[1]).strip() == c_fac_str and str(fila[6]).strip() == "Pendiente":
                            hoja_trabajos.update_cell(i + 1, 7, "Facturado")
                            
                    obtener_facturas_records.clear()
                    obtener_trabajos.clear()
                    
                    if PASSWORD_APP_GMAIL:
                        try:
                            msg = EmailMessage()
                            msg['Subject'] = f'Invoice {folio} - Miranda Service LLC'
                            msg['From'] = CORREO_PAPA
                            
                            if cor_cli and "@" in cor_cli:
                                msg['To'] = cor_cli
                                msg['Cc'] = CORREO_PAPA
                            else:
                                msg['To'] = CORREO_PAPA
                                
                            msg.set_content(f"Hi {c_fac_str},\n\nAttached is invoice {folio}.\nTotal Due: ${total_due:,.2f}\n\nThank you!")
                            with open(fname, 'rb') as f:
                                msg.add_attachment(f.read(), maintype='application', subtype='pdf', filename=fname)
                            with smtplib.SMTP_SSL('smtp.gmail.com', 465) as s:
                                s.login(CORREO_PAPA, str(PASSWORD_APP_GMAIL).replace(" ", ""))
                                s.send_message(msg)
                            st.info(f"📧 Copia enviada exitosamente a {CORREO_PAPA}" + (f" y al cliente ({cor_cli})." if (cor_cli and "@" in cor_cli) else "."))
                        except Exception as e:
                            st.error(f"Error al enviar correo por Gmail SMTP: {e}")

                    st.success(f"Factura {folio} generada correctamente.")
                    with open(fname, "rb") as f:
                        pdf_bytes = f.read()
                    st.download_button("📥 DESCARGAR PDF", pdf_bytes, file_name=fname, mime="application/pdf", type="primary", width="stretch")
                    os.remove(fname)
        else:
            st.success("no hay trabajos pendientes para facturar.")

# --- PESTAÑA 3: FINANZAS ---
with tab3:
    st.header("ANÁLISIS FINANCIERO")
    data_f = obtener_facturas_records()
    if data_f:
        df_f = pd.DataFrame(data_f)
        df_f.columns = df_f.columns.str.strip()
        st.write("### Resumen Mensual")
        try:
            df_fin = df_f.copy()
            df_fin['Valor_Num'] = df_fin.iloc[:, 4].astype(str).str.replace('$', '', regex=False).str.replace(',', '', regex=False)
            df_fin['Valor_Num'] = pd.to_numeric(df_fin['Valor_Num'], errors='coerce').fillna(0)
            df_fin['Mes'] = pd.to_datetime(df_fin.iloc[:, 2], errors='coerce').dt.to_period('M')
            
            resumen = df_fin.groupby(['Mes', 'Estado'])['Valor_Num'].sum().unstack(fill_value=0)
            if 'Pagado' not in resumen.columns:
                resumen['Pagado'] = 0.0
            if 'Pendiente' not in resumen.columns:
                resumen['Pendiente'] = 0.0
            
            meses_list = sorted(resumen.index.astype(str).tolist(), reverse=True)
            if meses_list:
                mes_sel = st.selectbox("Seleccionar Mes:", meses_list)
                m_per = pd.Period(mes_sel, freq='M')
                
                m1, m2, m3 = st.columns(3)
                m1.metric("💰 Cobrado", f"${resumen.loc[m_per, 'Pagado']:,.2f}")
                m2.metric("⏳ Pendiente", f"${resumen.loc[m_per, 'Pendiente']:,.2f}")
                m3.metric("📊 Total", f"${(resumen.loc[m_per, 'Pagado'] + resumen.loc[m_per, 'Pendiente']):,.2f}")
        except Exception:
            st.warning("error al procesar datos financieros. verifica la estructura de la base de datos.")

        st.divider()
        st.write("### 🗂️ Registro General de Facturas")
        df_mostrar = df_f.drop(columns=["Archivo"]) if "Archivo" in df_f.columns else df_f.copy()
        df_mostrar = df_mostrar.astype(str)
        st.dataframe(df_mostrar, hide_index=True, width="stretch")

        st.divider()
        st.write("### Acciones sobre Facturas")
        todas = df_f.iloc[:, 0].astype(str).tolist() if not df_f.empty else []
        if todas:
            f_sel = st.selectbox("Seleccionar Factura:", todas)
            col_b1, col_b2 = st.columns(2)
            with col_b1:
                if st.button("✅ MARCAR COMO PAGADA", width="stretch"):
                    fila = hoja_facturas.find(str(f_sel)).row
                    hoja_facturas.update_cell(fila, 6, "Pagado")
                    obtener_facturas_records.clear()
                    st.rerun()
            with col_b2:
                if st.button("🗑️ ELIMINAR FACTURA", type="primary", width="stretch"):
                    fila = hoja_facturas.find(str(f_sel)).row
                    hoja_facturas.delete_rows(fila)
                    obtener_facturas_records.clear()
                    st.rerun()
    else:
        st.info("no hay facturas registradas.")

# --- PESTAÑA 4: DIRECTORIO ---
with tab4:
    st.header("GESTIÓN DE DIRECTORIO")
    st.info("💡 instrucción: edita directamente en la tabla (doble clic). al terminar pulsa el botón guardar.")
    
    col_c, col_s = st.columns([2, 1])
    
    with col_c:
        st.subheader("👥 Clientes")
        registros_clientes = limpiar_registros(hoja_clientes.get_all_records())
        df_cl = pd.DataFrame(registros_clientes).astype(str) if registros_clientes else pd.DataFrame(columns=["Nombre", "Correo", "Direccion", "Telefono"])
        df_cl_edit = st.data_editor(df_cl, num_rows="dynamic", width="stretch", key="edit_cli_full")
        
        if st.button("💾 GUARDAR CLIENTES", type="primary", width="stretch"):
            hoja_clientes.clear()
            datos_nuevos = [df_cl_edit.columns.tolist()] + df_cl_edit.fillna("").astype(str).values.tolist()
            hoja_clientes.append_rows(datos_nuevos)
            obtener_clientes.clear()
            st.success("directorio actualizado.")
            time.sleep(1)
            st.rerun()

    with col_s:
        st.subheader("🛠️ Servicios")
        registros_servicios = limpiar_registros(hoja_servicios.get_all_records())
        if registros_servicios:
            df_srv = pd.DataFrame(registros_servicios)
            df_srv['Servicio'] = df_srv['Servicio'].astype(str)
            df_srv['Precio'] = pd.to_numeric(df_srv['Precio'], errors='coerce').fillna(0.0)
        else:
            df_srv = pd.DataFrame(columns=["Servicio", "Precio"])
        df_srv_edit = st.data_editor(df_srv, num_rows="dynamic", width="stretch", key="edit_srv")
        
        if st.button("💾 GUARDAR SERVICIOS", type="primary", width="stretch"):
            hoja_servicios.clear()
            datos_nuevos = [df_srv_edit.columns.tolist()] + df_srv_edit.fillna("").astype(str).values.tolist()
            hoja_servicios.append_rows(datos_nuevos)
            obtener_servicios.clear()
            st.success("servicios actualizados.")
            time.sleep(1)
            st.rerun()
