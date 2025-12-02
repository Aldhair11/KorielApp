import streamlit as st
import pandas as pd
from supabase import create_client
from datetime import datetime, timedelta, date
import time
import extra_streamlit_components as stx
import json
import io

# ==========================================
# CONFIGURACIÓN VISUAL Y ESTILOS
# ==========================================
st.set_page_config(page_title="Grupo Koriel ERP", page_icon="⚡", layout="wide")

st.markdown("""
<style>
    [data-testid="stSidebarNav"] {display: none;}
    .stRadio > label {display: none;}
    div[data-testid="stMetricValue"] {font-size: 26px; font-weight: bold;}
    
    .client-card {
        background-color: #f8f9fa;
        padding: 15px;
        border-radius: 8px;
        border-left: 5px solid #ff4b4b;
        margin-bottom: 10px;
        box-shadow: 2px 2px 5px rgba(0,0,0,0.1);
    }
    .client-card h3 { margin-top: 0; color: #31333F; }
    
    .link-btn {
        display: inline-block;
        padding: 5px 10px;
        background-color: #007bff;
        color: white !important;
        text-decoration: none;
        border-radius: 5px;
        margin-right: 5px;
        font-size: 0.8em;
    }
</style>
""", unsafe_allow_html=True)

# ==========================================
# CONEXIÓN A BASE DE DATOS
# ==========================================
@st.cache_resource
def init_connection():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

supabase = init_connection()

# ==========================================
# USUARIOS Y ROLES 
# ==========================================
USUARIOS = {
    "admin": {"pass": "123", "rol": "admin"},
    "werlin": {"pass": "1234", "rol": "user"},
    "rossel": {"pass": "0000", "rol": "user"}
}

# ==========================================
# 4. FUNCIONES DEL MOTOR (CRUD)
# ==========================================

def insertar_registro(tabla, datos):
    try:
        response = supabase.table(tabla).insert(datos).execute()
        return response
    except Exception as e:
        st.error(f"Error guardando en {tabla}: {e}")
        return None

def cargar_tabla(tabla):
    try:
        response = supabase.table(tabla).select("*").execute()
        df = pd.DataFrame(response.data)
        
        cols_fecha = ["fecha_registro", "fecha_evento", "fecha", "fecha_pedido", "fecha_llegada_estimada"]
        for col in cols_fecha:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors='coerce')
        
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

def actualizar_estado_importacion(id_imp, nuevo_estado):
    try:
        supabase.table("importaciones").update({"estado": nuevo_estado}).eq("id", id_imp).execute()
        return True
    except Exception as e:
        st.error(f"Error actualizando estado: {e}")
        return False

# --- FUNCIONES DE INTEGRIDAD ---

def editar_cliente_global(id_row, datos_nuevos, nombre_anterior):
    try:
        supabase.table("clientes").update(datos_nuevos).eq("id", id_row).execute()
        nuevo_nombre = datos_nuevos.get("nombre")
        if nuevo_nombre and nuevo_nombre != nombre_anterior:
            supabase.table("prestamos").update({"cliente": nuevo_nombre}).eq("cliente", nombre_anterior).execute()
            supabase.table("historial").update({"cliente": nuevo_nombre}).eq("cliente", nombre_anterior).execute()
        return True
    except Exception as e:
        st.error(f"Error editando cliente: {e}")
        return False

def editar_producto_global(id_row, datos_nuevos, nombre_anterior):
    try:
        supabase.table("productos").update(datos_nuevos).eq("id", id_row).execute()
        nuevo_nombre = datos_nuevos.get("nombre")
        if nuevo_nombre and nuevo_nombre != nombre_anterior:
            supabase.table("prestamos").update({"producto": nuevo_nombre}).eq("producto", nombre_anterior).execute()
            supabase.table("historial").update({"producto": nuevo_nombre}).eq("producto", nombre_anterior).execute()
            supabase.table("stock_real").update({"producto": nuevo_nombre}).eq("producto", nombre_anterior).execute()
        return True
    except Exception as e:
        st.error(f"Error editando producto: {e}")
        return False

# --- FUNCIONES DE INVENTARIO ---

