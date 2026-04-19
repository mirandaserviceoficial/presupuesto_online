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
TELEFONO_PAPA = "(302) 584-2281"

# Intentar leer secretos de Streamlit Cloud (Seguridad para la versión online)
try:
    PASSWORD_APP_GMAIL = st.secrets["gmail_password"]
except:
    # PEGA AQUÍ TUS 16 DÍGITOS SÓLO PARA PRUEBAS LOCALES EN TU PC
    PASSWORD_APP_GMAIL = "yanwkulxewxpnccg"

# Manejo de rutas absolutas
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

# --- FUNCIONES DE BASE DE DATOS (CON BLINDAJE ANTI-BLOQUEOS) ---
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

# --- LÓGICA DE MEMORIA (SESSION STATE) ---
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
        st.session_state["input_correo"] = ""
        st.session_state["input_direccion"] = ""
        st.session_state["input_telefono"] = ""

def cb_precio(i):
    ds = st.session_state[f"desc_{i}"]
    if ds in servicios_db:
        st.session_state[f"precio_{i}"] = servicios_db[ds]
        if st.session_state[f"cant_{i}"] == 0: st.session_state[f"cant_{i}"] = 1

# --- INTERFAZ ---
st.title("🌿 MIRANDA SERVICE ERP")
tab1, tab2, tab3 = st.tabs(["📝 Facturar", "📊 Historial", "🗂️ Directorio"])

