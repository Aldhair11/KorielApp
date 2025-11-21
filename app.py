import streamlit as st
import pandas as pd
from supabase import create_client
from datetime import datetime, timedelta, date
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
        # Limpieza de fechas
        if "fecha_registro" in df.columns:
            df["fecha_registro"] = pd.to_datetime(df["fecha_registro"]).dt.date
        if "fecha_evento" in df.columns:
            df["fecha_evento"] = pd.to_datetime(df["fecha_evento"]) # Mantenemos hora para orden, quitamos al mostrar
        # Eliminar created_at si existe (para limpieza visual)
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
    # 1. NUEVO PRÉSTAMO (SIN CAMBIOS, FUNCIONA BIEN)
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
    # 2. RUTAS Y COBRO (CORREGIDO MODULO 1)
    # ==========================================
    elif menu == "📍 Rutas y Cobro":
        st.title("📍 Cobranza")
        df_pend = cargar_tabla("prestamos")
        if not df_pend.empty: df_pend = df_pend[df_pend["cantidad_pendiente"] > 0]
        
        if df_pend.empty:
            st.success("✅ Nada pendiente.")
        else:
            cli_visita = st.selectbox("Cliente a Visitar:", sorted(df_pend["cliente"].unique()))
            
            # 1. Info Cliente y DEUDA TOTAL
            datos = df_pend[df_pend["cliente"] == cli_visita].copy()
            deuda_total_cliente = datos["total_pendiente"].sum()
            
            col_info, col_deuda = st.columns([3, 1])
            with col_info:
                if not df_cli.empty:
                    info = df_cli[df_cli["nombre"] == cli_visita]
                    if not info.empty:
                        r = info.iloc[0]
                        st.info(f"🏠 {r.get('tienda','-')} | 📍 {r.get('direccion','-')} | 📞 {r.get('telefono','-')}")
            with col_deuda:
                st.metric("DEUDA TOTAL", f"${deuda_total_cliente:,.2f}")

            # Preparamos la tabla
            datos["Cobrar"] = 0
            datos["Devolver"] = 0
            
            # 2. Botones de Acción Rápida (Cobrar Todo / Devolver Todo)
            col_flash1, col_flash2 = st.columns(2)
            with col_flash1:
                if st.button("💰 COBRAR TODO (Pagó 100%)", type="primary", use_container_width=True):
                    hoy = datetime.now().isoformat()
                    for i, r in datos.iterrows():
                        cant = int(r["cantidad_pendiente"])
                        monto = float(cant * r["precio_unitario"])
                        insertar_registro("historial", {"fecha_evento": hoy, "usuario_responsable": usuario_actual, "tipo": "COBRO", "cliente": cli_visita, "producto": r["producto"], "cantidad": cant, "monto_operacion": monto})
                        actualizar_prestamo(r["id"], 0, 0)
                    st.toast("✅ ¡Cobro Total!"); time.sleep(1); st.rerun()
            
            with col_flash2:
                # NUEVO BOTON PEDIDO: DEVOLVER TODO
                if st.button("🔙 DEVOLVER TODO (No vendió nada)", type="secondary", use_container_width=True):
                    hoy = datetime.now().isoformat()
                    for i, r in datos.iterrows():
                        cant = int(r["cantidad_pendiente"])
                        insertar_registro("historial", {"fecha_evento": hoy, "usuario_responsable": usuario_actual, "tipo": "DEVOLUCION", "cliente": cli_visita, "producto": r["producto"], "cantidad": cant, "monto_operacion": 0})
                        actualizar_prestamo(r["id"], 0, 0)
                    st.toast("✅ ¡Todo Devuelto!"); time.sleep(1); st.rerun()

            st.markdown("---")
            st.write("##### 📝 Gestión Manual (Parciales)")
            
            # 3. Tabla Editable Manual
            edited = st.data_editor(
                datos[["id", "producto", "cantidad_pendiente", "precio_unitario", "Cobrar", "Devolver"]],
                column_config={
                    "id": st.column_config.NumberColumn(disabled=True),
                    "cantidad_pendiente": st.column_config.NumberColumn("En Tienda", disabled=True),
                    "precio_unitario": st.column_config.NumberColumn("Precio", format="$%.2f", disabled=True),
                    "Cobrar": st.column_config.NumberColumn("Pagó (Und)", min_value=0),
                    "Devolver": st.column_config.NumberColumn("Devuelve (Und)", min_value=0)
                },
                hide_index=True, key="edit_cob"
            )
            
            # Cálculo Dinámico del Total a Pagar en ese momento
            total_a_pagar_ahora = (edited["Cobrar"] * edited["precio_unitario"]).sum()
            
            c_conf1, c_conf2 = st.columns([2, 1])
            with c_conf1:
                 if total_a_pagar_ahora > 0:
                    st.success(f"💵 CLIENTE ESTÁ PAGANDO AHORA: **${total_a_pagar_ahora:,.2f}**")
            with c_conf2:
                if st.button("✅ Procesar Manual", use_container_width=True):
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
    # 3. CONSULTAS Y RECIBOS (CORREGIDO MODULO 2)
    # ==========================================
    elif menu == "🔍 Consultas y Recibos":
        st.title("🔍 Consultas y Recibos")
        
        tab_pend, tab_hist = st.tabs(["📂 Pendientes de Cobro", "📜 Historial"])
        
        # --- PENDIENTES (FILTROS MEJORADOS) ---
        with tab_pend:
            st.subheader("Pendientes de Cobro")
            df_p = cargar_tabla("prestamos")
            if not df_p.empty:
                df_p = df_p[df_p["cantidad_pendiente"] > 0]
                
                # FILTROS: TIEMPO Y CLIENTE
                col_f1, col_f2 = st.columns(2)
                with col_f1:
                    filtro_tiempo = st.selectbox("Filtrar por Fecha de Préstamo", ["Todos", "Hoy", "Esta Semana", "Este Mes"])
                with col_f2:
                    filtro_cli = st.multiselect("Filtrar por Cliente", sorted(df_p["cliente"].unique()))

                # Lógica de filtrado
                df_show = df_p.copy()
                
                # Filtro Tiempo
                hoy = date.today()
                if filtro_tiempo == "Hoy":
                    df_show = df_show[df_show["fecha_registro"] == hoy]
                elif filtro_tiempo == "Esta Semana":
                    inicio_semana = hoy - timedelta(days=hoy.weekday())
                    df_show = df_show[df_show["fecha_registro"] >= inicio_semana]
                elif filtro_tiempo == "Este Mes":
                    inicio_mes = hoy.replace(day=1)
                    df_show = df_show[df_show["fecha_registro"] >= inicio_mes]

                # Filtro Cliente
                if filtro_cli:
                    df_show = df_show[df_show["cliente"].isin(filtro_cli)]
                
                # Mostrar Tabla Limpia (Sin created_at)
                st.dataframe(df_show, use_container_width=True)
                st.metric("Total Deuda Filtrada", f"${df_show['total_pendiente'].sum():,.2f}")
                
                # Generador de Recibo
                st.divider()
                if not df_show.empty:
                    if st.button("🖨️ Generar Recibo de lo Filtrado"):
                        fecha_str = datetime.now().strftime("%d/%m/%Y")
                        texto = f"*REPORTE DE PENDIENTES - GRUPO KORIEL*\n📅 Fecha: {fecha_str}\n"
                        if filtro_tiempo != "Todos": texto += f"⏳ Periodo: {filtro_tiempo}\n"
                        texto += "--------------------------------\n"
                        
                        # Agrupar por cliente para el recibo
                        for cli in df_show["cliente"].unique():
                            texto += f"👤 *{cli}*:\n"
                            sub_df = df_show[df_show["cliente"] == cli]
                            for idx, row in sub_df.iterrows():
                                texto += f"   - {row['producto']} (x{row['cantidad_pendiente']}): ${row['total_pendiente']:,.2f}\n"
                        
                        texto += "--------------------------------\n"
                        texto += f"*💰 DEUDA TOTAL FILTRADA: ${df_show['total_pendiente'].sum():,.2f}*"
                        st.code(texto, language="text")

        # --- HISTORIAL (FILTROS MEJORADOS) ---
        with tab_hist:
            st.subheader("Historial de Movimientos")
            df_h = cargar_tabla("historial")
            if not df_h.empty:
                # Filtros Combinados
                c1, c2, c3 = st.columns(3)
                with c1:
                    f_cli_h = st.multiselect("Cliente", sorted(df_h["cliente"].unique()))
                with c2:
                    f_tipo_h = st.multiselect("Tipo", ["COBRO", "DEVOLUCION"])
                with c3:
                    f_fecha_h = st.date_input("Fecha (Desde - Hasta)", [date.today() - timedelta(days=30), date.today()])

                # Aplicar Filtros
                df_h_show = df_h.copy()
                if f_cli_h: df_h_show = df_h_show[df_h_show["cliente"].isin(f_cli_h)]
                if f_tipo_h: df_h_show = df_h_show[df_h_show["tipo"].isin(f_tipo_h)]
                
                # Filtro Fecha (Rango)
                if len(f_fecha_h) == 2:
                    df_h_show = df_h_show[(df_h_show["fecha_evento"].dt.date >= f_fecha_h[0]) & (df_h_show["fecha_evento"].dt.date <= f_fecha_h[1])]

                # Tabla (Sin created_at, solo fecha evento)
                cols_ver = ["fecha_evento", "tipo", "cliente", "producto", "cantidad", "monto_operacion", "usuario_responsable"]
                # Solo mostramos columnas que existan
                cols_final = [c for c in cols_ver if c in df_h_show.columns]
                
                st.dataframe(df_h_show[cols_final].sort_values("fecha_evento", ascending=False), use_container_width=True)

    # ==========================================
    # 4. REPORTES FINANCIEROS (CORREGIDO MODULO 3)
    # ==========================================
    elif menu == "📊 Reportes Financieros":
        st.title("📊 Balance General")
        
        # Filtros Globales para el Reporte
        st.markdown("### 🔍 Filtros de Reporte")
        c_rep1, c_rep2 = st.columns(2)
        f_rep_cli = c_rep1.multiselect("Filtrar Clientes Específicos", sorted(df_cli["nombre"].unique()) if not df_cli.empty else [])
        f_rep_fecha = c_rep2.date_input("Rango de Fechas (Para Ingresos)", [date.today() - timedelta(days=30), date.today()])

        df_p = cargar_tabla("prestamos")
        df_h = cargar_tabla("historial")
        
        # Aplicar filtros
        if f_rep_cli:
            if not df_p.empty: df_p = df_p[df_p["cliente"].isin(f_rep_cli)]
            if not df_h.empty: df_h = df_h[df_h["cliente"].isin(f_rep_cli)]
        
        if not df_h.empty and len(f_rep_fecha) == 2:
             df_h = df_h[(df_h["fecha_evento"].dt.date >= f_rep_fecha[0]) & (df_h["fecha_evento"].dt.date <= f_rep_fecha[1])]

        st.divider()

        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("🔴 Deuda Pendiente (Actual)")
            if not df_p.empty:
                deuda_total = df_p["total_pendiente"].sum()
                st.metric("Total por Cobrar", f"${deuda_total:,.2f}")
                st.dataframe(df_p.groupby("cliente")["total_pendiente"].sum().sort_values(ascending=False))
        
        with col2:
            st.subheader("🟢 Ingresos (En el periodo)")
            if not df_h.empty:
                cobros = df_h[df_h["tipo"]=="COBRO"]
                ganancia = cobros["monto_operacion"].sum()
                st.metric("Total Recaudado", f"${ganancia:,.2f}")
                st.dataframe(cobros.groupby("cliente")["monto_operacion"].sum().sort_values(ascending=False))

    # ==========================================
    # 5. ADMINISTRACIÓN (CORREGIDO MODULO 4)
    # ==========================================
    elif menu == "🛠️ Administración":
        st.title("🛠️ Administración")
        
        # CAMBIO ORDEN TABS: Crear primero, Editar después
        tab_crear, tab_edit = st.tabs(["➕ Crear Nuevos (Maestros)", "✏️ Editar Existentes"])
        
        with tab_crear:
            c1, c2 = st.columns(2)
            
            # CREAR CLIENTE COMPLETO
            with c1:
                st.subheader("Nuevo Cliente")
                with st.form("new_cli_full"):
                    nc = st.text_input("Nombre Completo *")
                    nt = st.text_input("Nombre Tienda")
                    ntel = st.text_input("Teléfono / Celular")
                    ndir = st.text_input("Dirección")
                    nruc1 = st.text_input("RUC Principal") # NUEVO
                    nruc2 = st.text_input("RUC Secundario (Opcional)") # NUEVO
                    
                    if st.form_submit_button("Guardar Cliente"):
                        if nc:
                            insertar_registro("clientes", {
                                "nombre": nc, "tienda": nt, "telefono": ntel, "direccion": ndir, 
                                "ruc1": nruc1, "ruc2": nruc2
                            })
                            st.success("Cliente Guardado"); time.sleep(1); st.rerun()
                        else: st.error("Nombre obligatorio")

            # CREAR PRODUCTO (AÑADIDO DE NUEVO)
            with c2:
                st.subheader("Nuevo Producto")
                with st.form("new_prod_full"):
                    np = st.text_input("Nombre Producto *")
                    ncat = st.selectbox("Categoría", ["Iluminación", "Cables", "Herramientas", "Interruptores", "Otros"])
                    npre = st.number_input("Precio Base ($)", min_value=0.0)
                    
                    if st.form_submit_button("Guardar Producto"):
                        if np:
                            insertar_registro("productos", {"nombre": np, "categoria": ncat, "precio_base": npre})
                            st.success("Producto Guardado"); time.sleep(1); st.rerun()
                        else: st.error("Nombre obligatorio")

        with tab_edit:
            st.info("Busca y corrige datos erróneos.")
            tipo = st.radio("Editar:", ["Clientes", "Productos"], horizontal=True)
            
            if tipo == "Clientes" and not df_cli.empty:
                edit_c = st.selectbox("Buscar Cliente", df_cli["nombre"].unique())
                dat = df_cli[df_cli["nombre"]==edit_c].iloc[0]
                with st.form("edit_c_f"):
                    en = st.text_input("Nombre", value=dat["nombre"])
                    et = st.text_input("Tienda", value=dat.get("tienda",""))
                    etel = st.text_input("Tel", value=dat.get("telefono",""))
                    edir = st.text_input("Dir", value=dat.get("direccion",""))
                    eruc1 = st.text_input("RUC 1", value=dat.get("ruc1",""))
                    eruc2 = st.text_input("RUC 2", value=dat.get("ruc2",""))
                    
                    if st.form_submit_button("Actualizar"):
                        editar_maestro("clientes", int(dat["id"]), {"nombre":en, "tienda":et, "telefono":etel, "direccion":edir, "ruc1":eruc1, "ruc2":eruc2})
                        st.success("Actualizado"); time.sleep(1); st.rerun()
            
            elif tipo == "Productos" and not df_prod.empty:
                edit_p = st.selectbox("Buscar Producto", df_prod["nombre"].unique())
                datp = df_prod[df_prod["nombre"]==edit_p].iloc[0]
                with st.form("edit_p_f"):
                    epn = st.text_input("Nombre", value=datp["nombre"])
                    epp = st.number_input("Precio", value=float(datp["precio_base"]))
                    epc = st.text_input("Cat", value=datp["categoria"])
                    if st.form_submit_button("Actualizar"):
                        editar_maestro("productos", int(datp["id"]), {"nombre":epn, "precio_base":epp, "categoria":epc})
                        st.success("Actualizado"); time.sleep(1); st.rerun()

# --- INICIO ---
if check_login():
    main_app()