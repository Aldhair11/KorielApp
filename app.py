import streamlit as st
import pandas as pd
from supabase import create_client
from datetime import datetime, timedelta, date
import time
import io # Necesario para el módulo de Backup

# --- 1. CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Grupo Koriel ERP", page_icon="⚡", layout="wide")

# --- 2. ESTILOS CSS (DISEÑO) ---
st.markdown("""
<style>
    [data-testid="stSidebarNav"] {display: none;}
    .stRadio > label {display: none;}
    div[data-testid="stMetricValue"] {font-size: 26px; font-weight: bold;}
    
    /* Estilo para alertas */
    .stAlert {padding: 0.5rem; margin-bottom: 1rem;}
</style>
""", unsafe_allow_html=True)

# --- 3. CONEXIÓN BASE DE DATOS ---
@st.cache_resource
def init_connection():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

supabase = init_connection()

# --- 4. USUARIOS Y SEGURIDAD ---
USUARIOS = {
    "admin": "admin123",
    "jorge": "1234",
    "maria": "0000"
}

# --- 5. FUNCIONES DEL SISTEMA (MOTOR) ---
def insertar_registro(tabla, datos):
    try:
        supabase.table(tabla).insert(datos).execute()
        return True
    except Exception as e:
        st.error(f"Error guardando en {tabla}: {e}")
        return False

def cargar_tabla(tabla):
    try:
        response = supabase.table(tabla).select("*").execute()
        df = pd.DataFrame(response.data)
        
        # Limpieza y formatos automáticos
        if "fecha_registro" in df.columns:
            df["fecha_registro"] = pd.to_datetime(df["fecha_registro"]).dt.date
        if "fecha_evento" in df.columns:
            df["fecha_evento"] = pd.to_datetime(df["fecha_evento"])
        
        # Quitamos columnas técnicas que ensucian la vista
        if "created_at" in df.columns:
            df = df.drop(columns=["created_at"])
            
        return df
    except:
        return pd.DataFrame()

def actualizar_prestamo(id_p, cant, total):
    try:
        supabase.table("prestamos").update({
            "cantidad_pendiente": cant, 
            "total_pendiente": total
        }).eq("id", id_p).execute()
    except Exception as e:
        st.error(f"Error actualizando préstamo: {e}")

def editar_maestro(tabla, id_row, datos_nuevos):
    try:
        supabase.table(tabla).update(datos_nuevos).eq("id", id_row).execute()
        return True
    except Exception as e:
        st.error(f"Error editando registro: {e}")
        return False

