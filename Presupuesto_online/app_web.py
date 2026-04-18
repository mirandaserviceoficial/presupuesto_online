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

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Miranda Service", page_icon="🌿", layout="centered")

# --- DATOS DE MIRANDA SERVICE ---
CORREO_PAPA = "MirandaServiceOficial@gmail.com"

try:
    PASSWORD_APP_GMAIL = st.secrets["gmail_password"]
except:
    PASSWORD_APP_GMAIL = "AQUI_TU_CONTRASENA_DE_APLICACION"

DIRECCION_PAPA = "190 Shannon Blvd, Middletown, DE 19709"
TELEFONO_PAPA = "(302) 584-2281"
# Obligamos al servidor a buscar en la ruta absoluta correcta
DIRECTORIO_ACTUAL = os.path.dirname(os.path.abspath(__file__))
PLANTILLA_IMG = os.path.join(DIRECTORIO_ACTUAL, "plantilla_presupuesto.png")

# --- CONEXIÓN A GOOGLE SHEETS ---
@st.cache_resource
def conectar_bd():
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
    db = conectar_bd()
    hoja_clientes = db.worksheet("Clientes")
    hoja_servicios = db.worksheet("Servicios")
    hoja_facturas = db.worksheet("Facturas")
except Exception as e:
    st.error(f"Error conectando a Google Sheets. Detalle: {e}")
    st.stop()

# --- FUNCIONES DE LECTURA (LIMPIEZA DE ESPACIOS INVISIBLES) ---
def obtener_clientes():
    registros = hoja_clientes.get_all_records()
    clientes_limpios = {}
    for fila in registros:
        # Quitamos espacios accidentales en los títulos de Excel
        fila_limpia = {str(k).strip(): v for k, v in fila.items()}
        if 'Nombre' in fila_limpia and fila_limpia['Nombre']:
            clientes_limpios[str(fila_limpia['Nombre']).strip()] = str(fila_limpia.get('Correo', '')).strip()
    return clientes_limpios

def obtener_servicios():
    registros = hoja_servicios.get_all_records()
    serv_limpios = {}
    for fila in registros:
        fila_limpia = {str(k).strip(): v for k, v in fila.items()}
        if 'Servicio' in fila_limpia and fila_limpia['Servicio']:
            try:
                serv_limpios[str(fila_limpia['Servicio']).strip()] = float(fila_limpia.get('Precio', 0.0))
            except:
                serv_limpios[str(fila_limpia['Servicio']).strip()] = 0.0
    return serv_limpios

clientes_db = obtener_clientes()
servicios_db = obtener_servicios()

# --- FUNCIONES DE AUTOCOMPLETADO (CALLBACKS) ---
def autocompletar_correo():
    sel = st.session_state["combo_cliente"]
    if sel != "(Nuevo Cliente)" and sel in clientes_db:
        st.session_state["input_correo"] = clientes_db[sel]
    else:
        st.session_state["input_correo"] = ""

def autocompletar_precio(i):
    desc = st.session_state[f"desc_{i}"]
    if desc in servicios_db:
        st.session_state[f"precio_{i}"] = float(servicios_db[desc])
        # Opcional: Si la cantidad está en 0, ponerle 1 automáticamente
        if st.session_state.get(f"cant_{i}", 0.0) == 0.0:
            st.session_state[f"cant_{i}"] = 1.0
    else:
        st.session_state[f"precio_{i}"] = 0.0

# --- INICIALIZAR MEMORIA (SESSION STATE) ---
if "input_correo" not in st.session_state:
    st.session_state["input_correo"] = ""
for i in range(5):
    if f"precio_{i}" not in st.session_state:
        st.session_state[f"precio_{i}"] = 0.0
    if f"cant_{i}" not in st.session_state:
        st.session_state[f"cant_{i}"] = 0.0


# --- INTERFAZ WEB ---
st.title("🌿 MIRANDA SERVICE")
st.caption("Sistema de Facturación en la Nube")

tab1, tab2, tab3 = st.tabs(["📝 Crear Factura", "📊 Historial", "🗂️ Directorio"])

