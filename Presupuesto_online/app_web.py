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
except:
    PASSWORD_APP_GMAIL = "yanwkulxewxpnccg" 

DIRECTORIO_ACTUAL = os.path.dirname(os.path.abspath(__file__))
PLANTILLA_IMG = os.path.join(DIRECTORIO_ACTUAL, "plantilla_nueva.png")

# --- CONEXIÓN A GOOGLE WORKSPACE ---
@st.cache_resource
def conectar_servicios():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    if "google_creds_json" in st.secrets:
        creds_dict = json.loads(st.secrets["google_creds_json"])
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    else:
        creds = ServiceAccountCredentials.from_json_keyfile_name("credenciales.json", scope)
    client = gspread.authorize(creds)
    sheet = client.open("Miranda_DB")
    return sheet

try:
    db = conectar_servicios()
    hoja_clientes = db.worksheet("Clientes")
    hoja_servicios = db.worksheet("Servicios")
    hoja_facturas = db.worksheet("Facturas")
    
    try:
        hoja_trabajos = db.worksheet("Trabajos")
    except gspread.exceptions.WorksheetNotFound:
        hoja_trabajos = db.add_worksheet(title="Trabajos", rows="1000", cols="7")
        hoja_trabajos.append_row(["ID", "Cliente", "Fecha", "Servicio", "Cantidad", "Precio", "Estado"])
        
except Exception as e:
    st.error(f"Error de conexión: {e}")
    st.stop()

# --- FUNCIONES DE BASE DE DATOS ---
@st.cache_data(ttl=600)
def obtener_clientes():
    for intento in range(3):
        try:
            registros = hoja_clientes.get_all_records()
            return {
                str(f.get('Nombre','')).strip(): {
                    'correo': str(f.get('Correo','')).strip(),
                    'direccion': str(f.get('Direccion','')).strip(),
                    'telefono': str(f.get('Telefono','')).strip()
                }
                for f in registros if f.get('Nombre')
            }
        except Exception: time.sleep(2)
    return {}

@st.cache_data(ttl=600)
def obtener_servicios():
    for intento in range(3):
        try:
            registros = hoja_servicios.get_all_records()
            return {str(f.get('Servicio','')).strip(): float(f.get('Precio',0)) for f in registros if f.get('Servicio')}
        except Exception: time.sleep(2)
    return {}

@st.cache_data(ttl=600)
def obtener_facturas_records():
    for intento in range(3):
        try: return hoja_facturas.get_all_records()
        except Exception: time.sleep(2)
    return []

@st.cache_data(ttl=300) 
def obtener_trabajos():
    for intento in range(3):
        try: return hoja_trabajos.get_all_records()
        except Exception: time.sleep(2)
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
        f_reg = st.date_input("Fecha del Servicio", datetime.date.today(), key="date_reg")
        
        c1, c2, c3 = st.columns([3, 1, 1])
        with c1: 
            s_reg = st.selectbox("Servicio Realizado", list(servicios_db.keys()), key="select_serv_reg", on_change=actualizar_precio_sugerido)
        with c2: 
            cant_reg = st.number_input("Cantidad", min_value=1, step=1, key="num_cant_reg")
        with c3: 
            p_reg = st.number_input("Precio Unitario ($)", min_value=0.0, key="num_precio_reg")
        
        if st.button("💾 GUARDAR TRABAJO", type="primary", use_container_width=True):
            id_trabajo = str(int(time.time())) 
            hoja_trabajos.append_row([id_trabajo, c_reg, str(f_reg), s_reg, cant_reg, p_reg, "Pendiente"])
            obtener_trabajos.clear()
            st.success(f"Trabajo guardado exitosamente para {c_reg}.")
            time.sleep(1)
            st.rerun()
                
        st.divider()
        st.subheader("TRABAJOS ACUMULADOS (SIN FACTURAR)")
        st.info("💡 instruccion: edita directamente en la tabla (doble clic). puedes borrar filas seleccionandolas. al terminar pulsa el boton guardar.")
        
        todos_los_trabajos = obtener_trabajos()
        if todos_los_trabajos:
            df_total = pd.DataFrame(todos_los_trabajos)
            # Editor interactivo para los pendientes con candados de seguridad
                df_p_editado = st.data_editor(
                    df_p, 
                    num_rows="fixed",  # <--- Evita que se creen nuevos trabajos desde la tabla
                    use_container_width=True, 
                    key="editor_trabajos_pendientes",
                    column_config={
                        "ID": st.column_config.TextColumn("ID", disabled=True),
                        "Estado": st.column_config.TextColumn("Estado", disabled=True), # <--- Bloquea la edición
                        "Cliente": st.column_config.SelectboxColumn(
                            "Cliente", 
                            options=list(clientes_db.keys()), # <--- Desplegable con tus clientes
                            required=True
                        ),
                        "Servicio": st.column_config.SelectboxColumn(
                            "Servicio", 
                            options=list(servicios_db.keys()) # <--- Desplegable con tus servicios
                        ),
                        "Cantidad": st.column_config.NumberColumn("Cantidad", min_value=1),
                        "Precio": st.column_config.NumberColumn("Precio", min_value=0.0)
                    }
                )
                
                if st.button("💾 GUARDAR CAMBIOS EN TABLA", type="secondary", use_container_width=True):
                    # Combinamos lo editado con lo que ya estaba facturado anteriormente
                    df_final_subida = pd.concat([df_f_hist, df_p_editado], ignore_index=True)
                    
                    hoja_trabajos.clear()
                    # Re-subimos encabezados y datos
                    headers = df_final_subida.columns.tolist()
                    data_rows = df_final_subida.fillna("").astype(str).values.tolist()
                    hoja_trabajos.append_rows([headers] + data_rows)
                    
                    obtener_trabajos.clear()
                    st.success("¡Registros actualizados correctamente!")
                    time.sleep(1)
                    st.rerun()
            else:
                st.info("No hay trabajos pendientes.")
        else:
            st.info("No hay trabajos registrados.")
    else:
        st.warning("Añade clientes en el Directorio primero.")