# --- 6. SISTEMA DE LOGIN ---
def check_login():
    if "usuario_logueado" in st.session_state and st.session_state["usuario_logueado"]:
        return True
    
    st.session_state["usuario_logueado"] = None
    st.markdown("<br><br>", unsafe_allow_html=True)
    st.markdown("<h1 style='text-align: center;'>🔐 GRUPO KORIEL CLOUD</h1>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("### Acceso al Sistema")
        user = st.text_input("Usuario")
        password = st.text_input("Contraseña", type="password")
        
        if st.button("Iniciar Sesión", use_container_width=True, type="primary"):
            if user in USUARIOS and USUARIOS[user] == password:
                st.session_state["usuario_logueado"] = user
                st.toast(f"¡Bienvenido {user}!")
                time.sleep(0.5)
                st.rerun()
            else:
                st.error("Credenciales incorrectas.")
    return False

def logout():
    st.session_state["usuario_logueado"] = None
    st.rerun()

# --- 7. APLICACIÓN PRINCIPAL ---
def main_app():
    usuario_actual = st.session_state["usuario_logueado"]
    
    # --- SIDEBAR (MENÚ) ---
    with st.sidebar:
        st.title("🏢 KORIEL CLOUD")
        st.write(f"👤 Usuario: **{usuario_actual.upper()}**")
        st.divider()
        
        menu = st.radio("Navegación", [
            "📦 Nuevo Préstamo", 
            "📍 Rutas y Cobro", 
            "🔍 Consultas y Recibos", 
            "📊 Reportes Financieros", 
            "🛠️ Administración"
        ])
        
        st.divider()
        if st.button("Cerrar Sesión"):
            logout()

    # Carga inicial de datos maestros
    df_cli = cargar_tabla("clientes")
    df_prod = cargar_tabla("productos")

    # ==========================================
    # MÓDULO 1: NUEVO PRÉSTAMO (CON RIESGO Y OBS)
    # ==========================================
    if menu == "📦 Nuevo Préstamo":
        st.title("📦 Registrar Salida de Mercadería")
        
        # Cargar deuda actual para el semáforo de riesgo
        df_deudas = cargar_tabla("prestamos")
        
        # Listas inteligentes (con opción de crear)
        lista_c = ["➕ CREAR NUEVO..."] + sorted(df_cli["nombre"].unique().tolist()) if not df_cli.empty else ["➕ CREAR NUEVO..."]
        lista_p = ["➕ CREAR NUEVO..."] + sorted(df_prod["nombre"].unique().tolist()) if not df_prod.empty else ["➕ CREAR NUEVO..."]

        with st.container(border=True):
            c1, c2 = st.columns(2)
            
            # --- SELECCIÓN DE CLIENTE ---
            with c1:
                st.subheader("1. Cliente")
                cli_sel = st.selectbox("Buscar Cliente", lista_c)
                
                cli_final = None
                new_cli_n = None; new_cli_t = None
                
                if cli_sel == "➕ CREAR NUEVO...":
                    st.info("⚡ Alta Rápida")
                    new_cli_n = st.text_input("Nombre Completo")
                    new_cli_t = st.text_input("Nombre Tienda")
                    cli_final = new_cli_n
                else: 
                    cli_final = cli_sel
                    # --- SEMÁFORO DE RIESGO (LO QUE PEDISTE) ---
                    if not df_deudas.empty:
                        deuda_actual = df_deudas[(df_deudas["cliente"] == cli_final)]["total_pendiente"].sum()
                        if deuda_actual > 0:
                            st.error(f"⚠️ **RIESGO:** Este cliente debe **${deuda_actual:,.2f}** actualmente.")
                        else:
                            st.success("✅ **CLEAN:** Cliente sin deuda pendiente.")
            
            # --- SELECCIÓN DE PRODUCTO ---
            with c2:
                st.subheader("2. Producto")
                prod_sel = st.selectbox("Buscar Producto", lista_p)
                
                prod_final = None; pre_sug = 0.0
                if prod_sel == "➕ CREAR NUEVO...":
                    st.info("⚡ Alta Rápida")
                    prod_final = st.text_input("Descripción Producto")
                else:
                    prod_final = prod_sel
                    # Buscar precio sugerido
                    if not df_prod.empty:
                        row = df_prod[df_prod["nombre"]==prod_sel]
                        if not row.empty: pre_sug = float(row.iloc[0]["precio_base"])

                cc1, cc2 = st.columns(2)
                cant = cc1.number_input("Cantidad", min_value=1, value=1)
                precio = cc2.number_input("Precio Unitario ($)", min_value=0.0, value=pre_sug, step=0.50)
            
            # --- OBSERVACIONES (NUEVO CAMPO) ---
            st.divider()
            obs = st.text_input("📝 Observaciones / Notas del Préstamo (Opcional)", placeholder="Ej: Entregar al portero, paga el fin de semana...")

            # --- BOTÓN GUARDAR ---
            if st.button("💾 GUARDAR PRÉSTAMO", type="primary", use_container_width=True):
                # Validaciones básicas
                if not cli_final or not prod_final:
                    st.error("Por favor completa el Cliente y el Producto.")
                else:
                    # 1. Crear cliente si es nuevo
                    if cli_sel == "➕ CREAR NUEVO...": 
                        insertar_registro("clientes", {"nombre": new_cli_n, "tienda": new_cli_t})
                    
                    # 2. Crear producto si es nuevo
                    if prod_sel == "➕ CREAR NUEVO...": 
                        insertar_registro("productos", {"nombre": prod_final, "categoria": "Otros", "precio_base": precio})
                    
                    # 3. Guardar Préstamo
                    insertar_registro("prestamos", {
                        "fecha_registro": datetime.now().strftime("%Y-%m-%d"),
                        "usuario": usuario_actual,
                        "cliente": cli_final,
                        "producto": prod_final,
                        "cantidad_pendiente": cant,
                        "precio_unitario": precio,
                        "total_pendiente": cant*precio,
                        "observaciones": obs # Guardando la observación
                    })
                    
                    st.success(f"✅ ¡Listo! Asignado a {cli_final}.")
                    time.sleep(1.5)
                    st.rerun()

    # ==========================================
    # MÓDULO 2: RUTAS Y COBRO (CON DEVOLVER TODO + OBS)
    # ==========================================
    elif menu == "📍 Rutas y Cobro":
        st.title("📍 Gestión de Cobranza")
        
        df_pend = cargar_tabla("prestamos")
        if not df_pend.empty: df_pend = df_pend[df_pend["cantidad_pendiente"] > 0]
        
        if df_pend.empty:
            st.balloons()
            st.success("🎉 ¡Felicidades! No hay cobranza pendiente.")
        else:
            # Selector de Cliente
            cli_visita = st.selectbox("Seleccionar Cliente en Ruta:", sorted(df_pend["cliente"].unique()))
            
            # Filtrar datos
            datos = df_pend[df_pend["cliente"] == cli_visita].copy()
            deuda_total_cliente = datos["total_pendiente"].sum()
            
            # Tarjeta de Info
            with st.container(border=True):
                col_info, col_deuda = st.columns([3, 1])
                with col_info:
                    if not df_cli.empty:
                        info = df_cli[df_cli["nombre"] == cli_visita]
                        if not info.empty:
                            r = info.iloc[0]
                            st.markdown(f"🏠 **Tienda:** {r.get('tienda','-')}")
                            st.markdown(f"📍 **Dirección:** {r.get('direccion','-')}")
                            st.markdown(f"📞 **Contacto:** {r.get('telefono','-')}")
                with col_deuda:
                    st.metric("DEUDA TOTAL", f"${deuda_total_cliente:,.2f}")

            # Preparar tabla editable
            datos["Cobrar"] = 0
            datos["Devolver"] = 0
            if "observaciones" not in datos.columns: datos["observaciones"] = "" # Evitar error si campo no existe
            
            # BOTONES DE ACCIÓN RÁPIDA (FLASH)
            col_flash1, col_flash2 = st.columns(2)
            with col_flash1:
                if st.button("💰 COBRAR TODO (Pagó 100%)", type="primary", use_container_width=True):
                    hoy = datetime.now().isoformat()
                    for i, r in datos.iterrows():
                        cant = int(r["cantidad_pendiente"])
                        monto = float(cant * r["precio_unitario"])
                        # Logica Cobro
                        insertar_registro("historial", {"fecha_evento": hoy, "usuario_responsable": usuario_actual, "tipo": "COBRO", "cliente": cli_visita, "producto": r["producto"], "cantidad": cant, "monto_operacion": monto})
                        # Dejar en 0
                        actualizar_prestamo(r["id"], 0, 0)
                    st.toast("✅ ¡Deuda Saldada!"); time.sleep(1); st.rerun()
            
            with col_flash2:
                if st.button("🔙 DEVOLVER TODO (No vendió)", use_container_width=True):
                    hoy = datetime.now().isoformat()
                    for i, r in datos.iterrows():
                        cant = int(r["cantidad_pendiente"])
                        # Logica Devolucion
                        insertar_registro("historial", {"fecha_evento": hoy, "usuario_responsable": usuario_actual, "tipo": "DEVOLUCION", "cliente": cli_visita, "producto": r["producto"], "cantidad": cant, "monto_operacion": 0})
                        # Dejar en 0
                        actualizar_prestamo(r["id"], 0, 0)
                    st.toast("✅ ¡Mercadería Devuelta!"); time.sleep(1); st.rerun()

            st.markdown("---")
            st.write("##### 📝 Gestión Manual / Parcial")
            
            # TABLA EDITABLE (CON OBSERVACIONES VISIBLES)
            edited = st.data_editor(
                datos[["id", "producto", "cantidad_pendiente", "precio_unitario", "observaciones", "Cobrar", "Devolver"]],
                column_config={
                    "id": st.column_config.NumberColumn(disabled=True),
                    "cantidad_pendiente": st.column_config.NumberColumn("Stock", disabled=True),
                    "precio_unitario": st.column_config.NumberColumn("Precio", format="$%.2f", disabled=True),
                    "observaciones": st.column_config.TextColumn("Notas", disabled=True),
                    "Cobrar": st.column_config.NumberColumn("Pagó (Und)", min_value=0),
                    "Devolver": st.column_config.NumberColumn("Devuelve (Und)", min_value=0)
                },
                hide_index=True, key="edit_cob"
            )
            
            # Cálculo en tiempo real
            total_a_pagar_ahora = (edited["Cobrar"] * edited["precio_unitario"]).sum()
            
            c_conf1, c_conf2 = st.columns([2, 1])
            with c_conf1:
                 if total_a_pagar_ahora > 0: 
                     st.success(f"💵 EL CLIENTE DEBE PAGAR AHORA: **${total_a_pagar_ahora:,.2f}**")
            
            with c_conf2:
                if st.button("✅ Procesar Manual", use_container_width=True):
                    hoy = datetime.now().isoformat()
                    proc = False
                    for i, r in edited.iterrows():
                        v, d = r["Cobrar"], r["Devolver"]
                        if v > 0 or d > 0:
                            proc = True
                            # Registrar Cobro
                            if v > 0: 
                                insertar_registro("historial", {"fecha_evento": hoy, "usuario_responsable": usuario_actual, "tipo": "COBRO", "cliente": cli_visita, "producto": r["producto"], "cantidad": int(v), "monto_operacion": float(v*r["precio_unitario"])})
                            # Registrar Devolución
                            if d > 0: 
                                insertar_registro("historial", {"fecha_evento": hoy, "usuario_responsable": usuario_actual, "tipo": "DEVOLUCION", "cliente": cli_visita, "producto": r["producto"], "cantidad": int(d), "monto_operacion": 0})
                            
                            # Actualizar Pendiente
                            new_c = int(r["cantidad_pendiente"]-v-d)
                            new_t = float(new_c * r["precio_unitario"])
                            actualizar_prestamo(r["id"], new_c, new_t)
                    
                    if proc: st.toast("Procesado correctamente"); time.sleep(1); st.rerun()

    # ==========================================
    # MÓDULO 3: CONSULTAS Y RECIBOS (CON FILTROS Y FORMATO TEXTO)
    # ==========================================
    elif menu == "🔍 Consultas y Recibos":
        st.title("🔍 Consultas y Recibos")
        
        tab_pend, tab_hist = st.tabs(["📂 Pendientes de Cobro", "📜 Historial de Movimientos"])
        
        # --- PESTAÑA PENDIENTES ---
        with tab_pend:
            df_p = cargar_tabla("prestamos")
            if not df_p.empty:
                df_p = df_p[df_p["cantidad_pendiente"] > 0]
                
                # FILTROS AVANZADOS
                with st.expander("🔎 Filtros de Búsqueda", expanded=True):
                    c1, c2 = st.columns(2)
                    with c1:
                        filtro_fecha = st.selectbox("📅 Periodo de Préstamo", ["Todos", "Hoy", "Esta Semana", "Este Mes"])
                    with c2:
                        filtro_clis = st.multiselect("👤 Clientes", sorted(df_p["cliente"].unique()))

                # APLICAR FILTROS
                df_show = df_p.copy()
                hoy = date.today()
                
                if filtro_fecha == "Hoy":
                    df_show = df_show[df_show["fecha_registro"] == hoy]
                elif filtro_fecha == "Esta Semana":
                    inicio = hoy - timedelta(days=hoy.weekday())
                    df_show = df_show[df_show["fecha_registro"] >= inicio]
                elif filtro_fecha == "Este Mes":
                    inicio = hoy.replace(day=1)
                    df_show = df_show[df_show["fecha_registro"] >= inicio]
                
                if filtro_clis:
                    df_show = df_show[df_show["cliente"].isin(filtro_clis)]
                
                # MOSTRAR TABLA
                st.dataframe(df_show, use_container_width=True)
                st.metric("Total Deuda en Pantalla", f"${df_show['total_pendiente'].sum():,.2f}")
                
                # GENERADOR DE RECIBO WHATSAPP
                st.divider()
                if not df_show.empty:
                    if st.button("🖨️ Generar Texto para WhatsApp"):
                        fecha_str = datetime.now().strftime("%d/%m/%Y")
                        txt = f"*ESTADO DE CUENTA - GRUPO KORIEL*\n📅 Fecha: {fecha_str}\n"
                        if filtro_fecha != "Todos": txt += f"⏳ Filtro: {filtro_fecha}\n"
                        txt += "--------------------------------\n"
                        
                        # Agrupar por cliente
                        clis = df_show["cliente"].unique()
                        for c in clis:
                            txt += f"👤 *{c}*:\n"
                            sub = df_show[df_show["cliente"] == c]
                            for i, r in sub.iterrows():
                                txt += f"   - {r['producto']} (x{r['cantidad_pendiente']}): ${r['total_pendiente']:,.2f}\n"
                        
                        txt += "--------------------------------\n"
                        txt += f"*💰 TOTAL PENDIENTE: ${df_show['total_pendiente'].sum():,.2f}*"
                        st.code(txt, language="text")

        # --- PESTAÑA HISTORIAL ---
        with tab_hist:
            df_h = cargar_tabla("historial")
            if not df_h.empty:
                # FILTROS
                c1, c2, c3 = st.columns(3)
                f_c = c1.multiselect("Cliente", sorted(df_h["cliente"].unique()))
                f_t = c2.multiselect("Tipo Movimiento", ["COBRO", "DEVOLUCION"])
                f_d = c3.date_input("Rango de Fechas", [date.today()-timedelta(days=30), date.today()])
                
                df_hs = df_h.copy()
                if f_c: df_hs = df_hs[df_hs["cliente"].isin(f_c)]
                if f_t: df_hs = df_hs[df_hs["tipo"].isin(f_t)]
                if len(f_d)==2: 
                    df_hs = df_hs[(df_hs["fecha_evento"].dt.date >= f_d[0]) & (df_hs["fecha_evento"].dt.date <= f_d[1])]
                
                # Seleccionar columnas limpias
                cols_ok = ["fecha_evento", "tipo", "cliente", "producto", "cantidad", "monto_operacion", "usuario_responsable"]
                cols_final = [x for x in cols_ok if x in df_hs.columns]
                
                st.dataframe(df_hs[cols_final].sort_values("fecha_evento", ascending=False), use_container_width=True)
                
                # Total cobrado en la selección
                cobrado_sel = df_hs[df_hs["tipo"]=="COBRO"]["monto_operacion"].sum()
                st.metric("Dinero Recaudado (Selección)", f"${cobrado_sel:,.2f}")

    # ==========================================
    # MÓDULO 4: REPORTES FINANCIEROS (FILTROS COMPLETOS)
    # ==========================================
    elif menu == "📊 Reportes Financieros":
        st.title("📊 Balance General")
        
        st.markdown("### 🔎 Filtros Globales")
        c1, c2 = st.columns(2)
        rep_cli = c1.multiselect("Clientes Específicos", sorted(df_cli["nombre"].unique()) if not df_cli.empty else [])
        rep_fec = c2.date_input("Periodo de Análisis (Ingresos)", [date.today().replace(day=1), date.today()])
        
        df_p = cargar_tabla("prestamos")
        df_h = cargar_tabla("historial")
        
        # Aplicar filtros
        if rep_cli:
            if not df_p.empty: df_p = df_p[df_p["cliente"].isin(rep_cli)]
            if not df_h.empty: df_h = df_h[df_h["cliente"].isin(rep_cli)]
        
        if not df_h.empty and len(rep_fec)==2:
            df_h = df_h[(df_h["fecha_evento"].dt.date >= rep_fec[0]) & (df_h["fecha_evento"].dt.date <= rep_fec[1])]
        
        st.divider()
        
        col_izq, col_der = st.columns(2)
        
        with col_izq:
            st.subheader("🔴 Capital en la Calle (Deuda)")
            if not df_p.empty:
                total_deuda = df_p["total_pendiente"].sum()
                st.metric("Total por Cobrar", f"${total_deuda:,.2f}")
                st.write("**Ranking de Deudores:**")
                st.dataframe(df_p.groupby("cliente")["total_pendiente"].sum().sort_values(ascending=False))
        
        with col_der:
            st.subheader("🟢 Ingresos Reales (Caja)")
            if not df_h.empty:
                cobros = df_h[df_h["tipo"]=="COBRO"]
                total_ingreso = cobros["monto_operacion"].sum()
                st.metric("Total Cobrado en Periodo", f"${total_ingreso:,.2f}")
                st.write("**Ranking de Pagadores:**")
                st.dataframe(cobros.groupby("cliente")["monto_operacion"].sum().sort_values(ascending=False))

    # ==========================================
    # MÓDULO 5: ADMINISTRACIÓN (FULL: RUC, BACKUP, EDIT)
    # ==========================================
    elif menu == "🛠️ Administración":
        st.title("🛠️ Administración del Sistema")
        
        # TABS ORGANIZADOS
        tab_new, tab_edit, tab_backup = st.tabs(["➕ Crear Maestros (Completo)", "✏️ Editar Datos", "💾 Copias de Seguridad (Backup)"])
        
        # --- TAB 1: CREAR (CON RUCS) ---
        with tab_new:
            c1, c2 = st.columns(2)
            with c1:
                st.markdown("#### Nuevo Cliente")
                with st.form("form_cli_full"):
                    nc = st.text_input("Nombre Completo *")
                    nt = st.text_input("Nombre Tienda")
                    ntel = st.text_input("Teléfono")
                    ndir = st.text_input("Dirección")
                    nruc1 = st.text_input("RUC Principal")
                    nruc2 = st.text_input("RUC Secundario (Opcional)")
                    
                    if st.form_submit_button("Guardar Cliente"):
                        if nc:
                            insertar_registro("clientes", {"nombre": nc, "tienda": nt, "telefono": ntel, "direccion": ndir, "ruc1": nruc1, "ruc2": nruc2})
                            st.success("Cliente Creado"); time.sleep(1); st.rerun()
                        else: st.error("Falta nombre")
            
            with c2:
                st.markdown("#### Nuevo Producto")
                with st.form("form_prod_full"):
                    np = st.text_input("Nombre Producto *")
                    nc = st.selectbox("Categoría", ["Iluminación", "Cables", "Herramientas", "Otros"])
                    np_base = st.number_input("Precio Base ($)", min_value=0.0)
                    
                    if st.form_submit_button("Guardar Producto"):
                        if np:
                            insertar_registro("productos", {"nombre": np, "categoria": nc, "precio_base": np_base})
                            st.success("Producto Creado"); time.sleep(1); st.rerun()

        # --- TAB 2: EDITAR ---
        with tab_edit:
            tipo_ed = st.radio("¿Qué deseas corregir?", ["Clientes", "Productos"], horizontal=True)
            
            if tipo_ed == "Clientes" and not df_cli.empty:
                s_cli = st.selectbox("Buscar Cliente a Editar", df_cli["nombre"].unique())
                d = df_cli[df_cli["nombre"]==s_cli].iloc[0]
                
                with st.form("edit_cli_form"):
                    en = st.text_input("Nombre", d["nombre"])
                    et = st.text_input("Tienda", d.get("tienda",""))
                    etel = st.text_input("Teléfono", d.get("telefono",""))
                    edir = st.text_input("Dirección", d.get("direccion",""))
                    er1 = st.text_input("RUC 1", d.get("ruc1",""))
                    er2 = st.text_input("RUC 2", d.get("ruc2",""))
                    
                    if st.form_submit_button("Actualizar Datos"):
                        editar_maestro("clientes", int(d["id"]), {"nombre": en, "tienda": et, "telefono": etel, "direccion": edir, "ruc1": er1, "ruc2": er2})
                        st.success("Datos actualizados"); time.sleep(1); st.rerun()
            
            elif tipo_ed == "Productos" and not df_prod.empty:
                s_prod = st.selectbox("Buscar Producto a Editar", df_prod["nombre"].unique())
                dp = df_prod[df_prod["nombre"]==s_prod].iloc[0]
                
                with st.form("edit_prod_form"):
                    epn = st.text_input("Nombre", dp["nombre"])
                    epp = st.number_input("Precio Base", float(dp["precio_base"]))
                    epc = st.text_input("Categoría", dp["categoria"])
                    
                    if st.form_submit_button("Actualizar Producto"):
                        editar_maestro("productos", int(dp["id"]), {"nombre": epn, "precio_base": epp, "categoria": epc})
                        st.success("Producto actualizado"); time.sleep(1); st.rerun()

        # --- TAB 3: BACKUP (DESCARGAS) ---
        with tab_backup:
            st.subheader("📥 Descarga Segura de Datos")
            st.info("Descarga tus datos en Excel (CSV) periódicamente como respaldo.")
            
            c1, c2 = st.columns(2)
            with c1:
                if not df_cli.empty:
                    csv_c = df_cli.to_csv(index=False).encode('utf-8')
                    st.download_button("👤 Descargar Clientes", data=csv_c, file_name="backup_clientes.csv", mime="text/csv")
                
                df_p_full = cargar_tabla("prestamos")
                if not df_p_full.empty:
                    csv_p = df_p_full.to_csv(index=False).encode('utf-8')
                    st.download_button("📦 Descargar Préstamos", data=csv_p, file_name="backup_prestamos.csv", mime="text/csv")
            
            with c2:
                df_h_full = cargar_tabla("historial")
                if not df_h_full.empty:
                    csv_h = df_h_full.to_csv(index=False).encode('utf-8')
                    st.download_button("📜 Descargar Historial", data=csv_h, file_name="backup_historial.csv", mime="text/csv")
                
                if not df_prod.empty:
                    csv_pr = df_prod.to_csv(index=False).encode('utf-8')
                    st.download_button("💡 Descargar Productos", data=csv_pr, file_name="backup_productos.csv", mime="text/csv")

# --- ARRANQUE ---
if check_login():
    main_app()