# ==========================================
# PESTAÑA 1: CREAR FACTURA
# ==========================================
with tab1:
    st.subheader("Datos del Cliente")
    
    nombres_clientes = ["(Nuevo Cliente)"] + list(clientes_db.keys())
    
    # El dropdown que activa el autocompletado del correo
    st.selectbox("Selecciona un cliente o elige (Nuevo Cliente)", nombres_clientes, key="combo_cliente", on_change=autocompletar_correo)
    
    if st.session_state["combo_cliente"] == "(Nuevo Cliente)":
        nombre_cliente = st.text_input("Nombre del Nuevo Cliente")
    else:
        nombre_cliente = st.session_state["combo_cliente"]
        
    correo_cliente = st.text_input("Correo Electrónico", key="input_correo")

    st.divider()
    st.subheader("Detalles del Servicio")
    
    nombres_servicios = [""] + list(servicios_db.keys())
    
    descripciones = []
    cantidades = []
    precios = []
    gran_total = 0.0

    # Dibujamos las 5 filas con memoria reactiva
    for i in range(5):
        col1, col2, col3 = st.columns([3, 1, 1])
        with col1:
            desc = st.selectbox(f"Servicio {i+1}", nombres_servicios, key=f"desc_{i}", on_change=autocompletar_precio, args=(i,))
            descripciones.append(desc)
        with col2:
            cant = st.number_input("Cant.", min_value=0.0, step=1.0, key=f"cant_{i}")
            cantidades.append(cant)
        with col3:
            precio = st.number_input("Precio ($)", min_value=0.0, step=1.0, key=f"precio_{i}")
            precios.append(precio)
            
        gran_total += (cant * precio)

    st.subheader(f"Total a Pagar: ${gran_total:,.2f}")
    enviar_correo = st.checkbox("Enviar PDF por Correo automáticamente", value=True)

    if st.button("📄 Generar Factura", type="primary", use_container_width=True):
        if not nombre_cliente.strip():
            st.warning("Debes ingresar el nombre del cliente.")
        elif gran_total == 0:
            st.warning("Debes agregar al menos un servicio válido.")
        else:
            with st.spinner("Generando documento y actualizando base de datos..."):
                if nombre_cliente not in clientes_db or clientes_db[nombre_cliente] != correo_cliente:
                    hoja_clientes.append_row([nombre_cliente, correo_cliente])
                
                registros_facturas = hoja_facturas.get_all_values()
                numero_folio = len(registros_facturas)
                str_folio = f"FAC-{numero_folio:04d}"
                
                fecha_emision = datetime.date.today()
                fecha_vencimiento = fecha_emision + datetime.timedelta(days=5)

                pdf = FPDF()
                pdf.add_page()
                if os.path.exists(PLANTILLA_IMG):
                    pdf.image(PLANTILLA_IMG, x=0, y=0, w=210)
                
                pdf.set_font("Arial", 'B', size=10)
                pdf.set_text_color(100, 100, 100)
                pdf.text(120, 20, "MIRANDA SERVICE")
                pdf.set_font("Arial", size=9)
                pdf.text(120, 25, DIRECCION_PAPA)
                pdf.text(120, 30, f"Tel: {TELEFONO_PAPA}")
                pdf.text(120, 35, CORREO_PAPA)
                pdf.set_text_color(0, 0, 0)

                pdf.set_font("Arial", 'B', size=12)
                pdf.text(120, 50, f"Invoice #:   {str_folio}")
                pdf.set_font("Arial", size=10)
                pdf.text(120, 55, f"Issued:   {fecha_emision.strftime('%m/%d/%Y')}")
                pdf.set_text_color(200, 0, 0)
                pdf.text(120, 60, f"Due Date:   {fecha_vencimiento.strftime('%m/%d/%Y')}")
                pdf.set_text_color(0, 0, 0)

                pdf.set_font("Arial", size=12)
                pdf.text(135, 76, nombre_cliente) 
                if correo_cliente:
                    pdf.set_font("Arial", size=10)
                    pdf.text(135, 81, correo_cliente)

                pdf.set_font("Arial", size=11)
                linea_y = 100
                for d, c, p in zip(descripciones, cantidades, precios):
                    if d and c > 0 and p > 0:
                        pdf.text(20, linea_y, d)
                        pdf.text(128, linea_y, str(int(c) if c.is_integer() else c))
                        pdf.text(150, linea_y, f"${p:,.2f}")
                        pdf.text(175, linea_y, f"${(c * p):,.2f}")
                        linea_y += 10

                pdf.set_font("Arial", 'B', size=12)
                pdf.text(170, 159, f"${gran_total:,.2f}")
                pdf.text(170, 178, f"${gran_total:,.2f}")

                nombre_archivo = f"{str_folio}_{nombre_cliente.replace(' ', '_')}.pdf"
                pdf.output(nombre_archivo)
                
                hoja_facturas.append_row([str_folio, nombre_cliente, str(fecha_emision), str(fecha_vencimiento), f"${gran_total:,.2f}", "Pendiente", "Nube"])

                mensaje_exito = f"Factura {str_folio} guardada en Google Sheets."
                if enviar_correo and correo_cliente and PASSWORD_APP_GMAIL != "AQUI_TU_CONTRASENA_DE_APLICACION":
                    try:
                        msg = EmailMessage()
                        msg['Subject'] = f'Factura {str_folio} - Miranda Service'
                        msg['From'] = CORREO_PAPA
                        msg['To'] = correo_cliente
                        msg['Cc'] = CORREO_PAPA 
                        msg.set_content(f"Hola {nombre_cliente},\n\nAdjunto encontrarás la factura {str_folio}.\nTienes 5 días para realizar el pago.\n\nGracias por confiar en Miranda Service.\nTel: {TELEFONO_PAPA}")
                        with open(nombre_archivo, 'rb') as f:
                            msg.add_attachment(f.read(), maintype='application', subtype='pdf', filename=nombre_archivo)
                        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
                            smtp.login(CORREO_PAPA, PASSWORD_APP_GMAIL)
                            smtp.send_message(msg)
                        mensaje_exito += " ✅ Correo enviado."
                    except Exception as e:
                        st.error(f"Error al enviar correo: {e}")

                st.success(mensaje_exito)
                
                with open(nombre_archivo, "rb") as pdf_file:
                    st.download_button(
                        label="⬇️ Descargar PDF",
                        data=pdf_file,
                        file_name=nombre_archivo,
                        mime="application/pdf",
                        type="primary"
                    )

