import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from fpdf import FPDF
import datetime
import os
import smtplib
from email.message import EmailMessage
import json
import pandas as pd # Necesario para mostrar tablas bonitas en Streamlit

# --- CONFIGURACIÓN DE PÁGINA DE STREAMLIT ---
st.set_page_config(page_title="Miranda Service", page_icon="🌿", layout="centered")

# --- DATOS DE MIRANDA SERVICE ---
CORREO_PAPA = "MirandaServiceOficial@gmail.com"

# Intentar leer la contraseña de Gmail desde los Secretos de la Nube. Si falla, usa un texto por defecto.
try:
    PASSWORD_APP_GMAIL = st.secrets["gmail_password"]
except:
    PASSWORD_APP_GMAIL = "AQUI_TU_CONTRASENA_DE_APLICACION"

DIRECCION_PAPA = "190 Shannon Blvd, Middletown, DE 19709"
TELEFONO_PAPA = "(302) 584-2281"
PLANTILLA_IMG = "plantilla_presupuesto.png"

# --- CONEXIÓN A GOOGLE SHEETS (CORREGIDA PARA LA NUBE) ---
@st.cache_resource
def conectar_bd():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    
    # El programa detecta si está en la nube (Streamlit) leyendo los secretos
    if "google_creds_json" in st.secrets:
        creds_dict = json.loads(st.secrets["google_creds_json"])
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    else:
        # Si lo pruebas en tu compu y no tienes secretos configurados, intenta leer el archivo local
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

# --- FUNCIONES DE LECTURA DE BD ---
def obtener_clientes():
    registros = hoja_clientes.get_all_records()
    return {fila['Nombre']: str(fila['Correo']) for fila in registros if 'Nombre' in fila}

def obtener_servicios():
    registros = hoja_servicios.get_all_records()
    return {fila['Servicio']: float(fila['Precio']) for fila in registros if 'Servicio' in fila}

clientes_db = obtener_clientes()
servicios_db = obtener_servicios()

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
    cliente_seleccionado = st.selectbox("Selecciona un cliente o elige (Nuevo Cliente)", nombres_clientes)
    
    if cliente_seleccionado == "(Nuevo Cliente)":
        nombre_cliente = st.text_input("Nombre del Nuevo Cliente")
        correo_cliente = st.text_input("Correo Electrónico")
    else:
        nombre_cliente = cliente_seleccionado
        correo_cliente = st.text_input("Correo Electrónico", value=clientes_db.get(cliente_seleccionado, ""))

    st.divider()
    st.subheader("Detalles del Servicio")
    
    nombres_servicios = [""] + list(servicios_db.keys())
    
    descripciones = []
    cantidades = []
    precios = []
    gran_total = 0.0

    for i in range(5):
        col1, col2, col3 = st.columns([3, 1, 1])
        with col1:
            desc = st.selectbox(f"Servicio {i+1}", nombres_servicios, key=f"desc_{i}")
            descripciones.append(desc)
        with col2:
            cant = st.number_input("Cant.", min_value=0.0, step=1.0, key=f"cant_{i}")
            cantidades.append(cant)
        with col3:
            precio_sugerido = servicios_db.get(desc, 0.0) if desc else 0.0
            precio = st.number_input("Precio ($)", min_value=0.0, value=float(precio_sugerido), step=1.0, key=f"precio_{i}")
            precios.append(precio)
            
        gran_total += (cant * precio)

    st.subheader(f"Total a Pagar: ${gran_total:,.2f}")
    enviar_correo = st.checkbox("Enviar PDF por Correo automáticamente al cliente y a mí", value=True)

    if st.button("📄 Generar Factura", type="primary", use_container_width=True):
        if not nombre_cliente.strip():
            st.warning("Debes ingresar el nombre del cliente.")
        elif gran_total == 0:
            st.warning("Debes agregar al menos un servicio con cantidad y precio.")
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
    st.subheader("Historial de Facturas (En vivo desde Google Sheets)")
    
    registros_fac = hoja_facturas.get_all_records()
    
    if not registros_fac:
        st.info("Aún no hay facturas registradas en la base de datos.")
    else:
        # Convertimos los datos de Google Sheets a una tabla bonita (DataFrame)
        df_facturas = pd.DataFrame(registros_fac)
        
        # Filtro de Estado
        filtro_estado = st.radio("Filtrar por:", ["Todas", "Pendiente", "Pagado"], horizontal=True)
        
        if filtro_estado != "Todas":
            df_mostrar = df_facturas[df_facturas["Estado"] == filtro_estado]
        else:
            df_mostrar = df_facturas
            
        st.dataframe(df_mostrar, use_container_width=True, hide_index=True)

        st.divider()
        st.write("### Marcar Factura como Pagada")
        
        # Obtenemos solo las facturas que están Pendientes
        facturas_pendientes = df_facturas[df_facturas["Estado"] == "Pendiente"]["Folio"].tolist()
        
        if facturas_pendientes:
            folio_a_pagar = st.selectbox("Selecciona el Folio que ya fue pagado:", facturas_pendientes)
            if st.button("💰 Confirmar Pago", type="primary"):
                # Buscar la fila exacta en Google Sheets para actualizarla
                celda = hoja_facturas.find(folio_a_pagar)
                if celda:
                    hoja_facturas.update_cell(celda.row, 6, "Pagado") # Columna 6 es la del Estado
                    st.success(f"¡Factura {folio_a_pagar} marcada como Pagada con éxito!")
                    st.rerun() # Refresca la página para mostrar los cambios
        else:
            st.success("¡Excelente! No tienes facturas pendientes de cobro.")

# ==========================================
# PESTAÑA 3: DIRECTORIO
# ==========================================
with tab3:
    st.subheader("Directorio de Clientes")
    if clientes_db:
        df_clientes = pd.DataFrame(list(clientes_db.items()), columns=["Nombre", "Correo"])
        st.dataframe(df_clientes, use_container_width=True, hide_index=True)
    else:
        st.info("No hay clientes registrados.")
        
    st.divider()
    st.subheader("Catálogo de Servicios")
    if servicios_db:
        df_servicios = pd.DataFrame(list(servicios_db.items()), columns=["Servicio", "Precio"])
        st.dataframe(df_servicios, use_container_width=True, hide_index=True)
    else:
        st.info("No hay servicios registrados.")
        
    st.divider()
    st.info("💡 Para agregar nuevos clientes o servicios a este directorio, simplemente escríbelos en la pestaña 'Crear Factura'. El sistema los guardará automáticamente al emitir el recibo. Para borrar o modificar registros antiguos, edita directamente tu archivo 'Miranda_DB' en tu App de Google Sheets.")
