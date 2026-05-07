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
st.set_page_config(page_title="Miranda Service ERP", page_icon="🌿", layout="wide")

# --- DATOS DE CONFIGURACIÓN ---
CORREO_PAPA = "MirandaServiceOficial@gmail.com"
DIRECCION_PAPA_1 = "980 Dixie Line Rd"
DIRECCION_PAPA_2 = "Newark, DE 19713"
TELEFONO_PAPA = "(302) 602-9250"
SITIO_WEB = "www.mirandaservice.com"

try:
    PASSWORD_APP_GMAIL = st.secrets["gmail_password"]
except:
    PASSWORD_APP_GMAIL = "yanwkulxewxpnccg" # Clave de 16 dígitos

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
    
    # Intentar abrir la hoja de trabajos, si no existe, crearla automáticamente
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

# --- INICIALIZAR MEMORIA PARA EL PRECIO ---
if "precio_inicial_cargado" not in st.session_state:
    st.session_state["precio_inicial_cargado"] = True
    if servicios_db:
        primer_srv = list(servicios_db.keys())[0]
        st.session_state["num_precio_reg"] = float(servicios_db.get(primer_srv, 0.0))
    else:
        st.session_state["num_precio_reg"] = 0.0

# --- INTERFAZ PRINCIPAL ---
st.title("🌿 MIRANDA SERVICE ERP")
tab1, tab2, tab3, tab4 = st.tabs(["🗓️ Registro Semanal", "🧾 Facturar Mes", "📊 Finanzas", "🗂️ Directorio"])

# --- PESTAÑA 1: REGISTRO SEMANAL DE TRABAJOS ---
with tab1:
    st.header("Añadir Trabajo a la Cuenta del Cliente")
    if clientes_db:
        
        # Función para actualizar el precio al instante
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
            # Streamlit respetará el valor forzado por la memoria
            p_reg = st.number_input("Precio Unitario ($)", min_value=0.0, key="num_precio_reg")
        
        if st.button("💾 Guardar Trabajo (Pendiente)", type="primary", use_container_width=True):
            id_trabajo = str(int(time.time())) 
            hoja_trabajos.append_row([id_trabajo, c_reg, str(f_reg), s_reg, cant_reg, p_reg, "Pendiente"])
            obtener_trabajos.clear()
            st.success(f"Trabajo guardado exitosamente para {c_reg}.")
            time.sleep(1)
            st.rerun()
                
        st.divider()
        st.subheader("Trabajos Acumulados (Sin Facturar)")
        trabajos_act = obtener_trabajos()
        if trabajos_act:
            df_t = pd.DataFrame(trabajos_act)
            df_pendientes = df_t[df_t['Estado'] == 'Pendiente'].copy()
            if not df_pendientes.empty:
                df_pendientes['Subtotal'] = df_pendientes['Cantidad'] * df_pendientes['Precio']
                st.dataframe(df_pendientes[['Cliente', 'Fecha', 'Servicio', 'Cantidad', 'Precio', 'Subtotal']], hide_index=True, use_container_width=True)
                
                # --- SECCIÓN: EDICIÓN DE TRABAJOS ---
                st.write("### ✏️ Editar / Borrar Trabajos")
                df_pendientes['ID'] = df_pendientes['ID'].astype(str)
                opciones_tr = df_pendientes.apply(lambda x: f"{x['ID']} | {x['Cliente']} - {x['Fecha']} - {x['Servicio']}", axis=1).tolist()
                
                tr_sel = st.selectbox("Selecciona un trabajo para modificar:", opciones_tr)
                
                if tr_sel:
                    id_target = tr_sel.split(" | ")[0].strip()
                    datos_tr = df_pendientes[df_pendientes['ID'] == id_target].iloc[0]
                    
                    col_e1, col_e2 = st.columns([2, 1])
                    with col_e1:
                        with st.form("form_edit_tr"):
                            st.write("**Modificar datos:**")
                            n_f = st.date_input("Fecha", pd.to_datetime(datos_tr['Fecha']).date())
                            n_s = st.text_input("Servicio", value=datos_tr['Servicio'])
                            n_c = st.number_input("Cantidad", min_value=1, value=int(datos_tr['Cantidad']))
                            n_p = st.number_input("Precio ($)", min_value=0.0, value=float(datos_tr['Precio']))
                            
                            if st.form_submit_button("Actualizar Trabajo"):
                                cell = hoja_trabajos.find(id_target)
                                hoja_trabajos.update_cell(cell.row, 3, str(n_f))
                                hoja_trabajos.update_cell(cell.row, 4, n_s)
                                hoja_trabajos.update_cell(cell.row, 5, n_c)
                                hoja_trabajos.update_cell(cell.row, 6, n_p)
                                obtener_trabajos.clear()
                                st.rerun()
                                
                    with col_e2:
                        st.write("**Eliminar registro:**")
                        if st.button("🗑️ Borrar este trabajo", type="primary", use_container_width=True):
                            cell = hoja_trabajos.find(id_target)
                            hoja_trabajos.delete_rows(cell.row)
                            obtener_trabajos.clear()
                            st.rerun()

            else:
                st.info("Todos los trabajos han sido facturados.")
        else:
            st.info("No hay trabajos registrados.")
    else:
        st.warning("Añade clientes en el Directorio primero.")