# ==========================================
# PESTAÑA 2: HISTORIAL Y COBROS
# ==========================================
with tab2:
    st.subheader("Historial de Facturas (En vivo)")
    registros_fac = hoja_facturas.get_all_records()
    
    if not registros_fac:
        st.info("Aún no hay facturas registradas.")
    else:
        df_facturas = pd.DataFrame(registros_fac)
        filtro_estado = st.radio("Filtrar por:", ["Todas", "Pendiente", "Pagado"], horizontal=True)
        
        if filtro_estado != "Todas":
            df_mostrar = df_facturas[df_facturas["Estado"] == filtro_estado]
        else:
            df_mostrar = df_facturas
            
        st.dataframe(df_mostrar, use_container_width=True, hide_index=True)

        st.divider()
        st.write("### Marcar Factura como Pagada")
        
        if "Folio" in df_facturas.columns:
            facturas_pendientes = df_facturas[df_facturas["Estado"] == "Pendiente"]["Folio"].tolist()
            if facturas_pendientes:
                folio_a_pagar = st.selectbox("Selecciona el Folio pagado:", facturas_pendientes)
                if st.button("💰 Confirmar Pago", type="primary"):
                    celda = hoja_facturas.find(folio_a_pagar)
                    if celda:
                        hoja_facturas.update_cell(celda.row, 6, "Pagado") 
                        st.success(f"¡Factura {folio_a_pagar} marcada como Pagada!")
                        st.rerun() 
            else:
                st.success("¡Excelente! No tienes facturas pendientes.")

