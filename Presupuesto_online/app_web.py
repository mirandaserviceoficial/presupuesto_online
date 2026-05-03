# --- Pestañas 2 y 3 (Gestión Actualizada con Finanzas Interactivas) ---
with tab2:
    st.subheader("Historial y Finanzas")
    data = obtener_facturas_records()
    if data:
        df = pd.DataFrame(data)
        
        # --- NUEVA SECCIÓN: FINANZAS MENSUALES INTERACTIVAS ---
        st.write("### 📈 Resumen Mensual")
        try:
            # Asumimos que la Fecha de Emisión es la col 2 y el Total la col 4 
            col_fecha = df.columns[2] 
            col_total = df.columns[4]
            
            df_finanzas = df.copy()
            
            # Limpiar la columna de Total (quitar '$' y ',') para sumar
            df_finanzas['Valor_Num'] = df_finanzas[col_total].astype(str).str.replace('$', '', regex=False).str.replace(',', '', regex=False)
            df_finanzas['Valor_Num'] = pd.to_numeric(df_finanzas['Valor_Num'], errors='coerce').fillna(0)
            
            # Extraer Mes y Año de la fecha
            df_finanzas['Mes'] = pd.to_datetime(df_finanzas[col_fecha], errors='coerce').dt.to_period('M')
            
            # Agrupar por Mes y por Estado
            resumen = df_finanzas.groupby(['Mes', 'Estado'])['Valor_Num'].sum().unstack(fill_value=0)
            
            # Asegurar que las columnas existan aunque no haya facturas de un tipo
            if 'Pagado' not in resumen.columns: resumen['Pagado'] = 0.0
            if 'Pendiente' not in resumen.columns: resumen['Pendiente'] = 0.0
            
            resumen['Total Generado'] = resumen['Pagado'] + resumen['Pendiente']
            
            # Crear lista de meses disponibles ordenados del más reciente al más antiguo
            meses_disponibles = sorted(resumen.index.astype(str).tolist(), reverse=True)
            
            if meses_disponibles:
                # Selector de mes interactivo
                mes_seleccionado = st.selectbox("📅 Seleccionar Mes a visualizar:", meses_disponibles)
                
                # Buscar los datos del mes seleccionado
                mes_period = pd.Period(mes_seleccionado, freq='M')
                
                pagado_mes = resumen.loc[mes_period, 'Pagado']
                pdte_mes = resumen.loc[mes_period, 'Pendiente']
                total_mes = resumen.loc[mes_period, 'Total Generado']
                
                # Mostrar tarjetas visuales actualizadas dinámicamente
                m1, m2, m3 = st.columns(3)
                m1.metric(label=f"💰 Ingresos ({mes_seleccionado})", value=f"${pagado_mes:,.2f}", help="Facturas cobradas este mes")
                m2.metric(label=f"⏳ Por Cobrar ({mes_seleccionado})", value=f"${pdte_mes:,.2f}", help="Facturas pendientes este mes")
                m3.metric(label=f"📊 Total Generado ({mes_seleccionado})", value=f"${total_mes:,.2f}", help="Pagado + Pendiente")
                
                with st.expander("Ver desglose de todos los meses"):
                    res_display = resumen.copy()
                    res_display.index = res_display.index.astype(str) # Convertir a texto para la tabla
                    for c in res_display.columns:
                        res_display[c] = res_display[c].apply(lambda x: f"${x:,.2f}")
                    st.dataframe(res_display, use_container_width=True)
                    
        except Exception as e:
            st.warning("No hay datos suficientes para graficar las métricas aún.")
            
        st.divider()
        
        # --- HISTORIAL Y EDICIÓN DE ESTADOS ---
        st.write("### 🗂️ Registro de Facturas")
        if 'Ruta_PDF' in df.columns: 
            df = df.drop(columns=['Ruta_PDF'])
        st.dataframe(df, hide_index=True, use_container_width=True)
        
        st.divider()
        st.write("### Acciones Rápidas")
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
