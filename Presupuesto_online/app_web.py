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
st.set_page_config(page_title="Miranda Service ERP", page_icon="🌿", layout="centered")

# --- DATOS DE CONFIGURACIÓN ---
CORREO_PAPA = "MirandaServiceOficial@gmail.com"
DIRECCION_PAPA_1 = "980 Dixie Line Rd"
DIRECCION_PAPA_2 = "Newark, DE 19713"
TELEFONO_PAPA = "(302) 602-9250"

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

clientes_db = obtener_clientes()
servicios_db = obtener_servicios()

# --- LÓGICA DE MEMORIA ---
if "input_correo" not in st.session_state: st.session_state["input_correo"] = ""
if "input_direccion" not in st.session_state: st.session_state["input_direccion"] = ""
if "input_telefono" not in st.session_state: st.session_state["input_telefono"] = ""
for i in range(5):
    if f"precio_{i}" not in st.session_state: st.session_state[f"precio_{i}"] = 0.0
    if f"cant_{i}" not in st.session_state: st.session_state[f"cant_{i}"] = 0

def cb_cliente():
    sel = st.session_state["combo_cliente"]
    if sel != "(Nuevo Cliente)" and sel in clientes_db:
        data = clientes_db[sel]
        st.session_state["input_correo"] = data['correo']
        st.session_state["input_direccion"] = data['direccion']
        st.session_state["input_telefono"] = data['telefono']
    else:
        st.session_state["input_correo"] = ""; st.session_state["input_direccion"] = ""; st.session_state["input_telefono"] = ""

def cb_precio(i):
    ds = st.session_state[f"desc_{i}"]
    if ds in servicios_db:
        st.session_state[f"precio_{i}"] = servicios_db[ds]
        if st.session_state[f"cant_{i}"] == 0: st.session_state[f"cant_{i}"] = 1

# --- INTERFAZ ---
st.title("🌿 MIRANDA SERVICE ERP")
tab1, tab2, tab3 = st.tabs(["📝 Facturar", "📊 Historial", "🗂️ Directorio"])