def mover_inventario(almacen, producto, cantidad, tipo, usuario, motivo):
    try:
        res = supabase.table("stock_real").select("*").eq("almacen", almacen).eq("producto", producto).execute()
        stock_actual = 0
        id_row = None
        
        if res.data:
            stock_actual = res.data[0]["cantidad"]
            id_row = res.data[0]["id"]
        
        nuevo_stock = stock_actual
        if tipo == "ENTRADA":
            nuevo_stock += cantidad
        elif tipo == "SALIDA":
            if stock_actual < cantidad:
                return False, "⛔ Stock insuficiente en este almacén."
            nuevo_stock -= cantidad
            
        if id_row:
            supabase.table("stock_real").update({"cantidad": nuevo_stock}).eq("id", id_row).execute()
        else:
            if tipo == "SALIDA": return False, "⛔ El producto no existe en este almacén."
            supabase.table("stock_real").insert({"almacen": almacen, "producto": producto, "cantidad": nuevo_stock}).execute()
            
        insertar_registro("movimientos_stock", {
            "fecha": datetime.now().isoformat(),
            "usuario": usuario,
            "tipo": tipo,
            "almacen": almacen,
            "producto": producto,
            "cantidad": cantidad,
            "motivo": motivo
        })
        return True, "Movimiento registrado correctamente."
    except Exception as e:
        return False, str(e)

# --- FUNCIONES DE AUDITORÍA ---

def anular_movimiento(id_historial, usuario_actual):
    try:
        resp = supabase.table("historial").select("*").eq("id", id_historial).execute()
        if not resp.data: return False
        dato = resp.data[0]
        
        prestamo = supabase.table("prestamos").select("*").eq("cliente", dato["cliente"]).eq("producto", dato["producto"]).execute()
        
        if prestamo.data:
            p = prestamo.data[0]
            nueva_cantidad = p["cantidad_pendiente"] + dato["cantidad"]
            nuevo_total = nueva_cantidad * p["precio_unitario"]
            
            supabase.table("prestamos").update({
                "cantidad_pendiente": nueva_cantidad,
                "total_pendiente": nuevo_total
            }).eq("id", p["id"]).execute()
            
            insertar_registro("anulaciones", {
                "fecha_error": datetime.now().strftime("%Y-%m-%d"),
                "usuario_responsable": usuario_actual,
                "accion_original": dato["tipo"],
                "cliente": dato["cliente"],
                "producto": dato["producto"],
                "cantidad_restaurada": dato["cantidad"],
                "monto_anulado": dato["monto_operacion"]
            })
            
            supabase.table("historial").delete().eq("id", id_historial).execute()
            return True
        else:
            st.error("No se encontró el préstamo original. No se puede restaurar.")
            return False
    except Exception as e:
        st.error(f"Error al anular: {e}")
        return False

# ==========================================
# 5. SISTEMA DE ACCESO (COOKIES)
# ==========================================

# Inicializar el Gestor de Cookies
def get_manager():
    return stx.CookieManager()

cookie_manager = get_manager()

def check_login():
    # Verifica si ya está en Memoria 
    if "usuario_logueado" in st.session_state and st.session_state["usuario_logueado"]:
        return True
    
    # Verificar si hay Cookie guardada 
    time.sleep(0.1)
    cookie_user = cookie_manager.get(cookie="koriel_user_secure")
    
    if cookie_user:
        # Validar que el usuario siga existiendo en tu lista
        if cookie_user in USUARIOS:
            st.session_state["usuario_logueado"] = cookie_user
            st.session_state["rol_usuario"] = USUARIOS[cookie_user]["rol"]
            return True
    
    # Si no hay nada, mostrar pantalla de Login
    st.session_state["usuario_logueado"] = None
    
    st.markdown("<br><br>", unsafe_allow_html=True)
    st.markdown("<h1 style='text-align: center;'>GRUPO KORIEL CLOUD</h1>", unsafe_allow_html=True)
    
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        user = st.text_input("Usuario")
        password = st.text_input("Contraseña", type="password")
        
        if st.button("Ingresar", use_container_width=True, type="primary"):
            if user in USUARIOS and USUARIOS[user]["pass"] == password:
                # Guarda la sesion
                st.session_state["usuario_logueado"] = user
                st.session_state["rol_usuario"] = USUARIOS[user]["rol"]
                fecha_exp = datetime.now() + timedelta(days=30)
                cookie_manager.set("koriel_user_secure", user, expires_at=fecha_exp)
                
                st.toast(f"¡Bienvenido {user}!")
                time.sleep(0.5)
                st.rerun()
            else:
                st.error("Datos incorrectos")
    return False

def logout():
    # Borrar cookie y limpiar sesión
    cookie_manager.delete("koriel_user_secure")
    st.session_state["usuario_logueado"] = None
    st.session_state["rol_usuario"] = None
    st.rerun()

