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
DIRECCION_PAPA = "190 Shannon Blvd, Middletown, DE 19709"
TELEFONO_PAPA = "(302) 584-2281"

# Intentar leer secretos de Streamlit Cloud
try:
    PASSWORD_APP_GMAIL = st.secrets["gmail_password"]
except:
    PASSWORD_APP_GMAIL = "AQUI_TU_CONTRASENA_DE_APLICACION"

# Manejo de rutas absolutas
DIRECTORIO_ACTUAL = os.path.dirname(os.path.abspath(__file__))
PLANTILLA_IMG = os.path.join(DIRECTORIO_ACTUAL, "plantilla_presupuesto.png")

# --- CONEXIÓN A GOOGLE SHEETS ---
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
            return {str(f.get('Nombre','')).strip(): str(f.get('Correo','')).strip() for f in registros if f.get('Nombre')}
        except Exception:
            time.sleep(2)
    return {}

@st.cache_data(ttl=600)
def obtener_servicios():
    for intento in range(3):
        try:
            registros = hoja_servicios.get_all_records()
            return {str(f.get('Servicio','')).strip(): float(f.get('Precio',0)) for f in registros if f.get('Servicio')}
        except Exception:
            time.sleep(2)
    return {}

@st.cache_data(ttl=600)
def obtener_facturas_records():
    for intento in range(3):
        try:
            return hoja_facturas.get_all_records()
        except Exception:
            time.sleep(2)
    return []

# --- LÓGICA DE AUTOCOMPLETADO Y MEMORIA ---
clientes_db = obtener_clientes()
servicios_db = obtener_servicios()

if "input_correo" not in st.session_state: st.session_state["input_correo"] = ""
for i in range(5):
    if f"precio_{i}" not in st.session_state: st.session_state[f"precio_{i}"] = 0.0
    if f"cant_{i}" not in st.session_state: st.session_state[f"cant_{i}"] = 0

def cb_cliente():
    sel = st.session_state["combo_cliente"]
    st.session_state["input_correo"] = clientes_db.get(sel, "") if sel != "(Nuevo Cliente)" else ""

def cb_precio(i):
    ds = st.session_state[f"desc_{i}"]
    if ds in servicios_db:
        st.session_state[f"precio_{i}"] = servicios_db[ds]
        if st.session_state[f"cant_{i}"] == 0: st.session_state[f"cant_{i}"] = 1

# --- INTERFAZ ---
st.title("🌿 MIRANDA SERVICE ERP")
tab1, tab2, tab3 = st.tabs(["📝 Facturar", "📊 Historial", "🗂️ Directorio"])

# TAB 1: CREAR FACTURA
with tab1:
    st.selectbox("Cliente", ["(Nuevo Cliente)"] + list(clientes_db.keys()), key="combo_cliente", on_change=cb_cliente)
    nom_cli = st.text_input("Nombre") if st.session_state["combo_cliente"] == "(Nuevo Cliente)" else st.session_state["combo_cliente"]
    cor_cli = st.text_input("Correo", key="input_correo")
    
    st.divider()
    rows = []
    g_total = 0.0
    for i in range(5):
        col_s, col_c, col_p = st.columns([3, 1, 1])
        with col_s: d = st.selectbox(f"Servicio {i+1}", [""] + list(servicios_db.keys()), key=f"desc_{i}", on_change=cb_precio, args=(i,))
        with col_c: c = st.number_input("Cant.", min_value=0, step=1, key=f"cant_{i}")
        with col_p: p = st.number_input("Precio ($)", min_value=0.0, key=f"precio_{i}")
        rows.append((d, c, p))
        g_total += (float(c) * p)

    st.subheader(f"Total: ${g_total:,.2f}")
    enviar_correo = st.checkbox("Enviar PDF por Correo automáticamente", value=True)

    if st.button("🚀 Emitir y Enviar", type="primary", use_container_width=True):
        if not nom_cli or g_total == 0:
            st.warning("Datos incompletos. Ingresa un cliente y al menos un servicio.")
        else:
            with st.spinner("Generando factura..."):
                if nom_cli not in clientes_db: 
                    hoja_clientes.append_row([nom_cli, cor_cli])
                    obtener_clientes.clear() 
                
                folio = f"FAC-{len(hoja_facturas.get_all_values()):04d}"
                f_emision = datetime.date.today()
                f_venc = f_emision + datetime.timedelta(days=5)
                
                pdf = FPDF()
                pdf.add_page()
                if os.path.exists(PLANTILLA_IMG): pdf.image(PLANTILLA_IMG, x=0, y=0, w=210)
                
                pdf.set_font("Arial", 'B', 10); pdf.set_text_color(100,100,100)
                pdf.text(120, 20, "MIRANDA SERVICE"); pdf.text(120, 25, DIRECCION_PAPA)
                pdf.text(120, 30, f"Tel: {TELEFONO_PAPA}"); pdf.text(120, 35, CORREO_PAPA)
                
                pdf.set_font("Arial", 'B', 12); pdf.set_text_color(0,0,0)
                pdf.text(120, 50, f"Invoice #: {folio}")
                pdf.set_font("Arial", '', 10)
                pdf.text(120, 55, f"Issued: {f_emision.strftime('%m/%d/%Y')}")
                pdf.set_text_color(200,0,0); pdf.text(120, 60, f"Due Date: {f_venc.strftime('%m/%d/%Y')}")
                
                pdf.set_font("Arial", '', 12); pdf.set_text_color(0,0,0)
                pdf.text(135, 76, nom_cli); pdf.set_font("Arial", '', 10); pdf.text(135, 81, cor_cli)
                
                pdf.set_font("Arial", '', 11); ly = 100
                for d, c, p in rows:
                    if d and c > 0:
                        pdf.text(20, ly, d); pdf.text(128, ly, str(c))
                        pdf.text(150, ly, f"${p:,.2f}"); pdf.text(175, ly, f"${(c*p):,.2f}")
                        ly += 10
                
                pdf.set_font("Arial", 'B', 12); pdf.text(170, 159, f"${g_total:,.2f}"); pdf.text(170, 178, f"${g_total:,.2f}")
                
                fname = f"{folio}_{nom_cli.replace(' ','_')}.pdf"
                pdf.output(fname)
                
                # Guardar en Sheets sin intentar subir a Drive
                hoja_facturas.append_row([folio, nom_cli, str(f_emision), str(f_venc), f"${g_total:,.2f}", "Pendiente", "Copia en Gmail"])
                obtener_facturas_records.clear() 
                
                # Envío de Correo
                if cor_cli and PASSWORD_APP_GMAIL != "AQUI_TU_CONTRASENA_DE_APLICACION" and enviar_correo:
                    try:
                        msg = EmailMessage()
                        msg['Subject'] = f'Invoice {folio} - Miranda Service'
                        msg['From'] = CORREO_PAPA; msg['To'] = cor_cli; msg['Cc'] = CORREO_PAPA
                        msg.set_content(f"Hi {nom_cli},\n\nAttached is invoice {folio}.\n\nThanks,\nMiranda Service")
                        with open(fname, 'rb') as f: msg.add_attachment(f.read(), maintype='application', subtype='pdf', filename=fname)
                        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as s:
                            s.login(CORREO_PAPA, PASSWORD_APP_GMAIL); s.send_message(msg)
                    except Exception as email_err:
                        st.error(f"Factura generada, pero hubo un error enviando el correo: {email_err}")
                
                st.success(f"¡Factura {folio} emitida con éxito!")
                with open(fname, "rb") as f: 
                    st.download_button("⬇️ Descargar PDF ahora", f, file_name=fname, type="primary")
                os.remove(fname)

