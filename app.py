import streamlit as st
import pandas as pd
from supabase import create_client
from datetime import datetime, timedelta
import time
import extra_streamlit_components as stx

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Grupo Koriel ERP", page_icon="⚡", layout="wide")

# --- ESTILOS ---
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

# --- GESTOR DE COOKIES (CORREGIDO AQUÍ) ---
# Quitamos el argumento que daba error. @st.cache_resource debe ir solo.
@st.cache_resource
def get_manager():
    return stx.CookieManager()

cookie_manager = get_manager()

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
    except Exception as e:
        st.error(f"Error guardando datos: {e}")

def cargar_tabla(tabla):
    try:
        response = supabase.table(tabla).select("*").execute()
        return pd.DataFrame(response.data)
    except:
        return pd.DataFrame()

def actualizar_prestamo(id_p, cant, total):
    supabase.table("prestamos").update({"cantidad_pendiente": cant, "total_pendiente": total}).eq("id", id_p).execute()

# --- LOGIN CON COOKIES ---
def check_login():
    time.sleep(0.1) # Pequeña pausa para asegurar carga de cookie
    cookie_usuario = cookie_manager.get(cookie="koriel_user")
    
    if cookie_usuario:
        if "usuario_logueado" not in st.session_state or st.session_state["usuario_logueado"] is None:
            st.session_state["usuario_logueado"] = cookie_usuario
        return True
    
    st.session_state["usuario_logueado"] = None
    
    st.markdown("<h1 style='text-align: center;'>🔐 GRUPO KORIEL CLOUD</h1>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        user = st.text_input("Usuario")
        password = st.text_input("Contraseña", type="password")
        
        if st.button("Ingresar", use_container_width=True):
            if user in USUARIOS and USUARIOS[user] == password:
                st.session_state["usuario_logueado"] = user
                
                # Guardar cookie por 30 días
                exp = datetime.now() + timedelta(days=30)
                cookie_manager.set("koriel_user", user, expires_at=exp)
                
                st.success(f"Bienvenido {user}")
                time.sleep(0.5)
                st.rerun()
            else:
                st.error("Acceso denegado")
    return False

# --- LOGOUT ---
def logout():
    cookie_manager.delete("koriel_user")
    st.session_state["usuario_logueado"] = None
    st.rerun()

# --- APP PRINCIPAL ---
def main_app():
    usuario_actual = st.session_state["usuario_logueado"]
    
    with st.sidebar:
        st.title("🏢 KORIEL CLOUD")
        st.write(f"👤 **{usuario_actual.upper()}**")
        st.divider()
        menu = st.radio("Menú", ["📍 Rutas y Cobro", "📦 Nuevo Préstamo", "🛠️ Administración", "📊 Reportes"])
        st.divider()
        if st.button("Cerrar Sesión"):
            logout()

    # Cargar datos
    df_cli = cargar_tabla("clientes")
    df_prod = cargar_tabla("productos")

    # --- PESTAÑAS ---
    if menu == "📍 Rutas y Cobro":
        st.title("📍 Cobranza en Campo")
        df_pend = cargar_tabla("prestamos")
        if not df_pend.empty:
            df_pend = df_pend[df_pend["cantidad_pendiente"] > 0]
            clientes = df_pend["cliente"].unique()
            if len(clientes) > 0:
                sel = st.selectbox("Cliente", clientes)
                
                if not df_cli.empty:
                    info = df_cli[df_cli["nombre"] == sel]
                    if not info.empty:
                        st.info(f"🏠 {info.iloc[0].get('tienda','-')} | 📍 {info.iloc[0].get('direccion','-')}")
                
                datos = df_pend[df_pend["cliente"] == sel].copy()
                datos["Cobrar"], datos["Devolver"] = 0, 0
                
                edited = st.data_editor(
                    datos[["id", "producto", "cantidad_pendiente", "precio_unitario", "Cobrar", "Devolver"]],
                    column_config={
                        "id": st.column_config.NumberColumn(disabled=True),
                        "cantidad_pendiente": st.column_config.NumberColumn("Stock", disabled=True),
                        "Cobrar": st.column_config.NumberColumn(min_value=0),
                        "Devolver": st.column_config.NumberColumn(min_value=0)
                    },
                    hide_index=True,
                    key="editor_cobro"
                )
                
                total = (edited["Cobrar"] * edited["precio_unitario"]).sum()
                if total > 0: st.success(f"💵 A RECIBIR: **${total:,.2f}**")
                
                if st.button("✅ Procesar", type="primary"):
                    proc = False
                    hoy = datetime.now().isoformat()
                    for i, r in edited.iterrows():
                        v, d = r["Cobrar"], r["Devolver"]
                        if v > 0 or d > 0:
                            proc = True
                            if v > 0: insertar_registro("historial", {"fecha_evento": hoy, "usuario_responsable": usuario_actual, "tipo": "COBRO", "cliente": sel, "producto": r["producto"], "cantidad": int(v), "monto_operacion": float(v*r["precio_unitario"])})
                            if d > 0: insertar_registro("historial", {"fecha_evento": hoy, "usuario_responsable": usuario_actual, "tipo": "DEVOLUCION", "cliente": sel, "producto": r["producto"], "cantidad": int(d), "monto_operacion": 0})
                            actualizar_prestamo(r["id"], int(r["cantidad_pendiente"] - v - d), float((r["cantidad_pendiente"] - v - d) * r["precio_unitario"]))
                    if proc:
                        st.toast("Actualizado")
                        time.sleep(1)
                        st.rerun()
            else: st.success("Todo al día.")
        else: st.success("Sin deudas.")

    elif menu == "📦 Nuevo Préstamo":
        st.title("📦 Registrar Salida")
        c1, c2 = st.columns(2)
        with c1:
            cli_list = df_cli["nombre"].unique() if not df_cli.empty else []
            prod_list = df_prod["nombre"].unique() if not df_prod.empty else []
            cli = st.selectbox("Cliente", cli_list)
            prod = st.selectbox("Producto", prod_list)
            pb = 0.0
            if not df_prod.empty and prod:
                 px = df_prod[df_prod["nombre"] == prod]
                 if not px.empty: pb = float(px.iloc[0]["precio_base"])
        with c2:
            cant = st.number_input("Cantidad", 1)
            pre = st.number_input("Precio", value=pb)
        
        if st.button("Guardar"):
            insertar_registro("prestamos", {"fecha_registro": datetime.now().strftime("%Y-%m-%d"), "usuario": usuario_actual, "cliente": cli, "producto": prod, "cantidad_pendiente": cant, "precio_unitario": pre, "total_pendiente": cant*pre})
            st.success("Guardado")
            st.rerun()

    elif menu == "🛠️ Administración":
        st.title("🛠️ Maestros")
        c1, c2 = st.columns(2)
        with c1:
            with st.form("fc"):
                n, t, tel, d = st.text_input("Nombre"), st.text_input("Tienda"), st.text_input("Tel"), st.text_input("Dir")
                if st.form_submit_button("Crear Cliente"):
                    insertar_registro("clientes", {"nombre": n, "tienda": t, "telefono": tel, "direccion": d})
                    st.rerun()
        with c2:
            with st.form("fp"):
                n, c, p = st.text_input("Prod"), st.selectbox("Cat", ["Varios"]), st.number_input("Precio")
                if st.form_submit_button("Crear Producto"):
                    insertar_registro("productos", {"nombre": n, "categoria": c, "precio_base": p})
                    st.rerun()

    elif menu == "📊 Reportes":
        st.title("📊 Reportes")
        h = cargar_tabla("historial")
        if not h.empty:
            st.dataframe(h.sort_values("fecha_evento", ascending=False), use_container_width=True)
            tot = h[h["tipo"]=="COBRO"]["monto_operacion"].sum()
            st.metric("Total Histórico", f"${tot:,.2f}")

if check_login():
    main_app()