# ==========================================
# 6. APLICACIÓN PRINCIPAL 
# ==========================================
def main_app():
    usuario_actual = st.session_state["usuario_logueado"]
    rol_actual = st.session_state["rol_usuario"]
    
    # --- MENÚ LATERAL DINÁMICO POR ROL ---
    with st.sidebar:
        st.title("KORIEL CLOUD")
        st.write(f"👤 **{usuario_actual.upper()}** ({rol_actual.upper()})")
        st.divider()
        
        opciones_menu = []
        
        if rol_actual == "admin":
            opciones_menu = [
                "Nuevo Préstamo", 
                "Rutas y Cobro", 
                #"Inventario y Almacenes", 
                "Consultas y Recibos", 
                "Anular/Corregir", 
                "Reportes Financieros", 
                "Administración"
                # "Importaciones" 
            ]
        else: # TRABAJADOR: Ve Nuevo Prestamo y el Historial General
            opciones_menu = [
                "Nuevo Préstamo",
                "Consultas y Recibos" 
            ]
            
        menu = st.radio("Navegación del Sistema", opciones_menu)
        
        st.divider()
        if st.button("Cerrar Sesión"):
            logout()

    # Carga de datos maestros
    df_cli = cargar_tabla("clientes")
    df_prod = cargar_tabla("productos")

    # ==========================================
    # MÓDULO: NUEVO PRÉSTAMO (VISIBLE PARA TODOS)
    # ==========================================
    if menu == "Nuevo Préstamo":
        st.title("Registrar Salida de Mercadería")
        
        df_deudas = cargar_tabla("prestamos")
        
        # Listas Inteligentes
        lista_c = ["➕ CREAR NUEVO..."] + sorted(df_cli["nombre"].unique().tolist()) if not df_cli.empty else ["➕ CREAR NUEVO..."]
        lista_p = ["➕ CREAR NUEVO..."] + sorted(df_prod["nombre"].unique().tolist()) if not df_prod.empty else ["➕ CREAR NUEVO..."]

        with st.container(border=True):
            c1, c2 = st.columns(2)
            
            # --- SECCIÓN CLIENTE ---
            with c1:
                st.subheader("1. Cliente")
                cli_sel = st.selectbox("Buscar Cliente", lista_c)
                
                cli_final = None
                new_cli_n = None
                new_cli_t = None
                
                if cli_sel == "➕ CREAR NUEVO...":
                    new_cli_n = st.text_input("Nombre Completo")
                    new_cli_t = st.text_input("Nombre Tienda")
                    cli_final = new_cli_n
                else: 
                    cli_final = cli_sel
                    # SEMÁFORO DE RIESGO
                    if not df_deudas.empty:
                        deuda = df_deudas[(df_deudas["cliente"] == cli_final)]["total_pendiente"].sum()
                        if deuda > 0:
                            st.error(f"⚠️ RIESGO: Este cliente tiene deuda de **${deuda:,.2f}**")
                        else:
                            st.success("✅ Cliente al día.")
            
            # --- SECCIÓN PRODUCTO ---
            with c2:
                st.subheader("2. Producto")
                prod_sel = st.selectbox("Buscar Producto", lista_p)
                
                prod_final = None
                pre_sug = 0.0
                
                if prod_sel == "➕ CREAR NUEVO...":
                    prod_final = st.text_input("Descripción Producto")
                else:
                    prod_final = prod_sel
                    if not df_prod.empty:
                        row = df_prod[df_prod["nombre"]==prod_sel]
                        if not row.empty: pre_sug = float(row.iloc[0]["precio_base"])

                cc1, cc2 = st.columns(2)
                cant = cc1.number_input("Cantidad", min_value=1, value=1)
                precio = cc2.number_input("Precio Unitario", min_value=0.0, value=pre_sug, step=0.5)
            
            st.divider()
            obs = st.text_input("Observaciones / Notas (Opcional)", placeholder="Ej: Paga el fin de semana, entregar sin caja...")

            # --- BOTÓN DE GUARDADO ---
            if st.button("GUARDAR PRÉSTAMO", type="primary", use_container_width=True):
                if cli_final and prod_final:
                    # Crear Maestros si son nuevos
                    if cli_sel == "➕ CREAR NUEVO...": 
                        insertar_registro("clientes", {"nombre": new_cli_n, "tienda": new_cli_t})
                    if prod_sel == "➕ CREAR NUEVO...": 
                        insertar_registro("productos", {"nombre": prod_final, "categoria": "Otros", "precio_base": precio})
                    
                    # Guardar Transacción
                    insertar_registro("prestamos", {
                        "fecha_registro": datetime.now().strftime("%Y-%m-%d"),
                        "usuario": usuario_actual,
                        "cliente": cli_final,
                        "producto": prod_final,
                        "cantidad_pendiente": cant,
                        "precio_unitario": precio,
                        "total_pendiente": cant*precio,
                        "observaciones": obs
                    })
                    st.success(f"Producto asignado a {cli_final}"); time.sleep(1.5); st.rerun()
                else: 
                    st.error("Faltan datos obligatorios.")

    # ==========================================
    # MÓDULO: MIS MOVIMIENTOS (SOLO TRABAJADOR)
    # ==========================================
    elif menu == "Mis Movimientos (Historial)":
        st.title(f"Historial de {usuario_actual.capitalize()}")
        st.info("Aquí puedes ver los préstamos que has registrado hoy.")
        
        df_p = cargar_tabla("prestamos")
        if not df_p.empty:
            mis_prestamos = df_p[df_p["usuario"] == usuario_actual].sort_values("fecha_registro", ascending=False)
            
            if not mis_prestamos.empty:
                st.dataframe(mis_prestamos[["fecha_registro", "cliente", "producto", "cantidad_pendiente", "total_pendiente", "observaciones"]], use_container_width=True)
            else:
                st.warning("No has registrado préstamos aún.")
        else:
            st.warning("No hay registros en el sistema.")

    # ==========================================
    # MÓDULO: RUTAS Y COBRO (SOLO ADMIN)
    # ==========================================
    elif menu == "Rutas y Cobro":
        st.title("Gestión de Cobranza")
        
        df_pend = cargar_tabla("prestamos")
        if not df_pend.empty: df_pend = df_pend[df_pend["cantidad_pendiente"] > 0]
        
        if df_pend.empty:
            st.success("✅ No hay cobranza pendiente.")
        else:
            cli_visita = st.selectbox("Seleccionar Cliente en Ruta:", sorted(df_pend["cliente"].unique()))
            datos = df_pend[df_pend["cliente"] == cli_visita].copy()
            deuda_total = datos["total_pendiente"].sum()
            
            # Tarjeta de Información con RUC
            with st.container(border=True):
                c_info, c_total = st.columns([3, 1])
                with c_info:
                    if not df_cli.empty:
                        info = df_cli[df_cli["nombre"] == cli_visita]
                        if not info.empty:
                            r = info.iloc[0]
                            st.markdown(f"🏠 **{r.get('tienda','-')}** | 📍 {r.get('direccion','-')} | 📞 {r.get('telefono','-')}")
                            ruc_txt = f"🆔 **RUC:** {r.get('ruc1', 'N/A')}"
                            if r.get('ruc2'): ruc_txt += f" / {r.get('ruc2')}"
                            st.markdown(ruc_txt)
                with c_total:
                    st.metric("DEUDA TOTAL", f"${deuda_total:,.2f}")

            datos["Cobrar"] = 0; datos["Devolver"] = 0
            if "observaciones" not in datos.columns: datos["observaciones"] = ""

            c1, c2 = st.columns(2)
            with c1:
                if st.button("COBRAR TODO (Pagó 100%)", type="primary", use_container_width=True):
                    hoy = datetime.now().isoformat()
                    for i, r in datos.iterrows():
                        cant = int(r["cantidad_pendiente"])
                        monto = float(cant * r["precio_unitario"])
                        insertar_registro("historial", {"fecha_evento": hoy, "usuario_responsable": usuario_actual, "tipo": "COBRO", "cliente": cli_visita, "producto": r["producto"], "cantidad": cant, "monto_operacion": monto})
                        actualizar_prestamo(r["id"], 0, 0)
                    st.toast("¡Cobro registrado!"); time.sleep(1); st.rerun()
            with c2:
                if st.button("DEVOLVER TODO (No vendió)", use_container_width=True):
                    hoy = datetime.now().isoformat()
                    for i, r in datos.iterrows():
                        cant = int(r["cantidad_pendiente"])
                        insertar_registro("historial", {"fecha_evento": hoy, "usuario_responsable": usuario_actual, "tipo": "DEVOLUCION", "cliente": cli_visita, "producto": r["producto"], "cantidad": cant, "monto_operacion": 0})
                        actualizar_prestamo(r["id"], 0, 0)
                    st.toast("¡Devolución registrada!"); time.sleep(1); st.rerun()

            st.markdown("---")
            st.write("##### Gestión Manual / Parcial")
            
            edited = st.data_editor(
                datos[["id", "producto", "cantidad_pendiente", "precio_unitario", "observaciones", "Cobrar", "Devolver"]],
                column_config={
                    "id": None,
                    "cantidad_pendiente": st.column_config.NumberColumn("Stock", disabled=True),
                    "precio_unitario": st.column_config.NumberColumn("Precio", format="$%.2f", disabled=True),
                    "observaciones": st.column_config.TextColumn("Notas", disabled=True),
                    "Cobrar": st.column_config.NumberColumn("Pagó", min_value=0),
                    "Devolver": st.column_config.NumberColumn("Devuelve", min_value=0)
                }, hide_index=True, key="ecob"
            )
            
            pay_now = (edited["Cobrar"] * edited["precio_unitario"]).sum()
            
            cp1, cp2 = st.columns([2, 1])
            with cp1:
                if pay_now > 0: st.success(f"💵 CLIENTE PAGA AHORA: **${pay_now:,.2f}**")
            with cp2:
                if st.button("Procesar Manual", use_container_width=True):
                    hoy = datetime.now().isoformat()
                    p = False
                    for i, r in edited.iterrows():
                        v, d = r["Cobrar"], r["Devolver"]
                        if v > 0 or d > 0:
                            p = True
                            if v > 0: insertar_registro("historial", {"fecha_evento": hoy, "usuario_responsable": usuario_actual, "tipo": "COBRO", "cliente": cli_visita, "producto": r["producto"], "cantidad": int(v), "monto_operacion": float(v*r["precio_unitario"])})
                            if d > 0: insertar_registro("historial", {"fecha_evento": hoy, "usuario_responsable": usuario_actual, "tipo": "DEVOLUCION", "cliente": cli_visita, "producto": r["producto"], "cantidad": int(d), "monto_operacion": 0})
                            
                            new_c = int(r["cantidad_pendiente"]-v-d)
                            actualizar_prestamo(r["id"], new_c, float(new_c*r["precio_unitario"]))
                    if p: st.toast("Procesado"); time.sleep(1); st.rerun()

    # ==========================================
    # MÓDULO: IMPORTACIONES Y COMPRAS (OCULTO PERO CÓDIGO PRESENTE)
    # ==========================================
    elif menu == "Importaciones":
       
        st.info("Módulo en construcción o desactivado.")

    # ==========================================
    # MÓDULO: INVENTARIO Y ALMACENES (SOLO ADMIN)
    # ==========================================
    elif menu == "Inventario y Almacenes":
        st.title("Gestión de Almacenes")
        
        df_alm = cargar_tabla("almacenes")
        df_stock = cargar_tabla("stock_real")
        
        t1, t2, t3 = st.tabs(["Registrar Movimiento", "Stock Actual", "Crear Almacén"])
        
        with t1:
            st.subheader("Entrada / Salida")
            if df_alm.empty:
                st.warning("Crea un almacén primero.")
            else:
                c1, c2 = st.columns(2)
                with c1:
                    tipo_mov = st.selectbox("Tipo Movimiento", ["ENTRADA ", "SALIDA (Tienda/Venta)"])
                    alm_mov = st.selectbox("Almacén", sorted(df_alm["nombre"].unique()))
                    prod_mov = st.selectbox("Producto", sorted(df_prod["nombre"].unique()) if not df_prod.empty else [])
                with c2:
                    cant_mov = st.number_input("Cantidad", min_value=1, value=1)
                    motivo_mov = st.text_input("Motivo / Detalle")
                
                if st.button("Registrar Movimiento", type="primary"):
                    if prod_mov:
                        ok, msg = mover_inventario(alm_mov, prod_mov, cant_mov, "ENTRADA" if "ENTRADA" in tipo_mov else "SALIDA", usuario_actual, motivo_mov)
                        if ok: st.success(msg); time.sleep(1); st.rerun()
                        else: st.error(msg)
                    else: st.error("Selecciona un producto.")

        with t2:
            st.subheader("Inventario Físico")
            if not df_stock.empty:
                filtro_alm = st.multiselect("Filtrar Almacén", sorted(df_stock["almacen"].unique()))
                df_view = df_stock.copy()
                if filtro_alm: df_view = df_view[df_view["almacen"].isin(filtro_alm)]
                
                st.dataframe(df_view[["almacen", "producto", "cantidad"]].sort_values("almacen"), use_container_width=True)
                
                st.divider()
                st.write("**Total Consolidado:**")
                st.dataframe(df_view.groupby("producto")["cantidad"].sum().sort_values(ascending=False))
            else: st.info("Sin stock registrado.")

        with t3:
            with st.form("new_alm"):
                n_alm = st.text_input("Nombre Almacén")
                if st.form_submit_button("Crear"):
                    insertar_registro("almacenes", {"nombre": n_alm})
                    st.success("Creado"); st.rerun()
            if not df_alm.empty: st.dataframe(df_alm["nombre"], use_container_width=True)

    # ==========================================
    # MÓDULO 3: CONSULTAS Y RECIBOS
    # ==========================================
    elif menu == "Consultas y Recibos":
        st.title("Consultas")
        t1, t2 = st.tabs(["Deudas", "Historial"])
        
        # --- DEUDAS ---
        with t1:
            df_p = cargar_tabla("prestamos")
            if not df_p.empty:
                df_p = df_p[df_p["cantidad_pendiente"] > 0]
                c1, c2 = st.columns(2)
                ft = c1.selectbox("Filtro Fecha", ["Todos", "Hoy", "Esta Semana", "Este Mes"])
                fc = c2.multiselect("Filtro Cliente", sorted(df_p["cliente"].unique()))
                
                df_s = df_p.copy()
                hoy = date.today()
                
                # Filtros de Fecha
                if ft == "Hoy": 
                    df_s = df_s[df_s["fecha_registro"].dt.date == hoy] if not df_s["fecha_registro"].empty else df_s
                elif ft == "Esta Semana": 
                    df_s = df_s[df_s["fecha_registro"].dt.date >= hoy - timedelta(days=hoy.weekday())] if not df_s["fecha_registro"].empty else df_s
                elif ft == "Este Mes": 
                     df_s = df_s[df_s["fecha_registro"].dt.date >= hoy.replace(day=1)] if not df_s["fecha_registro"].empty else df_s 
                
                # Filtro Cliente
                if fc: df_s = df_s[df_s["cliente"].isin(fc)]
                
                # ---  ORDEN NUEVO PRIMERO ---
                df_s = df_s.sort_values("fecha_registro", ascending=False)
                
                st.dataframe(
                    df_s, 
                    use_container_width=True,
                    column_config={
                        "id": None, # Oculta el ID
                        "fecha_registro": st.column_config.DateColumn("Fecha", format="YYYY-MM-DD"), 
                        "total_pendiente": st.column_config.NumberColumn("Total Deuda", format="$%.2f"), 
                        "precio_unitario": st.column_config.NumberColumn("Precio", format="$%.2f"),
                        "usuario": st.column_config.TextColumn("Vendedor"),
                        "observaciones": st.column_config.TextColumn("Notas")
                    }
                )
                
                st.metric("Total Mostrado", f"${df_s['total_pendiente'].sum():,.2f}")
                
                if st.button("🖨️ Generar Recibo WhatsApp"):
                    txt = f"*ESTADO DE CUENTA*\n📅 {datetime.now().strftime('%d/%m/%Y')}\n----------------\n"
                    for c in df_s["cliente"].unique():
                        txt += f"👤 {c}:\n"
                        for i, r in df_s[df_s["cliente"]==c].iterrows():
                           
                            fecha_txt = r['fecha_registro'].strftime('%d/%m') if pd.notnull(r['fecha_registro']) else ""
                            txt += f" - {fecha_txt} | {r['producto']} (x{r['cantidad_pendiente']}): ${r['total_pendiente']:,.2f}\n"
                    txt += f"----------------\n*TOTAL: ${df_s['total_pendiente'].sum():,.2f}*"
                    st.code(txt, language="text")

        # --- PESTAÑA 2: HISTORIAL ---
        with t2:
            df_h = cargar_tabla("historial")
            if not df_h.empty:
                c1, c2, c3 = st.columns(3)
                fc = c1.multiselect("Cliente", sorted(df_h["cliente"].unique()))
                ft = c2.multiselect("Tipo", ["COBRO", "DEVOLUCION"])
                fd = c3.date_input("Rango Fecha", [date.today()-timedelta(days=30), date.today()])
                
                df_hs = df_h.copy()
                if fc: df_hs = df_hs[df_hs["cliente"].isin(fc)]
                if ft: df_hs = df_hs[df_hs["tipo"].isin(ft)]
                if len(fd)==2: 
                    df_hs = df_hs[(df_hs["fecha_evento"].dt.date >= fd[0]) & (df_hs["fecha_evento"].dt.date <= fd[1])]
                
                # Ordenar historial también (lo último primero)
                df_hs = df_hs.sort_values("fecha_evento", ascending=False)

                # Visualización limpia del historial
                st.dataframe(
                    df_hs, 
                    use_container_width=True,
                    column_config={
                        "id": None,
                        "fecha_evento": st.column_config.DatetimeColumn("Fecha/Hora", format="DD/MM/YYYY HH:mm"),
                        "monto_operacion": st.column_config.NumberColumn("Monto", format="$%.2f")
                    }
                )

    # ==========================================
    # MÓDULO: ANULAR / CORREGIR (SOLO ADMIN)
    # ==========================================
    elif menu == "Anular/Corregir":
        st.title("Corrección de Errores")
        st.warning("ANULAR pagos o devoluciones.")
        
        tab_cor, tab_log = st.tabs(["Deshacer", "Historial"])
        
        with tab_cor:
            df_hist = cargar_tabla("historial")
            if not df_hist.empty:
                c_fil, _ = st.columns(2)
                filtro_c = c_fil.selectbox("Filtrar por Cliente", ["Todos"] + sorted(df_hist["cliente"].unique().tolist()))
                
                df_view = df_hist.copy()
                if filtro_c != "Todos": df_view = df_view[df_view["cliente"] == filtro_c]
                
                st.write("Últimos movimientos:")
                for index, row in df_view.sort_values("fecha_evento", ascending=False).head(20).iterrows():
                    c1, c2, c3, c4, c5 = st.columns([2, 2, 2, 2, 1])
                    fecha_evento = row['fecha_evento'].strftime("%Y-%m-%d %H:%M") 
                    c1.write(f"📅 {fecha_evento}")
                    c2.write(f"👤 {row['cliente']}")
                    c3.write(f"📦 {row['producto']} (x{row['cantidad']})")
                    c4.write(f"💰 {row['tipo']} (${row['monto_operacion']})")
                    
                    if c5.button("ANULAR ❌", key=f"del_{row['id']}"):
                        if anular_movimiento(row['id'], usuario_actual):
                            st.success("¡Anulado!"); time.sleep(1); st.rerun()
            else: st.info("Sin movimientos.")

        with tab_log:
            df_anul = cargar_tabla("anulaciones")
            if not df_anul.empty: 
                st.dataframe(
                    df_anul.sort_values("id", ascending=False), 
                    use_container_width=True,
                    column_config={
                        "id": None,
                        "created_at": st.column_config.DatetimeColumn("Fecha Anulación", format="YYYY-MM-DD HH:mm"),
                        "fecha_error": st.column_config.DateColumn("Fecha Original", format="YYYY-MM-DD")
                    }
                )
    # ==========================================
    # MÓDULO: REPORTES (SOLO ADMIN)
    # ==========================================
    elif menu == "Reportes Financieros":
        st.title("Balance General")
        c1, c2 = st.columns(2)
        f_cli = c1.multiselect("Filtrar Cliente", sorted(df_cli["nombre"].unique()) if not df_cli.empty else [])
        f_fec = c2.date_input("Periodo", [date.today().replace(day=1), date.today()])
        
        df_p = cargar_tabla("prestamos")
        df_h = cargar_tabla("historial")
        
        if f_cli: 
            if not df_p.empty: df_p = df_p[df_p["cliente"].isin(f_cli)]
            if not df_h.empty: df_h = df_h[df_h["cliente"].isin(f_cli)]
        if not df_h.empty and len(f_fec)==2:
            df_h = df_h[(df_h["fecha_evento"].dt.date >= f_fec[0]) & (df_h["fecha_evento"].dt.date <= f_fec[1])]
        
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("🔴 Deuda Activa")
            if not df_p.empty:
                st.metric("Total", f"${df_p['total_pendiente'].sum():,.2f}")
                st.dataframe(df_p.groupby("cliente")["total_pendiente"].sum().sort_values(ascending=False))
        with col2:
            st.subheader("🟢 Ingresos")
            if not df_h.empty:
                cob = df_h[df_h["tipo"]=="COBRO"]
                st.metric("Total", f"${cob['monto_operacion'].sum():,.2f}")
                st.dataframe(cob.groupby("cliente")["monto_operacion"].sum().sort_values(ascending=False))

    # ==========================================
    # MÓDULO: ADMINISTRACIÓN (SOLO ADMIN)
    # ==========================================
    elif menu == "Administración":
        st.title("Administración")
        t1, t2, t3, t4 = st.tabs(["Directorio", "➕ Crear", "✏️ Editar", "💾 Backup"])
        
        with t1:
            st.subheader("Ficha de Cliente")
            if not df_cli.empty:
                vc = st.selectbox("Buscar Cliente", sorted(df_cli["nombre"].unique()))
                dat = df_cli[df_cli["nombre"] == vc].iloc[0]
                st.markdown(f"""<div class="client-card"><h3>👤 {dat['nombre']}</h3><p>🏢 {dat.get('tienda', '-')}</p><p>📍 {dat.get('direccion', '-')}</p><p>📞 {dat.get('telefono', '-')}</p><hr><p>🆔 RUC 1: {dat.get('ruc1', '-')}</p><p>🆔 RUC 2: {dat.get('ruc2', '-')}</p></div>""", unsafe_allow_html=True)
        
        with t2:
            c1, c2 = st.columns(2)
            with c1:
                with st.form("fc"):
                    n=st.text_input("Nombre"); t=st.text_input("Tienda"); tel=st.text_input("Telefono"); d=st.text_input("Direccion"); r1=st.text_input("RUC1"); r2=st.text_input("RUC2")
                    if st.form_submit_button("Crear Cliente"):
                        insertar_registro("clientes", {"nombre":n, "tienda":t, "telefono":tel, "direccion":d, "ruc1":r1, "ruc2":r2}); st.rerun()
            with c2:
                with st.form("fp"):
                    n=st.text_input("Producto"); c=st.selectbox("Categoria", ["Tableros", "Llaves", "Cables", "Interruptores","Otros"]); p=st.number_input("Precio Base")
                    if st.form_submit_button("Crear Producto"):
                        insertar_registro("productos", {"nombre":n, "categoria":c, "precio_base":p}); st.rerun()

        with t3:
            mod = st.radio("Editar:", ["Clientes", "Productos"], horizontal=True)
            if mod == "Clientes" and not df_cli.empty:
                s = st.selectbox("Cliente", df_cli["nombre"].unique())
                d = df_cli[df_cli["nombre"]==s].iloc[0]
                with st.form("fe"):
                    nn=st.text_input("Nombre", d["nombre"]); nt=st.text_input("Tienda", d.get("tienda","")); ntel=st.text_input("Telefono", d.get("telefono","")); nd=st.text_input("Direccion", d.get("direccion","")); nr1=st.text_input("RUC1", d.get("ruc1","")); nr2=st.text_input("RUC2", d.get("ruc2",""))
                    if st.form_submit_button("Actualizar"):
                        editar_cliente_global(int(d["id"]), {"nombre":nn, "tienda":nt, "telefono":ntel, "direccion":nd, "ruc1":nr1, "ruc2":nr2}, d["nombre"])
                        st.success("Actualizado"); time.sleep(1); st.rerun()
            elif mod == "Productos" and not df_prod.empty:
                s = st.selectbox("Productos", df_prod["nombre"].unique())
                d = df_prod[df_prod["nombre"]==s].iloc[0]
                with st.form("fep"):
                    nn=st.text_input("Nombre", d["nombre"]); np=st.number_input("Precio", float(d["precio_base"])); nc=st.text_input("Categoria", d["categoria"])
                    if st.form_submit_button("Actualizar"):
                        editar_producto_global(int(d["id"]), {"nombre":nn, "precio_base":np, "categoria":nc}, d["nombre"])
                        st.success("Actualizado"); time.sleep(1); st.rerun()

        with t4:
            st.info("Descarga Excel limpia.")
            def clean_csv(df, map_cols): return df.rename(columns=map_cols).to_csv(index=False).encode('utf-8')
            c1, c2 = st.columns(2)
            
            # Cargar Datos para Backup
            df_p_full = cargar_tabla("prestamos")
            df_h_full = cargar_tabla("historial")
            df_s_full = cargar_tabla("stock_real")
            df_m_full = cargar_tabla("movimientos_stock")
            df_imp_full = cargar_tabla("importaciones")
            
            if not df_cli.empty: c1.download_button("📥 Clientes", clean_csv(df_cli, {"nombre": "Cliente", "ruc1": "RUC"}), "cli.csv", "text/csv")
            if not df_p_full.empty: c1.download_button("📥 Préstamos", clean_csv(df_p_full, {"cliente": "Cliente", "total_pendiente": "Deuda"}), "prest.csv", "text/csv")
            if not df_h_full.empty: c2.download_button("📥 Historial", clean_csv(df_h_full, {"fecha_evento": "Fecha", "monto_operacion": "Monto"}), "hist.csv", "text/csv")
            if not df_prod.empty: c2.download_button("📥 Productos", clean_csv(df_prod, {"nombre": "Producto"}), "prod.csv", "text/csv")
            
            st.write("---")
            st.write("Backups Inventario / Importaciones:")
            c3, c4 = st.columns(2)
            if not df_s_full.empty: c3.download_button("📥 Stock", clean_csv(df_s_full, {"cantidad": "Stock"}), "stock.csv", "text/csv")
            if not df_m_full.empty: c4.download_button("📥 Movimientos Almacén", clean_csv(df_m_full, {"tipo": "Tipo"}), "movs.csv", "text/csv")
            if not df_imp_full.empty: c3.download_button("📥 Importaciones", clean_csv(df_imp_full, {"codigo_pedido": "PO"}), "imports.csv", "text/csv")

# --- INICIO ---
if check_login():
    main_app()