# ==========================================
# TAB 1: CREAR FACTURA
# ==========================================
with tab1:
    st.subheader("Datos del Cliente")
    st.selectbox("Selecciona o Nuevo", ["(Nuevo Cliente)"] + list(clientes_db.keys()), key="combo_cliente", on_change=cb_cliente)
    nom_cli = st.text_input("Nombre Completo") if st.session_state["combo_cliente"] == "(Nuevo Cliente)" else st.session_state["combo_cliente"]
    
    col_c1, col_c2 = st.columns(2)
    with col_c1: cor_cli = st.text_input("Correo", key="input_correo")
    with col_c2: tel_cli = st.text_input("Teléfono / Cell", key="input_telefono", help="Ej: (302) 123-4567")
    
    dir_cli = st.text_area("Service Address (Lugar del trabajo)", key="input_direccion", help="Ej: 123 Main St, Newark, DE")

    st.divider()
    st.subheader("Detalles del Servicio")
    rows = []
    subtotal = 0.0
    for i in range(5):
        col_s, col_c, col_p = st.columns([3, 1, 1])
        with col_s: d = st.selectbox(f"Servicio {i+1}", [""] + list(servicios_db.keys()), key=f"desc_{i}", on_change=cb_precio, args=(i,))
        with col_c: c = st.number_input("Cant.", min_value=0, step=1, key=f"cant_{i}")
        with col_p: p = st.number_input("Unit Price ($)", min_value=0.0, key=f"precio_{i}")
        rows.append((d, c, p))
        subtotal += (float(c) * p)

    col_t1, col_t2 = st.columns([2,1])
    with col_t2:
        desc_valor = st.number_input("Discount ($ opcional)", min_value=0.0, step=1.0)
        g_total = subtotal - desc_valor
        if g_total < 0: g_total = 0
        st.subheader(f"Total Due: ${g_total:,.2f}")
    
    with col_t1:
        st.write("### Payment Info")
        col_p1, col_p2 = st.columns(2)
        with col_p1: 
            zelle_on = st.checkbox("Show Zelle", value=True)
            cash_on = st.checkbox("Show Cash/Check", value=True)
        with col_p2:
            venmo_on = st.checkbox("Show Venmo", value=True)

    enviar_correo = st.checkbox("Enviar PDF automáticamente por correo", value=True)

    if st.button("🚀 Emitir Factura", type="primary", width="stretch"):
        if not nom_cli or not dir_cli or g_total == 0:
            st.warning("Completa Nombre, Dirección y al menos un servicio.")
        else:
            with st.spinner("Procesando factura..."):
                # --- Guardar datos del cliente ---
                if nom_cli not in clientes_db or clientes_db[nom_cli]['correo'] != cor_cli or clientes_db[nom_cli]['direccion'] != dir_cli or clientes_db[nom_cli]['telefono'] != tel_cli:
                    registros_cli = hoja_clientes.get_all_values()
                    encontrado = False
                    for idx, r in enumerate(registros_cli):
                        if idx > 0 and r[0] == nom_cli:
                            hoja_clientes.update_cell(idx+1, 2, cor_cli)
                            hoja_clientes.update_cell(idx+1, 3, dir_cli)
                            hoja_clientes.update_cell(idx+1, 4, tel_cli)
                            encontrado = True; break
                    if not encontrado:
                        hoja_clientes.append_row([nom_cli, cor_cli, dir_cli, tel_cli])
                    obtener_clientes.clear() 
                
                folio = f"FAC-{len(hoja_facturas.get_all_values()):04d}"
                f_emision = datetime.date.today()
                f_venc = f_emision + datetime.timedelta(days=5)
                
                # --- GENERACIÓN DE PDF PROFESIONAL ---
                pdf = FPDF(orientation='P', unit='mm', format='A4')
                pdf.add_page()
                
                if os.path.exists(PLANTILLA_IMG): 
                    pdf.image(PLANTILLA_IMG, x=0, y=0, w=210, h=297)
                else: 
                    st.error(f"⚠️ Plantilla no encontrada: {PLANTILLA_IMG}")
                
                blue = (0, 102, 204)
                
                # Encabezado Comercial
                pdf.set_font("Helvetica", 'B', 14)
                pdf.set_text_color(*blue)
                pdf.text(120, 25, "MIRANDA SERVICE LLC")
                
                pdf.set_font("Helvetica", '', 10)
                pdf.set_text_color(0, 0, 0)
                pdf.text(120, 30, DIRECCION_PAPA_1)
                pdf.text(120, 35, DIRECCION_PAPA_2)
                pdf.text(120, 40, f"Tel: {TELEFONO_PAPA}")
                pdf.text(120, 45, f"Email: {CORREO_PAPA}")
                
                # Billed To e Invoice (ALINEADOS A LA MISMA ALTURA Y=60)
                pdf.set_font("Helvetica", 'B', 11)
                pdf.set_text_color(*blue)
                pdf.text(15, 60, "BILLED TO:")
                pdf.text(120, 60, f"INVOICE #:   {folio}")
                
                # Datos Billed To
                pdf.set_text_color(0, 0, 0)
                pdf.set_font("Helvetica", 'B', 10)
                pdf.text(15, 66, nom_cli)
                pdf.set_font("Helvetica", '', 10)
                pdf.set_xy(14, 68)
                pdf.multi_cell(80, 5, f"{dir_cli}\nTel: {tel_cli}\nEmail: {cor_cli}", align='L')
                
                # Datos Invoice
                pdf.set_font("Helvetica", '', 10)
                pdf.text(120, 66, f"Issued Date: {f_emision.strftime('%m/%d/%Y')}")
                pdf.set_text_color(220, 20, 60) # Rojo
                pdf.text(120, 72, f"Due Date:     {f_venc.strftime('%m/%d/%Y')}")
                pdf.set_text_color(0, 0, 0)

                # Tabla dibujada automáticamente
                pdf.set_xy(10, 100)
                pdf.set_fill_color(*blue)
                pdf.set_text_color(255, 255, 255)
                pdf.set_font("Helvetica", 'B', 10)
                
                # Cabeceras
                pdf.cell(95, 8, "Description", 1, 0, 'C', True)
                pdf.cell(25, 8, "Quantity", 1, 0, 'C', True)
                pdf.cell(35, 8, "Unit Price", 1, 0, 'C', True)
                pdf.cell(35, 8, "Amount", 1, 1, 'C', True)
                
                # Filas
                pdf.set_text_color(0, 0, 0)
                pdf.set_font("Helvetica", '', 10)
                
                for d, c, p in rows:
                    if d and c > 0:
                        total_fila = float(c) * p
                        pdf.set_x(10)
                        pdf.cell(95, 8, f" {d}", 1, 0, 'L')
                        pdf.cell(25, 8, str(c), 1, 0, 'C')
                        pdf.cell(35, 8, f"${p:,.2f}", 1, 0, 'C')
                        pdf.cell(35, 8, f"${total_fila:,.2f}", 1, 1, 'C')

                # Totales dinámicos (Justo debajo de la tabla)
                ty = pdf.get_y() + 10
                pdf.set_font("Helvetica", 'B', 10)
                pdf.text(140, ty, "Subtotal:")
                pdf.text(175, ty, f"${subtotal:,.2f}")
                
                if desc_valor > 0:
                    pdf.set_text_color(220, 20, 60)
                    pdf.text(140, ty+7, "Discount:")
                    pdf.text(175, ty+7, f"-${desc_valor:,.2f}")
                    pdf.set_text_color(0, 0, 0)
                
                pdf.set_font("Helvetica", 'B', 13)
                pdf.set_text_color(*blue)
                pdf.text(140, ty+16, "TOTAL:")
                pdf.text(175, ty+16, f"${g_total:,.2f}")
                
                # Métodos de pago
                pdf.set_font("Helvetica", 'B', 11)
                pdf.text(15, ty, "PAYMENT OPTIONS:")
                pdf.set_text_color(0, 0, 0)
                pdf.set_font("Helvetica", '', 9)
                pm_y = ty + 6
                if zelle_on:
                    pdf.text(15, pm_y, "Zelle: MirandaServiceOficial@gmail.com")
                    pm_y += 5
                if venmo_on:
                    pdf.text(15, pm_y, "Venmo: @UsuarioDePapa") 
                    pm_y += 5
                if cash_on:
                    pdf.text(15, pm_y, "Check: Payable to Miranda Service / Cash Accepted")

                # Pie de página: Agradecimiento (Restaurado)
                pdf.set_text_color(100, 100, 100)
                pdf.set_font("Helvetica", '', 8)
                footer_text = "Thank you for choosing Miranda Service! Your landscaping, professionalized.\nFull payment is due within 5 days. Late fee of 5% may apply after Due Date."
                pdf.set_xy(15, 270)
                pdf.multi_cell(180, 4, footer_text, align='C')

                # Guardar y procesar datos
                fname = f"{folio}_{nom_cli.replace(' ','_')}.pdf"
                pdf.output(fname)
                
                hoja_facturas.append_row([folio, nom_cli, str(f_emision), str(f_venc), f"${g_total:,.2f}", "Pendiente", "Copia en Gmail"])
                obtener_facturas_records.clear() 
                
                # Enviar correo (Totalmente restaurado)
                if cor_cli and PASSWORD_APP_GMAIL != "yanwkulxewxpnccg" and enviar_correo:
                    try:
                        msg = EmailMessage()
                        msg['Subject'] = f'Invoice {folio} - Miranda Service LLC'
                        msg['From'] = CORREO_PAPA
                        msg['To'] = cor_cli
                        msg['Cc'] = CORREO_PAPA
                        msg.set_content(f"Hi {nom_cli},\n\nAttached is invoice {folio} from Miranda Service LLC for landscaping services.\n\nService Address: {dir_cli}\n\nTotal Due: ${g_total:,.2f}\n\nThank you for your business!\n\nRegards,\nMiranda Service\nTel: {TELEFONO_PAPA}")
                        
                        with open(fname, 'rb') as f: 
                            msg.add_attachment(f.read(), maintype='application', subtype='pdf', filename=fname)
                        
                        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as s:
                            s.login(CORREO_PAPA, PASSWORD_APP_GMAIL)
                            s.send_message(msg)
                    except Exception as email_err:
                        st.error(f"Factura generada, pero hubo un error enviando el correo: {email_err}")
                
                st.success(f"¡Factura {folio} emitida con éxito!")
                with open(fname, "rb") as f: 
                    st.download_button("⬇️ Descargar PDF", f, file_name=fname, type="primary", width="stretch")
                os.remove(fname)

