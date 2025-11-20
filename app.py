import streamlit as st
import pandas as pd
from supabase import create_client, Client
from datetime import datetime
import time

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Grupo Koriel ERP", page_icon="⚡", layout="wide")

# --- ESTILOS ---
st.markdown("""
<style>
    [data-testid="stSidebarNav"] {display: none;}
    .stRadio > label {display: none;}
</style>
""", unsafe_allow_html=True)

# --- USUARIOS (Esto podría ir a base de datos luego) ---
USUARIOS = {
    "admin": "admin123",
    "jorge": "1234",
    "maria": "0000"
}

# --- CONEXIÓN A BASE DE DATOS (SUPABASE) ---
# Usamos st.cache_resource para no reconectar a cada rato
@st.cache_resource
def init_connection():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

supabase = init_connection()

# --- FUNCIONES DE DATOS (CRUD) ---
def cargar_tabla(nombre_tabla):
    response = supabase.table(nombre_tabla).select("*").execute()
    df = pd.DataFrame(response.data)
    return df

def insertar_registro(nombre_tabla, datos):
    supabase.table(nombre_tabla).insert(datos).execute()

def actualizar_prestamo(id_prestamo, nueva_cantidad, nuevo_total):
    supabase.table("prestamos").update({
        "cantidad_pendiente": nueva_cantidad,
        "total_pendiente": nuevo_total
    }).eq("id", id_prestamo).execute()

# --- LOGIN ---
def check_login():
    if "usuario_logueado" not in st.session_state:
        st.session_state["usuario_logueado"] = None

    if st.session_state["usuario_logueado"] is None:
        st.markdown("<h1 style='text-align: center;'>🔐 GRUPO KORIEL CLOUD</h1>", unsafe_allow_html=True)
        c1, c2, c3 = st.columns([1, 2, 1])
        with c2:
            user = st.text_input("Usuario")
            password = st.text_input("Contraseña", type="password")
            if st.button("Ingresar", use_container_width=True):
                if user in USUARIOS and USUARIOS[user] == password:
                    st.session_state["usuario_logueado"] = user
                    st.success(f"Bienvenido {user}")
                    time.sleep(0.5)
                    st.rerun()
                else:
                    st.error("Acceso denegado")
        return False
    return True