# --- PESTAÑA 2: GENERACIÓN DE FACTURA ---
with tab2:
    st.header("GENERAR FACTURA CONSOLIDADA")
    trabajos_para_facturar = obtener_trabajos()
    
    if trabajos_para_facturar:
        df_tf = pd.DataFrame(trabajos_para_facturar)
        df_pendientes_f = df_tf[df_tf['Estado'] == 'Pendiente']
        
        if not df_pendientes_f.empty:
            clientes_pendientes = df_pendientes_f['Cliente'].unique().tolist()
            c_fac = st.selectbox("Seleccionar Cliente a Facturar", clientes_pendientes)
            
            trabajos_cliente = df_pendientes_f[df_pendientes_f['Cliente'] == c_fac].copy()
            # Asegurar que cantidad y precio sean numéricos para el cálculo
            trabajos_cliente['Cantidad'] = pd.to_numeric(trabajos_cliente['Cantidad'], errors='coerce').fillna(0)
            trabajos_cliente['Precio'] = pd.to_numeric(trabajos_cliente['Precio'], errors='coerce').fillna(0)
            trabajos_cliente['TotalFila'] = trabajos_cliente['Cantidad'] * trabajos_cliente['Precio']
            
            st.write(f"### Trabajos acumulados de {c_fac}")
            st.dataframe(trabajos_cliente[['Fecha', 'Servicio', 'Cantidad', 'Precio', 'TotalFila']], hide_index=True, use_container_width=True)
            
            subtotal_mes = trabajos_cliente['TotalFila'].sum()
            
            col_t1, col_t2 = st.columns([2,1])
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
            frase_secreta = st.text_input("escriba: ELESVAN MI HIJO FAVORITO", placeholder="Escribe aquí...")
            
            boton_activado = (frase_secreta == "ELESVAN MI HIJO FAVORITO")
            
            if st.button("🚀 EMITIR FACTURA MENSUAL", type="primary", use_container_width=True, disabled=not boton_activado):
                with st.spinner("Creando PDF..."):
                    folio = f"FAC-{len(hoja_facturas.get_all_values()):04d}"
                    f_emision = datetime.date.today()
                    f_venc = f_emision + datetime.timedelta(days=5)
                    
                    datos_cli = clientes_db.get(c_fac, {})
                    cor_cli = datos_cli.get('correo', '')
                    dir_cli = datos_cli.get('direccion', '')
                    tel_cli = datos_cli.get('telefono', '')
                    
                    pdf = FPDF()
                    pdf.add_page()
                    if os.path.exists(PLANTILLA_IMG):
                        pdf.image(PLANTILLA_IMG, x=0, y=0, w=210, h=297)
                    
                    blue = (0, 102, 204)
                    pdf.set_font("Helvetica", 'B', 14); pdf.set_text_color(*blue)
                    pdf.text(120, 25, "MIRANDA SERVICE")
                    pdf.set_font("Helvetica", '', 10); pdf.set_text_color(0,0,0)
                    pdf.text(120, 30, DIRECCION_PAPA_1); pdf.text(120, 35, DIRECCION_PAPA_2)
                    pdf.text(120, 40, f"Tel: {TELEFONO_PAPA}")
                    pdf.set_font("Helvetica", 'B', 10); pdf.set_text_color(*blue)
                    pdf.text(120, 45, f"Web: {SITIO_WEB}")

                    pdf.set_font("Helvetica", 'B', 11); pdf.set_text_color(*blue)
                    pdf.text(15, 60, "BILLED TO:")
                    pdf.text(120, 60, f"INVOICE #: {folio}")
                    pdf.set_font("Helvetica", 'B', 10); pdf.set_text_color(0,0,0)
                    pdf.text(15, 65, c_fac)
                    pdf.set_font("Helvetica", '', 9)
                    pdf.set_xy(15, 67); pdf.multi_cell(80, 4, f"{dir_cli}\nTel: {tel_cli}")

                    pdf.set_font("Helvetica", '', 10)
                    pdf.text(120, 65, f"Issued: {f_emision.strftime('%m/%d/%Y')}")
                    pdf.set_text_color(200, 0, 0); pdf.text(120, 70, f"Due Date: {f_venc.strftime('%m/%d/%Y')}")
                    pdf.set_text_color(0, 0, 0)

                    pdf.set_fill_color(*blue); pdf.set_text_color(255,255,255)
                    pdf.set_xy(10, 90)
                    pdf.cell(30, 8, "Date", 1, 0, 'C', True)
                    pdf.cell(75, 8, "Description", 1, 0, 'C', True)
                    pdf.cell(15, 8, "Qty", 1, 0, 'C', True)
                    pdf.cell(35, 8, "Unit Price", 1, 0, 'C', True)
                    pdf.cell(35, 8, "Amount", 1, 1, 'C', True)

                    pdf.set_text_color(0,0,0); pdf.set_font("Helvetica", '', 10)
                    for index, row in trabajos_cliente.iterrows():
                        pdf.set_x(10)
                        pdf.cell(30, 7, str(row['Fecha']), 1, 0, 'C')
                        pdf.cell(75, 7, f" {row['Servicio']}", 1)
                        pdf.cell(15, 7, str(row['Cantidad']), 1, 0, 'C')
                        pdf.cell(35, 7, f"${float(row['Precio']):,.2f}", 1, 0, 'C')
                        pdf.cell(35, 7, f"${float(row['TotalFila']):,.2f}", 1, 1, 'C')

                    ty = pdf.get_y() + 8
                    pdf.set_font("Helvetica", 'B', 10)
                    pdf.text(140, ty, "Subtotal:")
                    pdf.text(175, ty, f"${subtotal_mes:,.2f}")
                    pdf.text(140, ty+7, "Discount:")
                    pdf.set_text_color(200,0,0); pdf.text(175, ty+7, f"-${desc_val:,.2f}")
                    
                    pdf.set_text_color(*blue); pdf.set_font("Helvetica", 'B', 13)
                    pdf.text(140, ty+16, "TOTAL:")
                    pdf.text(175, ty+16, f"${total_due:,.2f}")

                    pdf.set_font("Helvetica", 'B', 11); pdf.text(15, ty, "PAYMENT OPTIONS:")
                    pdf.set_text_color(0, 0, 0); pdf.set_font("Helvetica", '', 9)
                    pm_y = ty + 6
                    if zelle_info: pdf.text(15, pm_y, f"Zelle: {zelle_info}"); pm_y += 5
                    if cash_check: pdf.text(15, pm_y, "Check: Payable to Miranda Service / Cash Accepted")

                    fname = f"{folio}_{c_fac.replace(' ','_')}.pdf"
                    pdf.output(fname)
                    
                    hoja_facturas.append_row([folio, c_fac, str(f_emision), str(f_venc), f"${total_due:,.2f}", "Pendiente", "Gmail Copy"])
                    
                    # Marcar trabajos como facturados en la nube
                    todas_filas_trabajos = hoja_trabajos.get_all_values()
                    for i, fila in enumerate(todas_filas_trabajos):
                        if i > 0 and fila[1] == c_fac and fila[6] == "Pendiente":
                            hoja_trabajos.update_cell(i+1, 7, "Facturado")
                            
                    obtener_facturas_records.clear()
                    obtener_trabajos.clear()
                    
                    if cor_cli and PASSWORD_APP_GMAIL != "yanwkulxewxpnccg":
                        try:
                            msg = EmailMessage()
                            msg['Subject'] = f'Invoice {folio} - Miranda Service LLC'
                            msg['From'] = CORREO_PAPA; msg['To'] = cor_cli; msg['Cc'] = CORREO_PAPA
                            msg.set_content(f"Hi {c_fac},\n\nAttached is invoice {folio}.\nTotal Due: ${total_due:,.2f}\n\nThank you!")
                            with open(fname, 'rb') as f: msg.add_attachment(f.read(), maintype='application', subtype='pdf', filename=fname)
                            with smtplib.SMTP_SSL('smtp.gmail.com', 465) as s:
                                s.login(CORREO_PAPA, PASSWORD_APP_GMAIL); s.send_message(msg)
                        except Exception as e: st.error(f"Error correo: {e}")

                    st.success(f"Factura {folio} generada correctamente.")
                    with open(fname, "rb") as f: st.download_button("📥 DESCARGAR PDF", f, file_name=fname, type="primary")
                    os.remove(fname)
        else:
            st.success("No hay trabajos pendientes para facturar.")