with tab1:
    st.subheader("Datos del Cliente")
    st.selectbox("Seleccionar Cliente", ["(Nuevo Cliente)"] + list(clientes_db.keys()), key="combo_cliente", on_change=cb_cliente)
    nom_cli = st.text_input("Nombre") if st.session_state["combo_cliente"] == "(Nuevo Cliente)" else st.session_state["combo_cliente"]
    
    col_c1, col_c2 = st.columns(2)
    with col_c1: cor_cli = st.text_input("Email", key="input_correo")
    with col_c2: tel_cli = st.text_input("Phone", key="input_telefono")
    dir_cli = st.text_area("Service Address", key="input_direccion")

    st.divider()
    st.subheader("Detalles del Servicio")
    rows = []
    subtotal = 0.0
    for i in range(5):
        cs, cc, cp = st.columns([3, 1, 1])
        with cs: d = st.selectbox(f"Service {i+1}", [""] + list(servicios_db.keys()), key=f"desc_{i}", on_change=cb_precio, args=(i,))
        with cc: c = st.number_input("Qty", min_value=0, step=1, key=f"cant_{i}")
        with cp: p = st.number_input("Price ($)", min_value=0.0, key=f"precio_{i}")
        rows.append((d, c, p))
        subtotal += (float(c) * p)

    col_t1, col_t2 = st.columns([2,1])
    with col_t2:
        desc_val = st.number_input("Discount ($)", min_value=0.0)
        total_due = subtotal - desc_val
        st.subheader(f"Total Due: ${total_due:,.2f}")
    
    with col_t1:
        st.write("### Payment Information")
        zelle_info = st.text_input("Zelle Email/Phone", value="MirandaServiceOficial@gmail.com")
        venmo_info = st.text_input("Venmo Username", value="@MirandaService")
        cash_check = st.checkbox("Accept Cash/Check", value=True)

    if st.button("🚀 Emitir Factura", type="primary", width="stretch"):
        if not nom_cli or not dir_cli or total_due == 0:
            st.warning("Faltan datos obligatorios.")
        else:
            with st.spinner("Creando PDF..."):
                if nom_cli not in clientes_db:
                    hoja_clientes.append_row([nom_cli, cor_cli, dir_cli, tel_cli])
                    obtener_clientes.clear()
                
                folio = f"FAC-{len(hoja_facturas.get_all_values()):04d}"
                f_emision = datetime.date.today()
                f_venc = f_emision + datetime.timedelta(days=5)
                
                # --- GENERACIÓN DE PDF ---
                pdf = FPDF()
                pdf.add_page()
                if os.path.exists(PLANTILLA_IMG):
                    pdf.image(PLANTILLA_IMG, x=0, y=0, w=210, h=297)
                
                blue = (0, 102, 204)
                
                # Encabezado
                pdf.set_font("Helvetica", 'B', 14); pdf.set_text_color(*blue)
                pdf.text(120, 25, "MIRANDA SERVICE LLC")
                pdf.set_font("Helvetica", '', 10); pdf.set_text_color(0,0,0)
                pdf.text(120, 30, DIRECCION_PAPA_1); pdf.text(120, 35, DIRECCION_PAPA_2)
                pdf.text(120, 40, f"Tel: {TELEFONO_PAPA}")

                # Billed To e Invoice
                pdf.set_font("Helvetica", 'B', 11); pdf.set_text_color(*blue)
                pdf.text(15, 60, "BILLED TO:")
                pdf.text(120, 60, f"INVOICE #: {folio}")
                pdf.set_font("Helvetica", 'B', 10); pdf.set_text_color(0,0,0)
                pdf.text(15, 65, nom_cli)
                pdf.set_font("Helvetica", '', 9)
                pdf.set_xy(15, 67); pdf.multi_cell(80, 4, f"{dir_cli}\nTel: {tel_cli}")

                pdf.set_font("Helvetica", '', 10)
                pdf.text(120, 65, f"Issued: {f_emision.strftime('%m/%d/%Y')}")
                pdf.set_text_color(200, 0, 0); pdf.text(120, 70, f"Due Date: {f_venc.strftime('%m/%d/%Y')}")
                pdf.set_text_color(0, 0, 0)

                # Tabla de Productos
                pdf.set_fill_color(*blue); pdf.set_text_color(255,255,255)
                pdf.set_xy(10, 90)
                pdf.cell(95, 8, "Description", 1, 0, 'C', True)
                pdf.cell(25, 8, "Qty", 1, 0, 'C', True)
                pdf.cell(35, 8, "Unit Price", 1, 0, 'C', True)
                pdf.cell(35, 8, "Amount", 1, 1, 'C', True)

                pdf.set_text_color(0,0,0); pdf.set_font("Helvetica", '', 10)
                for d, c, p in rows:
                    if d and c > 0:
                        total_f = float(c) * p
                        pdf.set_x(10)
                        pdf.cell(95, 7, f" {d}", 1)
                        pdf.cell(25, 7, str(c), 1, 0, 'C')
                        pdf.cell(35, 7, f"${p:,.2f}", 1, 0, 'C')
                        pdf.cell(35, 7, f"${total_f:,.2f}", 1, 1, 'C')

                # Totales y Pago (SUBIDOS DE POSICIÓN)
                ty = pdf.get_y() + 8
                pdf.set_font("Helvetica", 'B', 10)
                pdf.text(140, ty, "Subtotal:")
                pdf.text(175, ty, f"${subtotal:,.2f}")
                pdf.text(140, ty+7, "Discount:")
                pdf.set_text_color(200,0,0); pdf.text(175, ty+7, f"-${desc_val:,.2f}")
                
                pdf.set_text_color(*blue); pdf.set_font("Helvetica", 'B', 13)
                pdf.text(140, ty+16, "TOTAL:")
                pdf.text(175, ty+16, f"${total_due:,.2f}")

                # Métodos de Pago
                pdf.set_font("Helvetica", 'B', 11); pdf.text(15, ty, "PAYMENT OPTIONS:")
                pdf.set_text_color(0, 0, 0); pdf.set_font("Helvetica", '', 9)
                pm_y = ty + 6
                if zelle_info:
                    pdf.text(15, pm_y, f"Zelle: {zelle_info}"); pm_y += 5
                if venmo_info:
                    pdf.text(15, pm_y, f"Venmo: {venmo_info}"); pm_y += 5
                if cash_check:
                    pdf.text(15, pm_y, "Check: Payable to Miranda Service / Cash Accepted")

                # Pie de página (SUBIDO A Y=255 PARA EVITAR 2DA PÁGINA)
                pdf.set_text_color(100, 100, 100); pdf.set_font("Helvetica", '', 8)
                footer_text = "Thank you for choosing Miranda Service! Your landscaping, professionalized.\nFull payment is due within 5 days. Late fee of 5% may apply after Due Date."
                pdf.set_xy(15, 255)
                pdf.multi_cell(180, 4, footer_text, align='C')

                # Guardar y Enviar
                fname = f"{folio}_{nom_cli.replace(' ','_')}.pdf"
                pdf.output(fname)
                hoja_facturas.append_row([folio, nom_cli, str(f_emision), str(f_venc), f"${total_due:,.2f}", "Pendiente", "Gmail Copy"])
                obtener_facturas_records.clear()
                
                if cor_cli and PASSWORD_APP_GMAIL != "yanwkulxewxpnccg":
                    try:
                        msg = EmailMessage()
                        msg['Subject'] = f'Invoice {folio} - Miranda Service LLC'
                        msg['From'] = CORREO_PAPA; msg['To'] = cor_cli; msg['Cc'] = CORREO_PAPA
                        msg.set_content(f"Hi {nom_cli},\n\nAttached is invoice {folio}.\nTotal Due: ${total_due:,.2f}\n\nThank you!")
                        with open(fname, 'rb') as f: msg.add_attachment(f.read(), maintype='application', subtype='pdf', filename=fname)
                        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as s:
                            s.login(CORREO_PAPA, PASSWORD_APP_GMAIL); s.send_message(msg)
                    except Exception as e: st.error(f"Error correo: {e}")

                st.success(f"Factura {folio} generada.")
                with open(fname, "rb") as f: st.download_button("📥 Descargar PDF", f, file_name=fname, type="primary", width="stretch")
                os.remove(fname)

