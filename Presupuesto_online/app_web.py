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

# --- FUNCIONES DE LECTURA (CON CACHÉ DINÁMICO) ---
@st.cache_data(ttl=60)
def obtener_clientes():
    for intento in range(3):
        try:
            registros = hoja_clientes.get_all_records()
            return {
                str(f.get('Nombre', '')).strip(): {
                    'correo': str(f.get('Correo', '')).strip(),
                    'direccion': str(f.get('Direccion', '')).strip(),
                    'telefono': str(f.get('Telefono', '')).strip()
                }
                for f in registros if f.get('Nombre')
            }
        except Exception:
            time.sleep(2)
    return {}

@st.cache_data(ttl=60)
def obtener_servicios():
    for intento in range(3):
        try:
            registros = hoja_servicios.get_all_records()
            return {str(f.get('Servicio', '')).strip(): float(f.get('Precio', 0)) for f in registros if f.get('Servicio')}
        except Exception:
            time.sleep(2)
    return {}

@st.cache_data(ttl=60)
def obtener_facturas_records():
    for intento in range(