# --- PESTAÑA 2: GENERACIÓN DE FACTURA MENSUAL ---
with tab2:
    st.header("Generar Factura Consolidada")
    trabajos_para_facturar = obtener_trabajos()
    
    if trabajos_para_facturar:
        df_tf = pd.DataFrame(trabajos_para_facturar)
        df_pendientes_f = df_tf[df_tf['Estado'] == 'Pendiente']
        
        if not df_pendientes_f.empty:
            clientes_pendientes = df_pendientes_f['Cliente'].unique().tolist()
            c_fac = st.selectbox("Seleccionar Cliente a Facturar", clientes_pendientes)
            
            trabajos_cliente = df_pendientes_f[df_pendientes_f['Cliente'] == c_fac]
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
                zelle_info = st.text_input("Zelle Email/Phone", value=CORREO_PAPA)
                venmo_info = st.text_input("Venmo Username", value="@MirandaService")
                cash_check = st.checkbox("Accept Cash/Check", value=True)

            if st.button("🚀 Emitir Factura Mensual", type="primary", use_container_width=True):
                with st.spinner("Compilando trabajos y creando PDF..."):
                    folio = f"FAC-{len(hoja_facturas.get_all_values()):04d}"
                    f_emision = datetime.date.today()
                    f_venc = f_emision + datetime.timedelta(days=5)
                    
                    datos_cli = clientes_db.get(c_fac, {})
                    cor_cli = datos_cli.get('correo', '')
                    dir_cli = datos_cli.get('direccion', '')
                    tel_cli = datos_cli.get('telefono', '')
                    
                    # --- PDF GENERATION ---
                    pdf = FPDF()
                    pdf.add_page()
                    if os.path.exists(PLANTILLA_IMG):
                        pdf.image(PLANTILLA_IMG, x=0, y=0, w=210, h=297)
                    
                    blue = (0, 102, 204)
                    
                    # Encabezado con Sitio Web
                    pdf.set_font("Helvetica", 'B', 14); pdf.set_text_color(*blue)
                    pdf.text(120, 25, "MIRANDA SERVICE LLC")
                    pdf.set_font("Helvetica", '', 10); pdf.set_text_color(0,0,0)
                    pdf.text(120, 30, DIRECCION_PAPA_1); pdf.text(120, 35, DIRECCION_PAPA_2)
                    pdf.text(120, 40, f"Tel: {TELEFONO_PAPA}")
                    pdf.set_font("Helvetica", 'B', 10); pdf.set_text_color(*blue)
                    pdf.text(120, 45, f"Web: {SITIO_WEB}")

                    # Billed To
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

                    # Tabla
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
                        pdf.cell(35, 7, f"${row['Precio']:,.2f}", 1, 0, 'C')
                        pdf.cell(35, 7, f"${row['TotalFila']:,.2f}", 1, 1, 'C')

                    # Totales
                    ty = pdf.get_y() + 8
                    pdf.set_font("Helvetica", 'B', 10)
                    pdf.text(140, ty, "Subtotal:")
                    pdf.text(175, ty, f"${subtotal_mes:,.2f}")
                    pdf.text(140, ty+7, "Discount:")
                    pdf.set_text_color(200,0,0); pdf.text(175, ty+7, f"-${desc_val:,.2f}")
                    
                    pdf.set_text_color(*blue); pdf.set_font("Helvetica", 'B', 13)
                    pdf.text(140, ty+16, "TOTAL:")
                    pdf.text(175, ty+16, f"${total_due:,.2f}")

                    # Pagos
                    pdf.set_font("Helvetica", 'B', 11); pdf.text(15, ty, "PAYMENT OPTIONS:")
                    pdf.set_text_color(0, 0, 0); pdf.set_font("Helvetica", '', 9)
                    pm_y = ty + 6
                    if zelle_info: pdf.text(15, pm_y, f"Zelle: {zelle_info}"); pm_y += 5
                    if venmo_info: pdf.text(15, pm_y, f"Venmo: {venmo_info}"); pm_y += 5
                    if cash_check: pdf.text(15, pm_y, "Check: Payable to Miranda Service / Cash Accepted")

                    # Pie de página con Sitio Web
                    pdf.set_text_color(100, 100, 100); pdf.set_font("Helvetica", '', 8)
                    footer_text = f"Thank you for choosing Miranda Service! Visit us at {SITIO_WEB}\nFull payment is due within 5 days. Late fee of 5% may apply."
                    pdf.set_xy(15, 255); pdf.multi_cell(180, 4, footer_text, align='C')

                    # Guardar y Enviar
                    fname = f"{folio}_{c_fac.replace(' ','_')}.pdf"
                    pdf.output(fname)
                    
                    # Registrar en Google Sheets (Solo 7 columnas)
                    hoja_facturas.append_row([folio, c_fac, str(f_emision), str(f_venc), f"${total_due:,.2f}", "Pendiente", "Gmail Copy"])
                    
                    # Actualizar estado de los Trabajos
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

                    st.success(f"Factura {folio} generada. Trabajos marcados como completados.")
                    with open(fname, "rb") as f: st.download_button("📥 Descargar PDF", f, file_name=fname, type="primary")
                    
                    # Borrar archivo para no saturar el servidor
                    os.remove(fname)
        else:
            st.success("🎉 No hay clientes con trabajos pendientes de facturar.")
    else:
        st.info("Registra trabajos en la primera pestaña para poder facturarlos.")