# --- PESTAÑA 3: FINANZAS ---
with tab3:
    st.header("ANÁLISIS FINANCIERO")
    data_f = obtener_facturas_records()
    if data_f:
        df_f = pd.DataFrame(data_f)
        st.write("### Resumen Mensual")
        try:
            df_fin = df_f.copy()
            df_fin['Valor_Num'] = df_fin.iloc[:, 4].astype(str).str.replace('$', '', regex=False).str.replace(',', '', regex=False)
            df_fin['Valor_Num'] = pd.to_numeric(df_fin['Valor_Num'], errors='coerce').fillna(0)
            df_fin['Mes'] = pd.to_datetime(df_fin.iloc[:, 2], errors='coerce').dt.to_period('M')
            
            resumen = df_fin.groupby(['Mes', 'Estado'])['Valor_Num'].sum().unstack(fill_value=0)
            if 'Pagado' not in resumen.columns: resumen['Pagado'] = 0.0
            if 'Pendiente' not in resumen.columns: resumen['Pendiente'] = 0.0
            
            meses_list = sorted(resumen.index.astype(str).tolist(), reverse=True)
            if meses_list:
                mes_sel = st.selectbox("Seleccionar Mes:", meses_list)
                m_per = pd.Period(mes_sel, freq='M')
                
                m1, m2, m3 = st.columns(3)
                m1.metric("💰 Cobrado", f"${resumen.loc[m_per, 'Pagado']:,.2f}")
                m2.metric("⏳ Pendiente", f"${resumen.loc[m_per, 'Pendiente']:,.2f}")
                m3.metric("📊 Total", f"${(resumen.loc[m_per, 'Pagado'] + resumen.loc[m_per, 'Pendiente']):,.2f}")
        except: st.warning("Error al procesar datos financieros.")

        st.divider()
        st.write("### Acciones sobre Facturas")
        todas = df_f.iloc[:, 0].tolist() if not df_f.empty else []
        if todas:
            f_sel = st.selectbox("Seleccionar Factura:", todas)
            col_b1, col_b2 = st.columns(2)
            with col_b1:
                if st.button("✅ MARCAR COMO PAGADA", use_container_width=True):
                    fila = hoja_facturas.find(f_sel).row
                    hoja_facturas.update_cell(fila, 6, "Pagado")
                    obtener_facturas_records.clear(); st.rerun()
            with col_b2:
                if st.button("🗑️ ELIMINAR FACTURA", type="primary", use_container_width=True):
                    fila = hoja_facturas.find(f_sel).row
                    hoja_facturas.delete_rows(fila)
                    obtener_facturas_records.clear(); st.rerun()
    else: st.info("No hay facturas registradas.")