# --- APP PRINCIPAL ---
def main_app():
    usuario_actual = st.session_state["usuario_logueado"]
    
    # Cargar Datos en tiempo real desde la Nube
    # Usamos try/except por si las tablas están vacías al inicio
    try:
        df_cli = cargar_tabla("clientes")
        df_prod = cargar_tabla("productos")
        df_pend = cargar_tabla("prestamos")
        df_hist = cargar_tabla("historial")
    except Exception as e:
        st.error(f"Error de conexión: {e}")
        return

    # Sidebar
    with st.sidebar:
        st.title("🏢 KORIEL CLOUD")
        st.write(f"👤 **{usuario_actual.upper()}**")
        st.divider()
        
        menu = st.radio("Menú", ["📍 Rutas y Cobro", "📦 Nuevo Préstamo", "🛠️ Administración", "📊 Reportes"])
        
        st.divider()
        if st.button("Cerrar Sesión"):
            st.session_state["usuario_logueado"] = None
            st.rerun()

    # --- 1. RUTAS Y COBRO ---
    if menu == "📍 Rutas y Cobro":
        st.title("📍 Cobranza en Campo")
        st.markdown("---")
        
        if df_pend.empty:
            st.success("✅ No hay deudas pendientes.")
        else:
            # Filtrar solo préstamos con cantidad > 0
            df_pend = df_pend[df_pend["cantidad_pendiente"] > 0]
            lista_clientes = df_pend["cliente"].unique()
            
            if len(lista_clientes) > 0:
                cliente_sel = st.selectbox("Cliente:", lista_clientes)
                
                # Info Cliente
                if not df_cli.empty:
                    info = df_cli[df_cli["nombre"] == cliente_sel]
                    if not info.empty:
                        r = info.iloc[0]
                        st.info(f"🏠 {r.get('tienda','-')} | 📍 {r.get('direccion','-')} | 📞 {r.get('telefono','-')}")

                # Tabla de Cobro
                datos_cliente = df_pend[df_pend["cliente"] == cliente_sel].copy()
                
                # Preparamos columnas para editar
                datos_cliente["Cobrar"] = 0
                datos_cliente["Devolver"] = 0
                
                config = {
                    "id": st.column_config.NumberColumn(disabled=True),
                    "cantidad_pendiente": st.column_config.NumberColumn("Stock", disabled=True),
                    "precio_unitario": st.column_config.NumberColumn("Precio", format="$%.2f", disabled=True),
                    "total_pendiente": st.column_config.NumberColumn("Total Deuda", format="$%.2f", disabled=True),
                    "Cobrar": st.column_config.NumberColumn("💰 Cobrar (Und)", min_value=0),
                    "Devolver": st.column_config.NumberColumn("🔙 Devolver (Und)", min_value=0)
                }
                
                edited = st.data_editor(
                    datos_cliente[["id", "producto", "cantidad_pendiente", "precio_unitario", "Cobrar", "Devolver"]],
                    column_config=config,
                    hide_index=True,
                    key="editor_cobro"
                )
                
                # Calcular monto a recibir
                monto_recibir = (edited["Cobrar"] * edited["precio_unitario"]).sum()
                if monto_recibir > 0:
                    st.success(f"💵 A RECIBIR AHORA: **${monto_recibir:,.2f}**")

                if st.button("✅ Procesar Transacción", type="primary"):
                    procesado = False
                    fecha = datetime.now().isoformat()
                    
                    for idx, row in edited.iterrows():
                        vende = row["Cobrar"]
                        devuelve = row["Devolver"]
                        id_prestamo = row["id"] # ID real de la base de datos
                        
                        if vende > 0 or devuelve > 0:
                            procesado = True
                            # 1. Guardar Historial
                            if vende > 0:
                                insertar_registro("historial", {
                                    "fecha_evento": fecha, "usuario_responsable": usuario_actual,
                                    "tipo": "COBRO", "cliente": cliente_sel, "producto": row["producto"],
                                    "cantidad": int(vende), "monto_operacion": float(vende * row["precio_unitario"])
                                })
                            if devuelve > 0:
                                insertar_registro("historial", {
                                    "fecha_evento": fecha, "usuario_responsable": usuario_actual,
                                    "tipo": "DEVOLUCION", "cliente": cliente_sel, "producto": row["producto"],
                                    "cantidad": int(devuelve), "monto_operacion": 0
                                })
                            
                            # 2. Actualizar Préstamo
                            nuevo_stock = int(row["cantidad_pendiente"] - vende - devuelve)
                            nuevo_total = float(nuevo_stock * row["precio_unitario"])
                            
                            # Actualizamos directo en Supabase
                            actualizar_prestamo(int(id_prestamo), nuevo_stock, nuevo_total)
                    
                    if procesado:
                        st.toast("✅ Actualizado en la Nube")
                        time.sleep(1)
                        st.rerun()

    # --- 2. NUEVO PRÉSTAMO ---
    elif menu == "📦 Nuevo Préstamo":
        st.title("📦 Registrar Salida")
        if df_cli.empty or df_prod.empty:
            st.warning("Faltan clientes o productos.")
        else:
            c1, c2 = st.columns(2)
            with c1:
                cli = st.selectbox("Cliente", df_cli["nombre"].unique())
                prod = st.selectbox("Producto", df_prod["nombre"].unique())
                # Buscar precio sugerido
                precio_base = 0.0
                if not df_prod.empty:
                    item = df_prod[df_prod["nombre"] == prod]
                    if not item.empty:
                        precio_base = float(item.iloc[0]["precio_base"])
            with c2:
                cant = st.number_input("Cantidad", 1)
                precio = st.number_input("Precio Final", value=precio_base)
            
            if st.button("💾 Guardar en Nube", type="primary"):
                datos = {
                    "fecha_registro": datetime.now().strftime("%Y-%m-%d"),
                    "usuario": usuario_actual,
                    "cliente": cli,
                    "producto": prod,
                    "cantidad_pendiente": cant,
                    "precio_unitario": precio,
                    "total_pendiente": cant * precio
                }
                insertar_registro("prestamos", datos)
                st.success("Guardado y sincronizado.")
                time.sleep(0.5)
                st.rerun()

    # --- 3. ADMINISTRACIÓN ---
    elif menu == "🛠️ Administración":
        st.title("🛠️ Maestros")
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("Nuevo Cliente")
            with st.form("f_cli"):
                nom = st.text_input("Nombre")
                tienda = st.text_input("Tienda")
                tel = st.text_input("Teléfono")
                dire = st.text_input("Dirección")
                if st.form_submit_button("Crear"):
                    insertar_registro("clientes", {"nombre": nom, "tienda": tienda, "telefono": tel, "direccion": dire})
                    st.rerun()
            st.dataframe(df_cli, height=150)
            
        with c2:
            st.subheader("Nuevo Producto")
            with st.form("f_prod"):
                nom_p = st.text_input("Nombre")
                cat = st.selectbox("Cat", ["Iluminación", "Cables", "Herramientas", "Otros"])
                pre = st.number_input("Precio Base", 0.0)
                if st.form_submit_button("Crear"):
                    insertar_registro("productos", {"nombre": nom_p, "categoria": cat, "precio_base": pre})
                    st.rerun()
            st.dataframe(df_prod, height=150)

    # --- 4. REPORTES ---
    elif menu == "📊 Reportes":
        st.title("📊 Reportes Cloud")
        if not df_hist.empty:
            cobros = df_hist[df_hist["tipo"] == "COBRO"]
            total = cobros["monto_operacion"].sum() if not cobros.empty else 0
            st.metric("Total Cobrado Histórico", f"${total:,.2f}")
            
            st.subheader("Movimientos")
            st.dataframe(df_hist.sort_values("fecha_evento", ascending=False), use_container_width=True)

# --- ARRANQUE ---
if check_login():
    main_app()