# ==========================================
# TAB 2: HISTORIAL (RESTAURADO)
# ==========================================
with tab2:
    st.subheader("Control de Cobros")
    data_fac = obtener_facturas_records()
    if data_fac:
        df = pd.DataFrame(data_fac)
        if 'Ruta_PDF' in df.columns:
            df = df.drop(columns=['Ruta_PDF'])
            
        st.dataframe(df, hide_index=True, width="stretch")
        
        pendientes = df[df["Estado"] == "Pendiente"]["Folio"].tolist()
        if pendientes:
            st.divider()
            f_pago = st.selectbox("Registrar pago de la factura:", pendientes)
            if st.button("💰 Confirmar Pago", width="stretch"):
                cell = hoja_facturas.find(f_pago)
                hoja_facturas.update_cell(cell.row, 6, "Pagado")
                obtener_facturas_records.clear()
                st.success(f"Factura {f_pago} actualizada.")
                st.rerun()
    else: 
        st.info("No hay facturas registradas.")

# ==========================================
# TAB 3: DIRECTORIO COMPLETO (RESTAURADO)
# ==========================================
with tab3:
    # CLIENTES
    st.header("👥 Clientes")
    c1, c2 = st.columns([2, 1])
    with c1: 
        df_c = pd.DataFrame([{'Nombre': k, 'Correo': v['correo'], 'Teléfono': v['telefono']} for k, v in clientes_db.items()])
        st.dataframe(df_c, hide_index=True, width="stretch")
    with c2:
        with st.expander("➕ Añadir"):
            n_n = st.text_input("Nombre cliente")
            n_c = st.text_input("Correo cliente")
            n_d = st.text_input("Dirección")
            n_t = st.text_input("Teléfono")
            if st.button("Guardar Cliente"):
                hoja_clientes.append_row([n_n, n_c, n_d, n_t])
                obtener_clientes.clear(); st.rerun()
                
        with st.expander("✏️ Editar/Borrar"):
            if clientes_db:
                c_sel = st.selectbox("Elegir cliente", list(clientes_db.keys()))
                nn = st.text_input("Editar Nombre", value=c_sel)
                nc = st.text_input("Editar Correo", value=clientes_db[c_sel]['correo'])
                nd = st.text_input("Editar Dirección", value=clientes_db[c_sel]['direccion'])
                nt = st.text_input("Editar Teléfono", value=clientes_db[c_sel]['telefono'])
                if st.button("Actualizar Cliente"):
                    r = hoja_clientes.find(c_sel).row
                    hoja_clientes.update_cell(r, 1, nn)
                    hoja_clientes.update_cell(r, 2, nc)
                    hoja_clientes.update_cell(r, 3, nd)
                    hoja_clientes.update_cell(r, 4, nt)
                    obtener_clientes.clear(); st.rerun()
                if st.button("🗑️ Eliminar Cliente", type="secondary"):
                    hoja_clientes.delete_rows(hoja_clientes.find(c_sel).row)
                    obtener_clientes.clear(); st.rerun()

    st.divider()

    # SERVICIOS
    st.header("🛠️ Servicios")
    s1, s2 = st.columns([2, 1])
    with s1: 
        st.dataframe(pd.DataFrame(list(servicios_db.items()), columns=["Servicio", "Precio"]), hide_index=True, width="stretch")
    with s2:
        with st.expander("➕ Añadir"):
            s_n = st.text_input("Descripción servicio")
            s_p = st.number_input("Precio base", min_value=0.0)
            if st.button("Guardar Servicio"):
                hoja_servicios.append_row([s_n, s_p])
                obtener_servicios.clear(); st.rerun()
                
        with st.expander("✏️ Editar/Borrar"):
            if servicios_db:
                s_sel = st.selectbox("Elegir servicio", list(servicios_db.keys()))
                sn = st.text_input("Editar Descripción", value=s_sel)
                sp = st.number_input("Editar Precio", value=servicios_db[s_sel])
                if st.button("Actualizar Servicio"):
                    r = hoja_servicios.find(s_sel).row
                    hoja_servicios.update_cell(r, 1, sn)
                    hoja_servicios.update_cell(r, 2, sp)
                    obtener_servicios.clear(); st.rerun()
                if st.button("🗑️ Eliminar Servicio"):
                    hoja_servicios.delete_rows(hoja_servicios.find(s_sel).row)
                    obtener_servicios.clear(); st.rerun()
