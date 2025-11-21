import streamlit as st
import pandas as pd
from supabase import create_client
from datetime import datetime, timedelta
import time

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Grupo Koriel ERP", page_icon="⚡", layout="wide")

# --- ESTILOS CSS ---
st.markdown("""
<style>
    [data-testid="stSidebarNav"] {display: none;}
    .stRadio > label {display: none;}
    div[data-testid="stMetricValue"] {font-size: 24px;}
</style>
""", unsafe_allow_html=True)

# --- CONEXIÓN SUPABASE ---
@st.cache_resource
def init_connection():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

supabase = init_connection()

# --- USUARIOS ---
USUARIOS = {
    "admin": "admin123",
    "jorge": "1234",
    "maria": "0000"
}

# --- FUNCIONES CRUD ---
def insertar_registro(tabla, datos):
    try:
        supabase.table(tabla).insert(datos).execute()
        return True
    except Exception as e:
        st.error(f"Error: {e}")
        return False

def cargar_tabla(tabla):
    try:
        response = supabase.table(tabla).select("*").execute()
        df = pd.DataFrame(response.data)
        # Convertir fechas a datetime si existen
        if "fecha_registro" in df.columns:
            df["fecha_registro"] = pd.to_datetime(df["fecha_registro"]).dt.date
        if "fecha_evento" in df.columns:
            df["fecha_evento"] = pd.to_datetime(df["fecha_evento"])
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
        st.error(f"Error actualizando: {e}")

def editar_maestro(tabla, id_row, datos_nuevos):
    try:
        supabase.table(tabla).update(datos_nuevos).eq("id", id_row).execute()
        return True
    except Exception as e:
        st.error(f"Error editando: {e}")
        return False