# ==========================================
# PESTAÑA 3: DIRECTORIO (GESTIÓN COMPLETA)
# ==========================================
with tab3:
    # --- SECCIÓN DE CLIENTES ---
    st.header("👥 Gestión de Clientes")
    
    col_tab_cli, col_ops_cli = st.columns([2, 1])
    
    with col_tab_cli:
        if clientes_db:
            df_clientes = pd.DataFrame(list(clientes_db.items()), columns=["Nombre", "Correo"])
            st.dataframe(df_clientes, use_container_width=True, hide_index=True)
        else:
            st.info("No hay clientes registrados.")

    with col_ops_cli:
        with st.expander("➕ Agregar"):
            with st.form("add_cli", clear_on_submit=True):
                n_nom = st.text_input("Nombre")
                n_cor = st.text_input("Correo")
                if st.form_submit_button("Guardar"):
                    if n_nom:
                        hoja_clientes.append_row([n_nom.strip(), n_cor.strip()])
                        st.success("Añadido")
                        st.rerun()
        
        with st.expander("✏️ Editar / Borrar"):
            if clientes_db:
                cli_a_mod = st.selectbox("Selecciona Cliente", list(clientes_db.keys()))
                nuevo_nom = st.text_input("Nuevo Nombre", value=cli_a_mod)
                nuevo_cor = st.text_input("Nuevo Correo", value=clientes_db[cli_a_mod])
                
                c1, c2 = st.columns(2)
                if c1.button("Actualizar", use_container_width=True):
                    celda = hoja_clientes.find(cli_a_mod)
                    hoja_clientes.update_cell(celda.row, 1, nuevo_nom)
                    hoja_clientes.update_cell(celda.row, 2, nuevo_cor)
                    st.success("Actualizado")
                    st.rerun()
                
                if c2.button("Eliminar", use_container_width=True, type="secondary"):
                    celda = hoja_clientes.find(cli_a_mod)
                    hoja_clientes.delete_rows(celda.row)
                    st.warning("Eliminado")
                    st.rerun()

    st.divider()

    # --- SECCIÓN DE SERVICIOS ---
    st.header("🛠️ Catálogo de Servicios")
    
    col_tab_ser, col_ops_ser = st.columns([2, 1])
    
    with col_tab_ser:
        if servicios_db:
            df_servicios = pd.DataFrame(list(servicios_db.items()), columns=["Servicio", "Precio"])
            st.dataframe(df_servicios, use_container_width=True, hide_index=True)
        else:
            st.info("No hay servicios registrados.")

    with col_ops_ser:
        with st.expander("➕ Agregar"):
            with st.form("add_ser", clear_on_submit=True):
                s_nom = st.text_input("Servicio")
                s_pre = st.number_input("Precio", min_value=0.0)
                if st.form_submit_button("Guardar"):
                    if s_nom:
                        hoja_servicios.append_row([s_nom.strip(), s_pre])
                        st.success("Añadido")
                        st.rerun()

        with st.expander("✏️ Editar / Borrar"):
            if servicios_db:
                ser_a_mod = st.selectbox("Selecciona Servicio", list(servicios_db.keys()))
                s_nuevo_nom = st.text_input("Nueva Descripción", value=ser_a_mod)
                s_nuevo_pre = st.number_input("Nuevo Precio", value=float(servicios_db[ser_a_mod]))
                
                b1, b2 = st.columns(2)
                if b1.button("Actualizar ", use_container_width=True):
                    celda = hoja_servicios.find(ser_a_mod)
                    hoja_servicios.update_cell(celda.row, 1, s_nuevo_nom)
                    hoja_servicios.update_cell(celda.row, 2, s_nuevo_pre)
                    st.success("Actualizado")
                    st.rerun()
                
                if b2.button("Eliminar ", use_container_width=True):
                    celda = hoja_servicios.find(ser_a_mod)
                    hoja_servicios.delete_rows(celda.row)
                    st.warning("Eliminado")
                    st.rerun()
