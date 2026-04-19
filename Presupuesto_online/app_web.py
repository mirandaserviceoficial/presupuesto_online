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
DIRECCION_PAPA_1 = "980 Dixie Line Rd"  # <-- TU NUEVA DIRECCIÓN COMERCIAL
DIRECCION_PAPA_2 = "Newark, DE 19713"
TELEFONO_PAPA = "(302) 584-2281"

# Intentar leer secretos de Streamlit Cloud (Seguridad para la versión online)
try:
    PASSWORD_APP_GMAIL = st.secrets["gmail_password"]
except:
    # LOCALMENTE, PEGA AQUÍ TUS 16 DÍGITOS DE GMAIL
    PASSWORD_APP_GMAIL = "yanwkulxewxpnccg" 

# Manejo de rutas absolutas (Súper importante para la nube)
DIRECTORIO_ACTUAL = os.path.dirname(os.path.abspath(__file__))
# NOMBRE DE TU NUEVA PLANTILLA
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

# TAB 1: CREAR FACTURA
with tab1:
    st.subheader("Datos del Cliente")
    st.selectbox("Selecciona o Nuevo", ["(Nuevo Cliente)"] + list(clientes_db.keys()), key="combo_cliente", on_change=cb_cliente)
    nom_cli = st.text_input("Nombre Completo") if st.session_state["combo_cliente"] == "(Nuevo Cliente)" else st.session_state["combo_cliente"]
    
    col_c1, col_c2 = st.columns(2)
    with col_c1: cor_cli = st.text_input("Correo", key="input_correo")
    with col_c2: tel_cli = st.text_input("Teléfono / Cell", key="input_telefono", help="Ej: (302) 123-4567")
    
    # NUEVO DATO: Dirección del Servicio
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

    enviar_correo = st.checkbox("Enviar PDF automáticamente", value=True)

    if st.button("🚀 Emitir Factura", type="primary", width="stretch"):
        if not nom_cli or not dir_cli or g_total == 0:
            st.warning("Completa Nombre, Dirección y al menos un servicio.")
        else:
            with st.spinner("Procesando factura..."):
                # Actualizar Clientes DB con los 4 datos
                if nom_cli not in clientes_db or clientes_db[nom_cli]['correo'] != cor_cli or clientes_db[nom_cli]['direccion'] != dir_cli or clientes_db[nom_cli]['telefono'] != tel_cli:
                    registros_cli = hoja_clientes.get_all_values()
                    encontrado = False
                    for idx, r in enumerate(registros_cli):
                        if idx > 0 and r[0] == nom_cli:
                            # Actualiza columnas C y D si ya existe
                            hoja_clientes.update_cell(idx+1, 2, cor_cli)
                            hoja_clientes.update_cell(idx+1, 3, dir_cli)
                            hoja_clientes.update_cell(idx+1, 4, tel_cli)
                            encontrado = True; break
                    if not encontrado:
                        # Si es nuevo, añade las 4 columnas
                        hoja_clientes.append_row([nom_cli, cor_cli, dir_cli, tel_cli])
                    obtener_clientes.clear() 
                
                # Folio y Fechas
                folio = f"FAC-{len(hoja_facturas.get_all_values()):04d}"
                f_emision = datetime.date.today()
                f_venc = f_emision + datetime.timedelta(days=5)
                
                # --- GENERACIÓN DE PDF PROFESIONAL CON FPDF ---
                # Usamos Helvetica (estándar) para evitar problemas de fuentes
                pdf = FPDF(orientation='P', unit='mm', format='A4')
                pdf.add_page()
                
                # 1. IMAGEN DE PLANTILLA DE FONDO (Full Page)
                if os.path.exists(PLANTILLA_IMG): 
                    pdf.image(PLANTILLA_IMG, x=0, y=0, w=210, h=297)
                else: st.error(f"⚠️ Plantilla no encontrada: {PLANTILLA_IMG}")
                
                # Definir color AZUL profesional que combina con la plantilla (R:0, G:102, B:204)
                blue = (0, 102, 204)
                
                # 2. ENCABEZADO: TUS DATOS COMERCIALES (Arriba a la derecha)
                pdf.set_font("Helvetica", 'B', 14)
                pdf.set_text_color(*blue)
                pdf.text(120, 25, "MIRANDA SERVICE LLC")
                
                pdf.set_font("Helvetica", '', 10)
                pdf.set_text_color(0, 0, 0) # Texto negro normal
                pdf.text(120, 30, DIRECCION_PAPA_1)
                pdf.text(120, 35, DIRECCION_PAPA_2)
                pdf.text(120, 40, f"Tel: {TELEFONO_PAPA}")
                pdf.text(120, 45, f"Email: {CORREO_PAPA}")
                
                # 3. DATOS DE LA FACTURA (Debajo de tus datos)
                pdf.set_font("Helvetica", 'B', 13)
                pdf.text(120, 60, f"Invoice #:   {folio}")
                
                pdf.set_font("Helvetica", '', 10)
                pdf.text(120, 65, f"Issued Date: {f_emision.strftime('%m/%d/%Y')}")
                # Fecha de vencimiento en ROJO para urgencia
                pdf.set_text_color(220, 20, 60) # Crimson Red
                pdf.text(120, 70, f"Due Date:     {f_venc.strftime('%m/%d/%Y')}")
                pdf.set_text_color(0, 0, 0) # Volver a negro

                # 4. DATOS DEL CLIENTE (Dentro del recuadro blanco de arriba)
                # Título del recuadro (x=110 aproxima al inicio de la cajita)
                pdf.set_font("Helvetica", 'B', 12)
                # El título "Datos del Cliente" ya viene impreso en azul en tu plantilla, no lo escribimos
                
                # Datos dentro de la cajita (coordenadas x=112, y=95)
                pdf.set_font("Helvetica", 'B', 11)
                pdf.text(112, 100, f"BILLED TO:")
                
                # Fuente normal para los datos
                pdf.set_font("Helvetica", '', 10)
                pdf.text(112, 105, nom_cli)
                
                # Manejo de múltiples líneas para la dirección si es muy larga
                pdf.set_xy(112, 107)
                # multi_cell dibuja dentro de un recuadro de x=90mm de ancho
                pdf.multi_cell(90, 4, dir_cli, align='L') 
                
                # Obtenemos la nueva posición Y después de MultiCell
                y_after_dir = pdf.get_y()
                pdf.text(112, y_after_dir + 2, f"Tel: {tel_cli}")
                pdf.text(112, y_after_dir + 6, f"Email: {cor_cli}")

                # 5. TABLA DE SERVICIOS (Coordenadas y=130 para iniciar las filas)
                # Los encabezados (Description, Quantity, Unit Price, Amount) ya vienen impresos en azul en tu plantilla
                
                pdf.set_font("Helvetica", '', 10)
                ly = 140 # Coordenada Y de inicio de la primera fila de datos
                
                for d, c, p in rows:
                    if d and c > 0:
                        total_fila = float(c) * p
                        
                        # Columna Description (x=15)
                        pdf.text(15, ly, d)
                        # Columna Quantity (x=120) - Centrado manual aproxiado
                        pdf.text(125, ly, str(c))
                        # Columna Unit Price (x=150)
                        pdf.text(150, ly, f"${p:,.2f}")
                        # Columna Amount (x=175)
                        pdf.text(175, ly, f"${total_fila:,.2f}")
                        ly += 8 # Espacio entre filas
                        
                        # Evitar que la tabla se salga de la hoja
                        if ly > 200: ly = 200

                # 6. TOTALES (Alineados con "Subtotal:" y "Total:" en tu plantilla)
                pdf.set_font("Helvetica", '', 11)
                # Coordenada x=170 alinea los valores a la derecha de los textos de la plantilla
                # Subtotal
                pdf.text(170, 219, f"${subtotal:,.2f}")
                
                # Discount (Nuevo dato)
                if desc_valor > 0:
                    pdf.set_text_color(220, 20, 60) # Rojo para descuento
                    pdf.text(170, 227, f"-${desc_valor:,.2f}")
                    pdf.set_text_color(0, 0, 0) # Volver a negro
                else:
                    pdf.text(170, 227, "$0.00")

                # Total Due
                pdf.set_font("Helvetica", 'B', 14)
                pdf.text(170, 239, f"${g_total:,.2f}")
                
                # 7. NUEVO BLOQUE: MÉTODOS DE PAGO (Parte inferior izquierda, cajita vacía)
                pdf.set_text_color(*blue)
                pdf.set_font("Helvetica", 'B', 11)
                pdf.text(15, 215, "PAYMENT OPTIONS:")
                
                pdf.set_text_color(0, 0, 0)
                pdf.set_font("Helvetica", '', 9)
                pm_y = 220
                if zelle_on:
                    pdf.text(15, pm_y, "Zelle: MirandaServiceOficial@gmail.com")
                    pm_y += 5
                if venmo_on:
                    pdf.text(15, pm_y, "Venmo: @UsuarioDePapa (Soon)") # Reemplazar por usuario real
                    pm_y += 5
                if cash_on:
                    pdf.set_font("Helvetica", '', 8) # Más chiquito para que quepa
                    pdf.text(15, pm_y, "Check: Payable to Miranda Service / Cash Accepted")
                    pdf.set_font("Helvetica", '', 9)
                
                # 8. PIE DE PÁGINA: AGRADECIMIENTO Y TÉRMINOS
                pdf.set_text_color(100, 100, 100) # Gris oscuro
                pdf.set_font("Helvetica", '', 8)
                footer_text = "Thank you for choosing Miranda Service! Your landscaping, professionalized.\nFull payment is due within 5 days. Late fee of 5% may apply after Due Date."
                pdf.set_xy(15, 250)
                # Centrado de footer_text en todo el ancho (180mm)
                pdf.multi_cell(180, 4, footer_text, align='C')

                # GUARDAR Y PROCESAR
                fname = f"{folio}_{nom_cli.replace(' ','_')}.pdf"
                # Usamos Helvetica para asegurar UTF-8 compatibility básica
                pdf.output(fname)
                
                hoja_facturas.append_row([folio, nom_cli, str(f_emision), str(f_venc), f"${g_total:,.2f}", "Pendiente", "Copy in Gmail"])
                obtener_facturas_records.clear() 
                
                if cor_cli and PASSWORD_APP_GMAIL != " yanwkulxewxpnccg " and enviar_correo:
                    try:
                        msg = EmailMessage()
                        msg['Subject'] = f'Invoice {folio} - Miranda Service LLC'
                        msg['From'] = CORREO_PAPA; msg['To'] = cor_cli; msg['Cc'] = CORREO_PAPA
                        msg.set_content(f"Hi {nom_cli},\n\nAttached is invoice {folio} from Miranda Service LLC for landscaping services.\n\nService Address: {dir_cli}\n\nTotal Due: ${g_total:,.2f}\n\nThank you for your business!\n\nRegards,\nMiranda Service\nTel: {TELEFONO_PAPA}")
                        with open(fname, 'rb') as f: msg.add_attachment(f.read(), maintype='application', subtype='pdf', filename=fname)
                        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as s:
                            s.login(CORREO_PAPA, PASSWORD_APP_GMAIL); s.send_message(msg)
                    except Exception as email_err:
                        st.error(f"Factura generada, error enviando correo: {email_err}")
                
                st.success(f"¡Factura {folio} emitida y guardada!")
                with open(fname, "rb") as f: st.download_button("⬇️ Descargar PDF Profesional", f, file_name=fname, type="primary", width="stretch")
                os.remove(fname)