# --- LOGIN ---
def check_login():
    if "usuario_logueado" in st.session_state and st.session_state["usuario_logueado"]:
        return True
    st.session_state["usuario_logueado"] = None
    st.markdown("<h1 style='text-align: center;'>🔐 GRUPO KORIEL CLOUD</h1>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        user = st.text_input("Usuario")
        password = st.text_input("Contraseña", type="password")
        if st.button("Entrar", use_container_width=True, type="primary"):
            if user in USUARIOS and USUARIOS[user] == password:
                st.session_state["usuario_logueado"] = user
                st.rerun()
            else:
                st.error("Datos incorrectos")
    return False

def logout():
    st.session_state["usuario_logueado"] = None
    st.rerun()

# --- APP PRINCIPAL ---
def main_app():
    usuario_actual = st.session_state["usuario_logueado"]
    
    with st.sidebar:
        st.title("🏢 KORIEL CLOUD")
        st.write(f"👤 **{usuario_actual.upper()}**")
        st.divider()
        menu = st.radio("Menú", [
            "📦 Nuevo Préstamo", 
            "📍 Rutas y Cobro", 
            "🔍 Consultas y Recibos", 
            "📊 Reportes Financieros", 
            "🛠️ Administración"
        ])
        st.divider()
        if st.button("Cerrar Sesión"):
            logout()

    df_cli = cargar_tabla("clientes")
    df_prod = cargar_tabla("productos")

    # ==========================================
    # 1. NUEVO PRÉSTAMO (AGILE)
    # ==========================================
    if menu == "📦 Nuevo Préstamo":
        st.title("📦 Registrar Salida")
        lista_c = ["➕ CREAR NUEVO..."] + sorted(df_cli["nombre"].unique().tolist()) if not df_cli.empty else ["➕ CREAR NUEVO..."]
        lista_p = ["➕ CREAR NUEVO..."] + sorted(df_prod["nombre"].unique().tolist()) if not df_prod.empty else ["➕ CREAR NUEVO..."]

        with st.container():
            c1, c2 = st.columns(2)
            with c1:
                cli_sel = st.selectbox("Cliente", lista_c)
                cli_final = None; new_cli_n = None; new_cli_t = None
                if cli_sel == "➕ CREAR NUEVO...":
                    st.info("Alta Rápida Cliente")
                    new_cli_n = st.text_input("Nombre")
                    new_cli_t = st.text_input("Tienda")
                    cli_final = new_cli_n
                else: cli_final = cli_sel
            
            with c2:
                prod_sel = st.selectbox("Producto", lista_p)
                prod_final = None; pre_sug = 0.0
                if prod_sel == "➕ CREAR NUEVO...":
                    st.info("Alta Rápida Producto")
                    prod_final = st.text_input("Nombre Producto")
                else:
                    prod_final = prod_sel
                    if not df_prod.empty:
                        row = df_prod[df_prod["nombre"]==prod_sel]
                        if not row.empty: pre_sug = float(row.iloc[0]["precio_base"])

                cc1, cc2 = st.columns(2)
                cant = cc1.number_input("Cantidad", 1)
                precio = cc2.number_input("Precio ($)", value=pre_sug)

            if st.button("💾 GUARDAR", type="primary", use_container_width=True):
                if cli_final and prod_final:
                    if cli_sel == "➕ CREAR NUEVO...": insertar_registro("clientes", {"nombre": new_cli_n, "tienda": new_cli_t})
                    if prod_sel == "➕ CREAR NUEVO...": insertar_registro("productos", {"nombre": prod_final, "categoria": "Otros", "precio_base": precio})
                    
                    insertar_registro("prestamos", {
                        "fecha_registro": datetime.now().strftime("%Y-%m-%d"),
                        "usuario": usuario_actual,
                        "cliente": cli_final,
                        "producto": prod_final,
                        "cantidad_pendiente": cant,
                        "precio_unitario": precio,
                        "total_pendiente": cant*precio
                    })
                    st.success("Registrado!"); time.sleep(1); st.rerun()
                else: st.error("Faltan datos")

    # ==========================================
    # 2. RUTAS Y COBRO (CON COBRO FLASH)
    # ==========================================
    elif menu == "📍 Rutas y Cobro":
        st.title("📍 Cobranza")
        df_pend = cargar_tabla("prestamos")
        if not df_pend.empty: df_pend = df_pend[df_pend["cantidad_pendiente"] > 0]
        
        if df_pend.empty:
            st.success("✅ Nada pendiente.")
        else:
            cli_visita = st.selectbox("Cliente a Visitar:", sorted(df_pend["cliente"].unique()))
            
            # Info Cliente
            if not df_cli.empty:
                info = df_cli[df_cli["nombre"] == cli_visita]
                if not info.empty:
                    st.info(f"🏠 {info.iloc[0].get('tienda','-')} | 📍 {info.iloc[0].get('direccion','-')}")

            datos = df_pend[df_pend["cliente"] == cli_visita].copy()
            datos["Cobrar"], datos["Devolver"] = 0, 0
            
            # --- SECCIÓN COBRO FLASH ---
            col_flash, col_manual = st.columns([1, 2])
            with col_flash:
                st.markdown("#### ⚡ Opción Rápida")
                if st.button("💰 COBRAR TODO EL STOCK", type="primary", help="Marca TODO lo que tiene el cliente como Vendido y Cobrado"):
                    hoy = datetime.now().isoformat()
                    for i, r in datos.iterrows():
                        cant = int(r["cantidad_pendiente"])
                        monto = float(cant * r["precio_unitario"])
                        insertar_registro("historial", {"fecha_evento": hoy, "usuario_responsable": usuario_actual, "tipo": "COBRO", "cliente": cli_visita, "producto": r["producto"], "cantidad": cant, "monto_operacion": monto})
                        actualizar_prestamo(r["id"], 0, 0)
                    st.toast("✅ ¡Cobro Total Realizado!"); time.sleep(1); st.rerun()

            with col_manual:
                st.markdown("#### 📝 Cobro Parcial / Devolución")
                edited = st.data_editor(
                    datos[["id", "producto", "cantidad_pendiente", "precio_unitario", "Cobrar", "Devolver"]],
                    column_config={
                        "id": st.column_config.NumberColumn(disabled=True),
                        "cantidad_pendiente": st.column_config.NumberColumn("En Tienda", disabled=True),
                        "precio_unitario": st.column_config.NumberColumn("Precio", format="$%.2f", disabled=True),
                        "Cobrar": st.column_config.NumberColumn("Vendido", min_value=0),
                        "Devolver": st.column_config.NumberColumn("Regresa", min_value=0)
                    },
                    hide_index=True, key="edit_cob"
                )
                if st.button("✅ Procesar Manual"):
                    hoy = datetime.now().isoformat()
                    proc = False
                    for i, r in edited.iterrows():
                        v, d = r["Cobrar"], r["Devolver"]
                        if v > 0 or d > 0:
                            proc = True
                            if v > 0: insertar_registro("historial", {"fecha_evento": hoy, "usuario_responsable": usuario_actual, "tipo": "COBRO", "cliente": cli_visita, "producto": r["producto"], "cantidad": int(v), "monto_operacion": float(v*r["precio_unitario"])})
                            if d > 0: insertar_registro("historial", {"fecha_evento": hoy, "usuario_responsable": usuario_actual, "tipo": "DEVOLUCION", "cliente": cli_visita, "producto": r["producto"], "cantidad": int(d), "monto_operacion": 0})
                            actualizar_prestamo(r["id"], int(r["cantidad_pendiente"]-v-d), float((r["cantidad_pendiente"]-v-d)*r["precio_unitario"]))
                    if proc: st.toast("Procesado"); time.sleep(1); st.rerun()

    # ==========================================
    # 3. CONSULTAS Y RECIBOS (NUEVO MODULO)
    # ==========================================
    elif menu == "🔍 Consultas y Recibos":
        st.title("🔍 Consultas y Recibos")
        
        tab_pend, tab_hist = st.tabs(["📂 Pendientes de Cobro", "📜 Historial (Pagado/Devuelto)"])
        
        # --- PENDIENTES ---
        with tab_pend:
            st.subheader("Filtro de Deudas")
            df_p = cargar_tabla("prestamos")
            if not df_p.empty:
                df_p = df_p[df_p["cantidad_pendiente"] > 0] # Solo lo activo
                
                # Filtros
                c1, c2 = st.columns(2)
                filtro_cli = c1.multiselect("Filtrar por Cliente", df_p["cliente"].unique())
                
                df_show = df_p if not filtro_cli else df_p[df_p["cliente"].isin(filtro_cli)]
                
                st.dataframe(df_show, use_container_width=True)
                st.metric("Total Deuda en Pantalla", f"${df_show['total_pendiente'].sum():,.2f}")
                
                st.divider()
                st.subheader("🖨️ Generador de Recibos")
                if len(filtro_cli) == 1:
                    cliente_recibo = filtro_cli[0]
                    datos_recibo = df_show[df_show["cliente"] == cliente_recibo]
                    
                    st.caption("Copia y pega esto en WhatsApp:")
                    fecha_hoy = datetime.now().strftime("%d/%m/%Y")
                    texto_recibo = f"*ESTADO DE CUENTA - GRUPO KORIEL*\n"
                    texto_recibo += f"📅 Fecha: {fecha_hoy}\n"
                    texto_recibo += f"👤 Cliente: {cliente_recibo}\n"
                    texto_recibo += "--------------------------------\n"
                    total = 0
                    for i, r in datos_recibo.iterrows():
                        sub = r['cantidad_pendiente'] * r['precio_unitario']
                        total += sub
                        texto_recibo += f"▫️ {r['producto']} (x{r['cantidad_pendiente']}) - ${sub:,.2f}\n"
                    texto_recibo += "--------------------------------\n"
                    texto_recibo += f"*💰 TOTAL A PAGAR: ${total:,.2f}*"
                    
                    st.code(texto_recibo, language="text")
                else:
                    st.info("Selecciona UN solo cliente arriba para generar su recibo detallado.")

        # --- HISTORIAL ---
        with tab_hist:
            st.subheader("Historial de Movimientos")
            df_h = cargar_tabla("historial")
            if not df_h.empty:
                # Filtro de Fechas
                c1, c2 = st.columns(2)
                fecha_inicio = c1.date_input("Desde", datetime.now() - timedelta(days=7))
                fecha_fin = c2.date_input("Hasta", datetime.now())
                
                # Convertir a datetime para filtrar
                mask = (df_h['fecha_evento'].dt.date >= fecha_inicio) & (df_h['fecha_evento'].dt.date <= fecha_fin)
                df_h_filtrado = df_h.loc[mask]
                
                st.dataframe(df_h_filtrado.sort_values("fecha_evento", ascending=False), use_container_width=True)
                
                st.metric("Dinero Recaudado en este periodo", f"${df_h_filtrado[df_h_filtrado['tipo']=='COBRO']['monto_operacion'].sum():,.2f}")

    # ==========================================
    # 4. REPORTES FINANCIEROS (MEJORADO)
    # ==========================================
    elif menu == "📊 Reportes Financieros":
        st.title("📊 Balance General")
        
        df_p = cargar_tabla("prestamos")
        df_h = cargar_tabla("historial")
        
        c1, c2 = st.columns(2)
        
        with c1:
            st.subheader("🔴 Por Cobrar (En Calle)")
            if not df_p.empty:
                deuda_total = df_p["total_pendiente"].sum()
                st.metric("Capital Pendiente", f"${deuda_total:,.2f}")
                
                # Top Deudores
                deuda_por_cli = df_p.groupby("cliente")["total_pendiente"].sum().sort_values(ascending=False).head(5)
                st.write("**Top 5 Clientes que más deben:**")
                st.dataframe(deuda_por_cli)
        
        with c2:
            st.subheader("🟢 Ingresos Reales (Cobrado)")
            if not df_h.empty:
                cobros = df_h[df_h["tipo"]=="COBRO"]
                ganancia_total = cobros["monto_operacion"].sum()
                st.metric("Total Cobrado (Histórico)", f"${ganancia_total:,.2f}")
                
                # Top Productos
                prod_top = cobros.groupby("producto")["cantidad"].sum().sort_values(ascending=False).head(5)
                st.write("**Top 5 Productos más vendidos:**")
                st.dataframe(prod_top)

    # ==========================================
    # 5. ADMINISTRACIÓN Y CORRECCIÓN
    # ==========================================
    elif menu == "🛠️ Administración":
        st.title("🛠️ Administración")
        
        tab1, tab2 = st.tabs(["📝 Editar Datos Maestros", "➕ Crear Nuevos"])
        
        with tab1:
            st.info("Aquí puedes corregir nombres o precios si te equivocaste.")
            tipo_edit = st.radio("¿Qué quieres editar?", ["Clientes", "Productos"], horizontal=True)
            
            if tipo_edit == "Clientes":
                if not df_cli.empty:
                    cli_a_editar = st.selectbox("Buscar Cliente a Corregir", df_cli["nombre"].unique())
                    datos_c = df_cli[df_cli["nombre"]==cli_a_editar].iloc[0]
                    
                    with st.expander("✏️ Editar Datos del Cliente", expanded=True):
                        new_n = st.text_input("Nombre", value=datos_c["nombre"])
                        new_t = st.text_input("Tienda", value=datos_c["tienda"])
                        new_tel = st.text_input("Teléfono", value=datos_c["telefono"])
                        new_d = st.text_input("Dirección", value=datos_c["direccion"])
                        
                        if st.button("Actualizar Cliente"):
                            editar_maestro("clientes", int(datos_c["id"]), {"nombre": new_n, "tienda": new_t, "telefono": new_tel, "direccion": new_d})
                            st.success("Actualizado!"); time.sleep(1); st.rerun()
            
            elif tipo_edit == "Productos":
                if not df_prod.empty:
                    prod_a_editar = st.selectbox("Buscar Producto a Corregir", df_prod["nombre"].unique())
                    datos_p = df_prod[df_prod["nombre"]==prod_a_editar].iloc[0]
                    
                    with st.expander("✏️ Editar Datos del Producto", expanded=True):
                        new_np = st.text_input("Nombre", value=datos_p["nombre"])
                        new_pp = st.number_input("Precio Base", value=float(datos_p["precio_base"]))
                        new_cat = st.text_input("Categoría", value=datos_p["categoria"])
                        
                        if st.button("Actualizar Producto"):
                            editar_maestro("productos", int(datos_p["id"]), {"nombre": new_np, "precio_base": new_pp, "categoria": new_cat})
                            st.success("Actualizado!"); time.sleep(1); st.rerun()

        with tab2:
            st.write("Usa el alta rápida en 'Nuevo Préstamo' o crea aquí:")
            with st.form("new_m"):
                st.write("Crear Cliente Manual")
                n=st.text_input("Nombre"); t=st.text_input("Tienda")
                if st.form_submit_button("Crear"):
                    insertar_registro("clientes", {"nombre":n, "tienda":t})
                    st.rerun()

# --- INICIO ---
if check_login():
    main_app()