# --- PESTAÑA 4: DIRECTORIO ---
with tab4:
    st.header("GESTIÓN DE DIRECTORIO")
    st.info("💡 instruccion: edita directamente en la tabla (doble clic). al terminar pulsa el boton guardar.")
    
    col_c, col_s = st.columns([2, 1])
    
    with col_c:
        st.subheader("👥 Clientes")
        registros_clientes = hoja_clientes.get_all_records()
        df_cl = pd.DataFrame(registros_clientes).astype(str) if registros_clientes else pd.DataFrame(columns=["Nombre", "Correo", "Direccion", "Telefono"])
        df_cl_edit = st.data_editor(df_cl, num_rows="dynamic", use_container_width=True, key="edit_cli_full")
        
        if st.button("💾 GUARDAR CLIENTES", type="primary", use_container_width=True):
            hoja_clientes.clear()
            datos_nuevos = [df_cl_edit.columns.tolist()] + df_cl_edit.fillna("").values.tolist()
            hoja_clientes.append_rows(datos_nuevos)
            obtener_clientes.clear()
            st.success("Directorio actualizado.")
            time.sleep(1); st.rerun()

    with col_s:
        st.subheader("🛠️ Servicios")
        registros_servicios = hoja_servicios.get_all_records()
        df_srv = pd.DataFrame(registros_servicios) if registros_servicios else pd.DataFrame(columns=["Servicio", "Precio"])
        df_srv_edit = st.data_editor(df_srv, num_rows="dynamic", use_container_width=True, key="edit_srv")
        
        if st.button("💾 GUARDAR SERVICIOS", type="primary", use_container_width=True):
            hoja_servicios.clear()
            datos_nuevos = [df_srv_edit.columns.tolist()] + df_srv_edit.fillna("").values.tolist()
            hoja_servicios.append_rows(datos_nuevos)
            obtener_servicios.clear()
            st.success("Servicios actualizados.")
            time.sleep(1); st.rerun()