# --- PESTAÑA 3: HISTORIAL Y FINANZAS INTERACTIVAS ---
with tab3:
    st.subheader("Análisis Financiero")
    data_f = obtener_facturas_records()
    if data_f:
        df_f = pd.DataFrame(data_f)
        
        st.write("### 📈 Resumen por Mes")
        try:
            col_fecha = df_f.columns[2] 
            col_total = df_f.columns[4]
            
            df_fin = df_f.copy()
            df_fin['Valor_Num'] = df_fin[col_total].astype(str).str.replace('$', '', regex=False).str.replace(',', '', regex=False)
            df_fin['Valor_Num'] = pd.to_numeric(df_fin['Valor_Num'], errors='coerce').fillna(0)
            df_fin['Mes'] = pd.to_datetime(df_fin[col_fecha], errors='coerce').dt.to_period('M')
            
            resumen = df_fin.groupby(['Mes', 'Estado'])['Valor_Num'].sum().unstack(fill_value=0)
            if 'Pagado' not in resumen.columns: resumen['Pagado'] = 0.0
            if 'Pendiente' not in resumen.columns: resumen['Pendiente'] = 0.0
            resumen['Total Generado'] = resumen['Pagado'] + resumen['Pendiente']
            
            meses_list = sorted(resumen.index.astype(str).tolist(), reverse=True)
            if meses_list:
                mes_sel = st.selectbox("📅 Ver métricas de:", meses_list)
                m_per = pd.Period(mes_sel, freq='M')
                
                m1, m2, m3 = st.columns(3)
                m1.metric(f"💰 Cobrado ({mes_sel})", f"${resumen.loc[m_per, 'Pagado']:,.2f}")
                m2.metric(f"⏳ Pendiente ({mes_sel})", f"${resumen.loc[m_per, 'Pendiente']:,.2f}")
                m3.metric(f"📊 Total Bruto", f"${resumen.loc[m_per, 'Total Generado']:,.2f}")
        except: st.warning("Datos insuficientes para finanzas.")

        st.divider()
        st.write("### 🗂️ Registro General")
        
        if 'Ruta_PDF' in df_f.columns: df_f = df_f.drop(columns=['Ruta_PDF'])
        st.dataframe(df_f, hide_index=True, use_container_width=True)
        
        st.divider()
        st.write("### 🛠️ Acciones sobre Facturas")
        c_p, c_r, c_b = st.columns(3)
        pendientes = df_f[df_f["Estado"] == "Pendiente"]["Folio"].tolist()
        pagadas = df_f[df_f["Estado"] == "Pagado"]["Folio"].tolist()
        todas = df_f["Folio"].tolist()

        with c_p:
            if pendientes:
                f_p = st.selectbox("Marcar Pagada:", pendientes, key="p_f")
                if st.button("💰 Confirmar Pago", use_container_width=True):
                    hoja_facturas.update_cell(hoja_facturas.find(f_p).row, 6, "Pagado")
                    obtener_facturas_records.clear(); st.rerun()
        with c_r:
            if pagadas:
                f_r = st.selectbox("Quitar Pagado:", pagadas, key="r_f")
                if st.button("⏪ Revertir a Pendiente", use_container_width=True):
                    hoja_facturas.update_cell(hoja_facturas.find(f_r).row, 6, "Pendiente")
                    obtener_facturas_records.clear(); st.rerun()
        with c_b:
            if todas:
                f_b = st.selectbox("Eliminar Factura:", todas, key="b_f")
                if st.button("🗑️ Borrar Factura", type="primary", use_container_width=True):
                    hoja_facturas.delete_rows(hoja_facturas.find(f_b).row)
                    obtener_facturas_records.clear(); st.rerun()
    else: st.info("No hay facturas registradas.")