# ==========================================
# PESTAÑAS 2 Y 3 (SIN CAMBIOS)
# ==========================================
with tab2:
    st.subheader("Control de Cobros")
    data_fac = obtener_facturas_records()
    if data_fac:
        df = pd.DataFrame(data_fac)
        if 'Ruta_PDF' in df.columns: df = df.drop(columns=['Ruta_PDF'])
        st.dataframe(df, hide_index=True, width="stretch")
        pendientes = df[df["Estado"] == "Pendiente"]["Folio"].tolist()
        if pendientes:
            st.divider()
            f_pago = st.selectbox("Registrar pago de la factura:", pendientes)
            if st.button("💰 Confirmar Pago", width="stretch"):
                cell = hoja_facturas.find(f_pago)
                hoja_facturas.update_cell(cell.row, 6, "Pagado")
                obtener_facturas_records.clear(); st.success(f"Factura {f_pago} actualizada."); st.rerun()
    else: st.info("Sin registros.")

with tab3:
    st.header("👥 Clientes")
    c1, c2 = st.columns([2, 1])
    with c1: 
        df_c = pd.DataFrame(list(clientes_db.items()), columns=["Nombre", "Data"])
        df_c["Correo"] = df_c["Data"].apply(lambda x: x['correo'])
        st.dataframe(df_c[["Nombre", "Correo"]], hide_index=True, width="stretch")
    with c2:
        with st.expander("✏️ Gestionar"):
            if clientes_db:
                c_sel = st.selectbox("Elegir cliente", list(clientes_db.keys()))
                d_dir = st.session_state.get(f"input_gestion_dir", clientes_db[c_sel]['direccion'])
                st.text_area("Editar Dirección", value=clientes_db[c_sel]['direccion'])
                st.write("*(Para ediciones avanzadas, usar Google Sheets directamente)*")

    st.divider()
    st.header("🛠️ Servicios")
    s1, s2 = st.columns([2, 1])
    with s1: st.dataframe(pd.DataFrame(list(servicios_db.items()), columns=["Servicio", "Precio"]), hide_index=True, width="stretch")
    with s2:
        with st.expander("➕ Añadir"):
            s_n = st.text_input("Descripción servicio")
            s_p = st.number_input("Precio base", min_value=0.0)
            if st.button("Guardar Nuevo Servicio"): hoja_servicios.append_row([s_n, s_p]); obtener_servicios.clear(); st.rerun()