# TAB 2: HISTORIAL
with tab2:
    st.subheader("Control de Cobros")
    data_fac = obtener_facturas_records()
    if data_fac:
        df = pd.DataFrame(data_fac)
        # Ocultamos la columna de Ruta_PDF ya que el respaldo está en el correo
        if 'Ruta_PDF' in df.columns:
            df = df.drop(columns=['Ruta_PDF'])
            
        st.dataframe(df, hide_index=True, use_container_width=True)
        
        pendientes = df[df["Estado"] == "Pendiente"]["Folio"].tolist()
        if pendientes:
            st.divider()
            f_pago = st.selectbox("Registrar pago de la factura:", pendientes)
            if st.button("💰 Confirmar Pago", use_container_width=True):
                cell = hoja_facturas.find(f_pago)
                hoja_facturas.update_cell(cell.row, 6, "Pagado")
                obtener_facturas_records.clear()
                st.success(f"Factura {f_pago} actualizada.")
                st.rerun()
    else: 
        st.info("No hay facturas registradas.")

# TAB 3: DIRECTORIO
with tab3:
    st.header("👥 Clientes")
    c1, c2 = st.columns([2, 1])
    with c1: 
        st.dataframe(pd.DataFrame(list(clientes_db.items()), columns=["Nombre", "Correo"]), hide_index=True, use_container_width=True)
    with c2:
        with st.expander("➕ Añadir"):
            n_n = st.text_input("Nombre cliente")
            n_c = st.text_input("Correo cliente")
            if st.button("Guardar Nuevo Cliente"):
                hoja_clientes.append_row([n_n, n_c])
                obtener_clientes.clear(); st.rerun()
        with st.expander("✏️ Gestionar"):
            if clientes_db:
                c_sel = st.selectbox("Elegir cliente", list(clientes_db.keys()))
                nn = st.text_input("Editar Nombre", value=c_sel)
                nc = st.text_input("Editar Correo", value=clientes_db[c_sel])
                if st.button("Actualizar Cliente"):
                    r = hoja_clientes.find(c_sel).row
                    hoja_clientes.update_cell(r, 1, nn); hoja_clientes.update_cell(r, 2, nc)
                    obtener_clientes.clear(); st.rerun()
                if st.button("🗑️ Eliminar Cliente", type="secondary"):
                    hoja_clientes.delete_rows(hoja_clientes.find(c_sel).row)
                    obtener_clientes.clear(); st.rerun()

    st.divider()

    st.header("🛠️ Servicios")
    s1, s2 = st.columns([2, 1])
    with s1: 
        st.dataframe(pd.DataFrame(list(servicios_db.items()), columns=["Servicio", "Precio"]), hide_index=True, use_container_width=True)
    with s2:
        with st.expander("➕ Añadir"):
            s_n = st.text_input("Descripción servicio")
            s_p = st.number_input("Precio base", min_value=0.0)
            if st.button("Guardar Nuevo Servicio"):
                hoja_servicios.append_row([s_n, s_p])
                obtener_servicios.clear(); st.rerun()
        with st.expander("✏️ Gestionar"):
            if servicios_db:
                s_sel = st.selectbox("Elegir servicio", list(servicios_db.keys()))
                sn = st.text_input("Editar Descripción", value=s_sel)
                sp = st.number_input("Editar Precio", value=servicios_db[s_sel])
                if st.button("Actualizar Servicio"):
                    r = hoja_servicios.find(s_sel).row
                    hoja_servicios.update_cell(r, 1, sn); hoja_servicios.update_cell(r, 2, sp)
                    obtener_servicios.clear(); st.rerun()
                if st.button("🗑️ Eliminar Servicio"):
                    hoja_servicios.delete_rows(hoja_servicios.find(s_sel).row)
                    obtener_servicios.clear(); st.rerun()