# --- Pestañas 2 y 3 (Gestión Actualizada) ---
with tab2:
    st.subheader("Historial de Facturas")
    data = obtener_facturas_records()
    if data:
        df = pd.DataFrame(data)
        if 'Ruta_PDF' in df.columns: 
            df = df.drop(columns=['Ruta_PDF'])
        st.dataframe(df, hide_index=True, use_container_width=True)
        
        st.divider()
        st.write("### Gestión de Facturas")
        c_pago, c_rev, c_borrar = st.columns(3)
        
        pendientes = df[df["Estado"] == "Pendiente"]["Folio"].tolist()
        pagadas = df[df["Estado"] == "Pagado"]["Folio"].tolist()
        todas = df["Folio"].tolist()
        
        with c_pago:
            if pendientes:
                f_pago = st.selectbox("Marcar como Pagada:", pendientes, key="sb_pago")
                if st.button("💰 Confirmar Pago", use_container_width=True):
                    cell = hoja_facturas.find(f_pago)
                    hoja_facturas.update_cell(cell.row, 6, "Pagado")
                    obtener_facturas_records.clear()
                    st.rerun()
                    
        with c_rev:
            if pagadas:
                f_rev = st.selectbox("Revertir a Pendiente:", pagadas, key="sb_rev")
                if st.button("⏪ Quitar 'Pagado'", use_container_width=True):
                    cell = hoja_facturas.find(f_rev)
                    hoja_facturas.update_cell(cell.row, 6, "Pendiente")
                    obtener_facturas_records.clear()
                    st.rerun()
                    
        with c_borrar:
            if todas:
                f_del = st.selectbox("Eliminar Factura:", todas, key="sb_del_fac")
                if st.button("🗑️ Borrar Factura", type="primary", use_container_width=True):
                    cell = hoja_facturas.find(f_del)
                    hoja_facturas.delete_rows(cell.row)
                    obtener_facturas_records.clear()
                    st.rerun()
    else: 
        st.info("Sin registros de facturas.")

