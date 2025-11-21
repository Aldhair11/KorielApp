import streamlit as st
import pandas as pd
from supabase import create_client
from datetime import datetime
import time

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Grupo Koriel ERP", page_icon="⚡", layout="wide")

# --- ESTILOS CSS ---
st.markdown("""
<style>
    [data-testid="stSidebarNav"] {display: none;}
    .stRadio > label {display: none;}
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

# --- FUNCIONES DE DATOS ---
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
        return pd.DataFrame(response.data)
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
        
        if st.button("Iniciar Sesión", use_container_width=True, type="primary"):
            if user in USUARIOS and USUARIOS[user] == password:
                st.session_state["usuario_logueado"] = user
                st.rerun()
            else:
                st.error("Credenciales incorrectas")
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
        # CAMBIO 1: Reordenamos el menú para que "Nuevo Préstamo" sea el primero (index 0)
        menu = st.radio("Menú Principal", ["📦 Nuevo Préstamo", "📍 Rutas y Cobro", "🛠️ Administración", "📊 Reportes"])
        st.divider()
        if st.button("Cerrar Sesión"):
            logout()

    # Carga de datos
    df_cli = cargar_tabla("clientes")
    df_prod = cargar_tabla("productos")

    # ==================================================
    # 📦 SECCIÓN: NUEVO PRÉSTAMO (PANTALLA PRINCIPAL)
    # ==================================================
    if menu == "📦 Nuevo Préstamo":
        st.title("📦 Registrar Salida (Rápida)")
        
        # Preparamos listas con opción de CREAR NUEVO al principio
        lista_clientes = ["➕ CREAR NUEVO CLIENTE..."] + sorted(df_cli["nombre"].unique().tolist()) if not df_cli.empty else ["➕ CREAR NUEVO CLIENTE..."]
        lista_productos = ["➕ CREAR NUEVO PRODUCTO..."] + sorted(df_prod["nombre"].unique().tolist()) if not df_prod.empty else ["➕ CREAR NUEVO PRODUCTO..."]

        with st.container(): # Contenedor para agrupar visualmente
            c1, c2 = st.columns(2)
            
            # --- COLUMNA 1: CLIENTE ---
            with c1:
                st.subheader("1. ¿A quién?")
                # El selectbox permite escribir para buscar
                cliente_seleccion = st.selectbox("Buscar Cliente", lista_clientes, help="Escribe para buscar")
                
                cliente_final = None
                nuevo_cliente_nombre = None
                nuevo_cliente_tienda = None
                
                # Lógica de Alta Rápida Cliente
                if cliente_seleccion == "➕ CREAR NUEVO CLIENTE...":
                    st.info("⚡ Alta Rápida de Cliente")
                    nuevo_cliente_nombre = st.text_input("Nombre del Cliente Nuevo")
                    nuevo_cliente_tienda = st.text_input("Nombre de su Tienda (Opcional)")
                    cliente_final = nuevo_cliente_nombre # Se usará este nombre
                else:
                    cliente_final = cliente_seleccion
            
            # --- COLUMNA 2: PRODUCTO Y PRECIO ---
            with c2:
                st.subheader("2. ¿Qué lleva?")
                producto_seleccion = st.selectbox("Buscar Producto", lista_productos, help="Escribe para buscar")
                
                producto_final = None
                precio_final = 0.0
                es_producto_nuevo = False
                
                # Lógica de Alta Rápida Producto
                if producto_seleccion == "➕ CREAR NUEVO PRODUCTO...":
                    st.info("⚡ Alta Rápida de Producto")
                    producto_final = st.text_input("Nombre del Producto Nuevo")
                    es_producto_nuevo = True
                    # Si es nuevo, el precio empieza en 0 para que tú lo pongas
                    precio_sugerido = 0.0
                else:
                    producto_final = producto_seleccion
                    # Si existe, buscamos su precio base
                    precio_sugerido = 0.0
                    if not df_prod.empty:
                        fila = df_prod[df_prod["nombre"] == producto_seleccion]
                        if not fila.empty:
                            precio_sugerido = float(fila.iloc[0]["precio_base"])

                # Inputs numéricos
                col_cant, col_prec = st.columns(2)
                with col_cant:
                    cantidad = st.number_input("Cantidad", min_value=1, value=1)
                with col_prec:
                    # El usuario puede editar el precio siempre
                    precio_final = st.number_input("Precio Unitario ($)", min_value=0.0, value=precio_sugerido, step=0.5)
            
            st.markdown("---")
            
            # --- BOTÓN DE GUARDADO INTELIGENTE ---
            # Calculamos total visualmente
            total_operacion = cantidad * precio_final
            st.metric("Total Estimado", f"${total_operacion:,.2f}")
            
            if st.button("💾 GUARDAR PRÉSTAMO", type="primary", use_container_width=True):
                error_validacion = False
                
                # 1. Validaciones
                if not cliente_final:
                    st.error("Falta el nombre del cliente.")
                    error_validacion = True
                if not producto_final:
                    st.error("Falta el nombre del producto.")
                    error_validacion = True
                    
                if not error_validacion:
                    exito_maestros = True
                    
                    # 2. Crear Cliente si es nuevo
                    if cliente_seleccion == "➕ CREAR NUEVO CLIENTE...":
                        exito_cli = insertar_registro("clientes", {
                            "nombre": nuevo_cliente_nombre,
                            "tienda": nuevo_cliente_tienda if nuevo_cliente_tienda else "Sin registrar",
                            "telefono": "", 
                            "direccion": ""
                        })
                        if not exito_cli: exito_maestros = False
                    
                    # 3. Crear Producto si es nuevo
                    if producto_seleccion == "➕ CREAR NUEVO PRODUCTO...":
                        exito_prod = insertar_registro("productos", {
                            "nombre": producto_final,
                            "categoria": "Otros", # Categoría automática como pediste
                            "precio_base": precio_final # Guardamos este precio como base futura
                        })
                        if not exito_prod: exito_maestros = False
                        
                    # 4. Guardar el Préstamo
                    if exito_maestros:
                        insertar_registro("prestamos", {
                            "fecha_registro": datetime.now().strftime("%Y-%m-%d"),
                            "usuario": usuario_actual,
                            "cliente": cliente_final,
                            "producto": producto_final,
                            "cantidad_pendiente": cantidad,
                            "precio_unitario": precio_final,
                            "total_pendiente": total_operacion
                        })
                        st.success(f"✅ ¡Listo! {producto_final} asignado a {cliente_final}.")
                        time.sleep(1.5)
                        st.rerun()
                    else:
                        st.error("Hubo un error creando el cliente o producto nuevo.")

    # ==================================================
    # 📍 SECCIÓN: RUTAS Y COBRO
    # ==================================================
    elif menu == "📍 Rutas y Cobro":
        st.title("📍 Gestión de Cobranza")
        df_pend = cargar_tabla("prestamos")
        
        if not df_pend.empty:
            df_pend = df_pend[df_pend["cantidad_pendiente"] > 0]
            if df_pend.empty:
                st.success("✅ Todo al día.")
            else:
                lista_clientes = sorted(df_pend["cliente"].unique())
                sel_cliente = st.selectbox("Cliente a Visitar:", lista_clientes)
                
                if not df_cli.empty:
                    info = df_cli[df_cli["nombre"] == sel_cliente]
                    if not info.empty:
                        r = info.iloc[0]
                        st.info(f"🏠 {r.get('tienda','-')} | 📍 {r.get('direccion','-')}")

                datos_cliente = df_pend[df_pend["cliente"] == sel_cliente].copy()
                datos_cliente["Cobrar"] = 0
                datos_cliente["Devolver"] = 0
                
                edited = st.data_editor(
                    datos_cliente[["id", "producto", "cantidad_pendiente", "precio_unitario", "Cobrar", "Devolver"]],
                    column_config={
                        "id": st.column_config.NumberColumn(disabled=True),
                        "cantidad_pendiente": st.column_config.NumberColumn("Stock", disabled=True),
                        "precio_unitario": st.column_config.NumberColumn("Precio", format="$%.2f", disabled=True),
                        "Cobrar": st.column_config.NumberColumn(min_value=0),
                        "Devolver": st.column_config.NumberColumn(min_value=0)
                    },
                    hide_index=True,
                    key="editor_cobro"
                )
                
                if st.button("✅ Confirmar Movimiento", type="primary"):
                    hoy = datetime.now().isoformat()
                    procesado = False
                    for i, r in edited.iterrows():
                        v, d = r["Cobrar"], r["Devolver"]
                        if v > 0 or d > 0:
                            procesado = True
                            if v > 0: insertar_registro("historial", {"fecha_evento": hoy, "usuario_responsable": usuario_actual, "tipo": "COBRO", "cliente": sel_cliente, "producto": r["producto"], "cantidad": int(v), "monto_operacion": float(v*r["precio_unitario"])})
                            if d > 0: insertar_registro("historial", {"fecha_evento": hoy, "usuario_responsable": usuario_actual, "tipo": "DEVOLUCION", "cliente": sel_cliente, "producto": r["producto"], "cantidad": int(d), "monto_operacion": 0})
                            actualizar_prestamo(r["id"], int(r["cantidad_pendiente"] - v - d), float((r["cantidad_pendiente"] - v - d) * r["precio_unitario"]))
                    
                    if procesado:
                        st.toast("Guardado")
                        time.sleep(1)
                        st.rerun()

    # ==================================================
    # 🛠️ SECCIÓN: ADMINISTRACIÓN
    # ==================================================
    elif menu == "🛠️ Administración":
        st.title("🛠️ Maestros")
        tab1, tab2 = st.tabs(["Clientes", "Productos"])
        
        with tab1:
            with st.form("fc"):
                n = st.text_input("Nombre"); t = st.text_input("Tienda"); tel = st.text_input("Tel"); d = st.text_input("Dir")
                if st.form_submit_button("Crear"):
                    if n: insertar_registro("clientes", {"nombre": n, "tienda": t, "telefono": tel, "direccion": d}); st.rerun()
            st.dataframe(df_cli)
            
        with tab2:
            with st.form("fp"):
                n = st.text_input("Prod"); c = st.selectbox("Cat", ["Varios", "Cables", "Focos"]); p = st.number_input("Precio")
                if st.form_submit_button("Crear"):
                    if n: insertar_registro("productos", {"nombre": n, "categoria": c, "precio_base": p}); st.rerun()
            st.dataframe(df_prod)

    # ==================================================
    # 📊 SECCIÓN: REPORTES
    # ==================================================
    elif menu == "📊 Reportes":
        st.title("📊 Reportes")
        df_hist = cargar_tabla("historial")
        if not df_hist.empty:
            st.dataframe(df_hist.sort_values("fecha_evento", ascending=False), use_container_width=True)
            st.metric("Total Cobrado", f"${df_hist[df_hist['tipo']=='COBRO']['monto_operacion'].sum():,.2f}")

# --- INICIO ---
if check_login():
    main_app()