# --- PESTAÑA 4: DIRECTORIO (CRUD CLIENTES Y SERVICIOS) ---
with tab4:
    st.header("👥 Gestión de Clientes")
    df_cl = pd.DataFrame([{'Nombre': k, 'Correo': v['correo'], 'Tel': v['telefono'], 'Dirección': v['direccion']} for k, v in clientes_db.items()])
    st.dataframe(df_cl, hide_index=True, use_container_width=True)
    
    t_c1, t_c2, t_c3 = st.tabs(["➕ Añadir", "✏️ Editar", "🗑️ Borrar"])
    with t_c1:
        with st.form("add_cli"):
            n_n = st.text_input("Nombre"); n_c = st.text_input("Email"); n_t = st.text_input("Tel"); n_d = st.text_area("Dir")
            if st.form_submit_button("Guardar"):
                if n_n: hoja_clientes.append_row([n_n, n_c, n_d, n_t]); obtener_clientes.clear(); st.rerun()
    with t_c2:
        if clientes_db:
            c_ed = st.selectbox("Elegir Cliente", list(clientes_db.keys()), key="ed_c")
            with st.form("edit_cli"):
                en = st.text_input("Nombre", value=c_ed)
                ec = st.text_input("Email", value=clientes_db[c_ed]['correo'])
                et = st.text_input("Tel", value=clientes_db[c_ed]['telefono'])
                ed = st.text_area("Dir", value=clientes_db[c_ed]['direccion'])
                
                if st.form_submit_button("Actualizar"):
                    celda = hoja_clientes.find(c_ed) # Primero buscamos
                    
                    if celda: # Si sí lo encontró...
                        row = celda.row
                        hoja_clientes.update_cell(row, 1, en)
                        hoja_clientes.update_cell(row, 2, ec)
                        hoja_clientes.update_cell(row, 3, ed)
                        hoja_clientes.update_cell(row, 4, et)
                        obtener_clientes.clear()
                        st.rerun()
                    else: # Si no lo encontró, mostramos un aviso en vez de chocar
                        st.error(f"Error: No se encontró a '{c_ed}' en Google Sheets. Revisa si tiene espacios al final del nombre.")
    with t_c3:
        if clientes_db:
            c_de = st.selectbox("Borrar Cliente", list(clientes_db.keys()), key="de_c")
            if st.button("🚨 Eliminar Definitivamente", type="primary"):
                hoja_clientes.delete_rows(hoja_clientes.find(c_de).row)
                obtener_clientes.clear(); st.rerun()

    st.divider()
    st.header("🛠️ Gestión de Servicios")
    s1, s2 = st.columns([1, 1])
    with s1: st.dataframe(pd.DataFrame(list(servicios_db.items()), columns=["Servicio", "Precio ($)"]), hide_index=True, use_container_width=True)
    with s2:
        ts1, ts2, ts3 = st.tabs(["➕", "✏️", "🗑️"])
        with ts1:
            with st.form("add_s"):
                sn = st.text_input("Servicio"); sp = st.number_input("Precio", min_value=0.0)
                if st.form_submit_button("Añadir"):
                    if sn: hoja_servicios.append_row([sn, sp]); obtener_servicios.clear(); st.rerun()
        with ts2:
            if servicios_db:
                s_ed = st.selectbox("Editar Servicio", list(servicios_db.keys()), key="ed_s")
                with st.form("edit_s"):
                    sen = st.text_input("Nombre", value=s_ed); sep = st.number_input("Precio", value=float(servicios_db[s_ed]))
                    if st.form_submit_button("Actualizar"):
                        row = hoja_servicios.find(s_ed).row
                        hoja_servicios.update_cell(row, 1, sen); hoja_servicios.update_cell(row, 2, sep)
                        obtener_servicios.clear(); st.rerun()
        with ts3:
            if servicios_db:
                s_de = st.selectbox("Borrar Servicio", list(servicios_db.keys()), key="de_s")
                if st.button("🗑️ Borrar", key="b_s"):
                    hoja_servicios.delete_rows(hoja_servicios.find(s_de).row)
                    obtener_servicios.clear(); st.rerun()