with tab3:
    st.header("👥 Gestión de Clientes")
    # Mostrar tabla de clientes más completa
    df_c = pd.DataFrame([{'Nombre': k, 'Correo': v['correo'], 'Teléfono': v['telefono'], 'Dirección': v['direccion']} for k, v in clientes_db.items()])
    st.dataframe(df_c, hide_index=True, use_container_width=True)
    
    t_c_add, t_c_edit, t_c_del = st.tabs(["➕ Añadir", "✏️ Editar", "🗑️ Borrar"])
    
    with t_c_add:
        with st.form("form_add_cli"):
            n_nom = st.text_input("Nombre del Cliente")
            n_cor = st.text_input("Correo")
            n_tel = st.text_input("Teléfono")
            n_dir = st.text_area("Dirección")
            if st.form_submit_button("Guardar Nuevo Cliente"):
                if n_nom:
                    hoja_clientes.append_row([n_nom, n_cor, n_dir, n_tel])
                    obtener_clientes.clear()
                    st.rerun()
                else:
                    st.warning("El nombre es obligatorio.")
                    
    with t_c_edit:
        if clientes_db:
            e_sel = st.selectbox("Seleccionar Cliente a Editar", list(clientes_db.keys()), key="sb_edit_cli")
            datos_actuales = clientes_db[e_sel]
            with st.form("form_edit_cli"):
                e_nom = st.text_input("Nombre", value=e_sel)
                e_cor = st.text_input("Correo", value=datos_actuales['correo'])
                e_tel = st.text_input("Teléfono", value=datos_actuales['telefono'])
                e_dir = st.text_area("Dirección", value=datos_actuales['direccion'])
                if st.form_submit_button("Actualizar Cliente"):
                    cell = hoja_clientes.find(e_sel)
                    hoja_clientes.update_cell(cell.row, 1, e_nom)
                    hoja_clientes.update_cell(cell.row, 2, e_cor)
                    hoja_clientes.update_cell(cell.row, 3, e_dir)
                    hoja_clientes.update_cell(cell.row, 4, e_tel)
                    obtener_clientes.clear()
                    st.rerun()

    with t_c_del:
        if clientes_db:
            d_sel = st.selectbox("Seleccionar Cliente a Borrar", list(clientes_db.keys()), key="sb_del_cli")
            if st.button("🚨 Eliminar Cliente Definitivamente", type="primary"):
                cell = hoja_clientes.find(d_sel)
                hoja_clientes.delete_rows(cell.row)
                obtener_clientes.clear()
                st.rerun()

    st.divider()
    
    st.header("🛠️ Gestión de Servicios")
    s1, s2 = st.columns([1, 1])
    with s1: 
        st.dataframe(pd.DataFrame(list(servicios_db.items()), columns=["Servicio", "Precio ($)"]), hide_index=True, use_container_width=True)
        
    with s2:
        t_s_add, t_s_edit, t_s_del = st.tabs(["➕ Añadir", "✏️ Editar", "🗑️ Borrar"])
        
        with t_s_add:
            with st.form("form_add_serv"):
                sn = st.text_input("Nuevo Servicio")
                sp = st.number_input("Precio ($)", min_value=0.0)
                if st.form_submit_button("Guardar Servicio"):
                    if sn:
                        hoja_servicios.append_row([sn, sp])
                        obtener_servicios.clear()
                        st.rerun()
                        
        with t_s_edit:
            if servicios_db:
                es_sel = st.selectbox("Seleccionar Servicio a Editar", list(servicios_db.keys()), key="sb_edit_serv")
                with st.form("form_edit_serv"):
                    es_nom = st.text_input("Servicio", value=es_sel)
                    es_pre = st.number_input("Precio ($)", min_value=0.0, value=float(servicios_db[es_sel]))
                    if st.form_submit_button("Actualizar Servicio"):
                        cell = hoja_servicios.find(es_sel)
                        hoja_servicios.update_cell(cell.row, 1, es_nom)
                        hoja_servicios.update_cell(cell.row, 2, es_pre)
                        obtener_servicios.clear()
                        st.rerun()
                        
        with t_s_del:
            if servicios_db:
                ds_sel = st.selectbox("Seleccionar Servicio a Borrar", list(servicios_db.keys()), key="sb_del_serv")
                if st.button("🚨 Eliminar Servicio", type="primary", key="btn_del_serv"):
                    cell = hoja_servicios.find(ds_sel)
                    hoja_servicios.delete_rows(cell.row)
                    obtener_servicios.clear()
                    st.rerun()
