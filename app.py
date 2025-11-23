import streamlit as st
import pandas as pd
from supabase import create_client
from datetime import datetime, timedelta, date
import time

# --- 1. CONFIGURACIÓN VISUAL ---
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
</style>
""", unsafe_allow_html=True)

# --- 2. CONEXIÓN ---
@st.cache_resource
def init_connection():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

supabase = init_connection()

# --- 3. USUARIOS ---
USUARIOS = {
    "admin": "admin123",
    "jorge": "1234",
    "maria": "0000"
}

# --- 4. FUNCIONES DEL MOTOR ---
def insertar_registro(tabla, datos):
    try:
        supabase.table(tabla).insert(datos).execute()
        return True
    except Exception as e:
        st.error(f"Error guardando: {e}")
        return False

def cargar_tabla(tabla):
    try:
        response = supabase.table(tabla).select("*").execute()
        df = pd.DataFrame(response.data)
        if "fecha_registro" in df.columns:
            df["fecha_registro"] = pd.to_datetime(df["fecha_registro"]).dt.date
        if "fecha_evento" in df.columns:
            df["fecha_evento"] = pd.to_datetime(df["fecha_evento"])
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
        return True
    except Exception as e:
        st.error(f"Error editando producto: {e}")
        return False

# --- NUEVA FUNCIÓN CORREGIDA: REVERTIR MOVIMIENTO ---
def anular_movimiento(id_historial, usuario_actual):
    try:
        # 1. Obtener datos del movimiento (CORREGIDO AQUÍ: id_historial)
        resp = supabase.table("historial").select("*").eq("id", id_historial).execute()
        if not resp.data: return False
        dato = resp.data[0]
        
        # 2. Buscar el préstamo activo
        prestamo = supabase.table("prestamos").select("*").eq("cliente", dato["cliente"]).eq("producto", dato["producto"]).execute()
        
        if prestamo.data:
            p = prestamo.data[0]
            # MATEMÁTICA INVERSA: Devuelve stock o deuda
            nueva_cantidad = p["cantidad_pendiente"] + dato["cantidad"]
            nuevo_total = nueva_cantidad * p["precio_unitario"]
            
            # Actualizamos el préstamo
            supabase.table("prestamos").update({
                "cantidad_pendiente": nueva_cantidad,
                "total_pendiente": nuevo_total
            }).eq("id", p["id"]).execute()
            
            # 3. Guardar en Log de Anulaciones
            insertar_registro("anulaciones", {
                "fecha_error": datetime.now().strftime("%Y-%m-%d"),
                "usuario_responsable": usuario_actual,
                "accion_original": dato["tipo"],
                "cliente": dato["cliente"],
                "producto": dato["producto"],
                "cantidad_restaurada": dato["cantidad"],
                "monto_anulado": dato["monto_operacion"]
            })
            
            # 4. Borrar del historial oficial (CORREGIDO AQUÍ: id_historial)
            supabase.table("historial").delete().eq("id", id_historial).execute()
            return True
        else:
            st.error("No se encontró el préstamo original. Tal vez se borró o cambió de nombre.")
            return False
            
    except Exception as e:
        st.error(f"Error al anular: {e}")
        return False

# --- 5. LOGIN ---
def check_login():
    if "usuario_logueado" in st.session_state and st.session_state["usuario_logueado"]:
        return True
    
    st.session_state["usuario_logueado"] = None
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("<h1 style='text-align: center;'>🔐 GRUPO KORIEL CLOUD</h1>", unsafe_allow_html=True)
    
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        user = st.text_input("Usuario")
        password = st.text_input("Contraseña", type="password")
        if st.button("Entrar al Sistema", use_container_width=True, type="primary"):
            if user in USUARIOS and USUARIOS[user] == password:
                st.session_state["usuario_logueado"] = user
                st.rerun()
            else:
                st.error("Usuario o contraseña incorrectos")
    return False

def logout():
    st.session_state["usuario_logueado"] = None
    st.rerun()

# --- 6. APLICACIÓN PRINCIPAL ---
def main_app():
    usuario_actual = st.session_state["usuario_logueado"]
    
    with st.sidebar:
        st.title("🏢 KORIEL CLOUD")
        st.write(f"👤 **{usuario_actual.upper()}**")
        st.divider()
        menu = st.radio("Navegación", [
            "📦 Nuevo Préstamo", 
            "📍 Rutas y Cobro", 
            "🔍 Consultas y Recibos", 
            "⚠️ Anular/Corregir", 
            "📊 Reportes Financieros", 
            "🛠️ Administración"
        ])
        st.divider()
        if st.button("Cerrar Sesión"):
            logout()

    df_cli = cargar_tabla("clientes")
    df_prod = cargar_tabla("productos")

    # ==========================================
    # 📦 MÓDULO 1: NUEVO PRÉSTAMO
    # ==========================================
    if menu == "📦 Nuevo Préstamo":
        st.title("📦 Registrar Salida")
        df_deudas = cargar_tabla("prestamos")
        
        lista_c = ["➕ CREAR NUEVO..."] + sorted(df_cli["nombre"].unique().tolist()) if not df_cli.empty else ["➕ CREAR NUEVO..."]
        lista_p = ["➕ CREAR NUEVO..."] + sorted(df_prod["nombre"].unique().tolist()) if not df_prod.empty else ["➕ CREAR NUEVO..."]

        with st.container(border=True):
            c1, c2 = st.columns(2)
            with c1:
                st.subheader("1. Cliente")
                cli_sel = st.selectbox("Buscar Cliente", lista_c)
                cli_final = None; new_cli_n = None; new_cli_t = None
                
                if cli_sel == "➕ CREAR NUEVO...":
                    st.info("⚡ Alta Rápida")
                    new_cli_n = st.text_input("Nombre Completo")
                    new_cli_t = st.text_input("Nombre Tienda")
                    cli_final = new_cli_n
                else: 
                    cli_final = cli_sel
                    if not df_deudas.empty:
                        deuda = df_deudas[(df_deudas["cliente"] == cli_final)]["total_pendiente"].sum()
                        if deuda > 0: st.error(f"⚠️ **RIESGO:** Debe **${deuda:,.2f}**")
                        else: st.success("✅ Cliente al día.")
            
            with c2:
                st.subheader("2. Producto")
                prod_sel = st.selectbox("Buscar Producto", lista_p)
                prod_final = None; pre_sug = 0.0
                
                if prod_sel == "➕ CREAR NUEVO...":
                    st.info("⚡ Alta Rápida")
                    prod_final = st.text_input("Descripción Producto")
                else:
                    prod_final = prod_sel
                    if not df_prod.empty:
                        row = df_prod[df_prod["nombre"]==prod_sel]
                        if not row.empty: pre_sug = float(row.iloc[0]["precio_base"])

                cc1, cc2 = st.columns(2)
                cant = cc1.number_input("Cantidad", 1)
                precio = cc2.number_input("Precio Unitario ($)", value=pre_sug, step=0.5)
            
            st.divider()
            obs = st.text_input("📝 Notas (Opcional)", placeholder="Ej: Paga el viernes, dejar en portería...")

            if st.button("💾 GUARDAR PRÉSTAMO", type="primary", use_container_width=True):
                if cli_final and prod_final:
                    if cli_sel == "➕ CREAR NUEVO...": 
                        insertar_registro("clientes", {"nombre": new_cli_n, "tienda": new_cli_t})
                    if prod_sel == "➕ CREAR NUEVO...": 
                        insertar_registro("productos", {"nombre": prod_final, "categoria": "Otros", "precio_base": precio})
                    
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
                    st.success(f"✅ Asignado a {cli_final}"); time.sleep(1); st.rerun()
                else: st.error("Faltan datos.")

    # ==========================================
    # 📍 MÓDULO 2: RUTAS Y COBRO
    # ==========================================
    elif menu == "📍 Rutas y Cobro":
        st.title("📍 Gestión de Cobranza")
        df_pend = cargar_tabla("prestamos")
        if not df_pend.empty: df_pend = df_pend[df_pend["cantidad_pendiente"] > 0]
        
        if df_pend.empty:
            st.success("✅ No hay cobranza pendiente.")
        else:
            cli_visita = st.selectbox("Seleccionar Cliente:", sorted(df_pend["cliente"].unique()))
            datos = df_pend[df_pend["cliente"] == cli_visita].copy()
            deuda_total = datos["total_pendiente"].sum()
            
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
                if st.button("💰 COBRAR TODO (Pagó 100%)", type="primary", use_container_width=True):
                    hoy = datetime.now().isoformat()
                    for i, r in datos.iterrows():
                        cant = int(r["cantidad_pendiente"])
                        monto = float(cant * r["precio_unitario"])
                        insertar_registro("historial", {"fecha_evento": hoy, "usuario_responsable": usuario_actual, "tipo": "COBRO", "cliente": cli_visita, "producto": r["producto"], "cantidad": cant, "monto_operacion": monto})
                        actualizar_prestamo(r["id"], 0, 0)
                    st.toast("✅ ¡Cobro registrado!"); time.sleep(1); st.rerun()
            with c2:
                if st.button("🔙 DEVOLVER TODO (No vendió)", use_container_width=True):
                    hoy = datetime.now().isoformat()
                    for i, r in datos.iterrows():
                        cant = int(r["cantidad_pendiente"])
                        insertar_registro("historial", {"fecha_evento": hoy, "usuario_responsable": usuario_actual, "tipo": "DEVOLUCION", "cliente": cli_visita, "producto": r["producto"], "cantidad": cant, "monto_operacion": 0})
                        actualizar_prestamo(r["id"], 0, 0)
                    st.toast("✅ ¡Devolución registrada!"); time.sleep(1); st.rerun()

            st.markdown("---")
            st.write("##### 📝 Gestión Manual")
            
            edited = st.data_editor(
                datos[["id", "producto", "cantidad_pendiente", "precio_unitario", "observaciones", "Cobrar", "Devolver"]],
                column_config={
                    "id": st.column_config.NumberColumn(disabled=True),
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
                if pay_now > 0: st.success(f"💵 PAGA AHORA: **${pay_now:,.2f}**")
            with cp2:
                if st.button("✅ Procesar Manual", use_container_width=True):
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
    # 🔍 MÓDULO 3: CONSULTAS
    # ==========================================
    elif menu == "🔍 Consultas y Recibos":
        st.title("🔍 Consultas")
        t1, t2, t3 = st.tabs(["📂 Deudas", "📜 Historial", "📇 Kardex Cliente"])
        
        with t1:
            df_p = cargar_tabla("prestamos")
            if not df_p.empty:
                df_p = df_p[df_p["cantidad_pendiente"] > 0]
                c1, c2 = st.columns(2)
                ft = c1.selectbox("Filtro Fecha", ["Todos", "Hoy", "Esta Semana", "Este Mes"])
                fc = c2.multiselect("Filtro Cliente", sorted(df_p["cliente"].unique()))
                
                df_s = df_p.copy()
                hoy = date.today()
                if ft == "Hoy": df_s = df_s[df_s["fecha_registro"] == hoy]
                elif ft == "Esta Semana": df_s = df_s[df_s["fecha_registro"] >= hoy - timedelta(days=hoy.weekday())]
                elif ft == "Este Mes": df_s = df_s[df_s["fecha_registro"] >= hoy.replace(day=1)]
                if fc: df_s = df_s[df_s["cliente"].isin(fc)]
                
                st.dataframe(df_s, use_container_width=True)
                st.metric("Total Mostrado", f"${df_s['total_pendiente'].sum():,.2f}")
                
                if st.button("🖨️ Generar Recibo WhatsApp"):
                    txt = f"*ESTADO DE CUENTA*\n📅 {datetime.now().strftime('%d/%m/%Y')}\n----------------\n"
                    for c in df_s["cliente"].unique():
                        txt += f"👤 {c}:\n"
                        for i, r in df_s[df_s["cliente"]==c].iterrows():
                            txt += f" - {r['producto']} (x{r['cantidad_pendiente']}): ${r['total_pendiente']:,.2f}\n"
                    txt += f"----------------\n*TOTAL: ${df_s['total_pendiente'].sum():,.2f}*"
                    st.code(txt, language="text")

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
                if len(fd)==2: df_hs = df_hs[(df_hs["fecha_evento"].dt.date >= fd[0]) & (df_hs["fecha_evento"].dt.date <= fd[1])]
                
                st.dataframe(df_hs.sort_values("fecha_evento", ascending=False), use_container_width=True)

        with t3:
            st.info("Historia completa del cliente.")
            cli_k = st.selectbox("Seleccionar Cliente", sorted(df_cli["nombre"].unique()) if not df_cli.empty else [])
            if cli_k:
                df_pk = cargar_tabla("prestamos")
                df_hk = cargar_tabla("historial")
                
                kardex = []
                if not df_pk.empty:
                    t = df_pk[df_pk["cliente"]==cli_k]
                    for i,r in t.iterrows(): 
                        kardex.append({"Fecha": str(r["fecha_registro"]), "Acción": "🔴 PRÉSTAMO", "Producto": r["producto"], "Detalle": f"Pendiente: {r['cantidad_pendiente']}"})
                
                if not df_hk.empty:
                    t = df_hk[df_hk["cliente"]==cli_k]
                    for i,r in t.iterrows(): 
                        kardex.append({"Fecha": str(r["fecha_evento"]), "Acción": "🟢 PAGO" if r["tipo"]=="COBRO" else "🟡 DEVOLUCIÓN", "Producto": r["producto"], "Detalle": f"Cant: {r['cantidad']} | ${r['monto_operacion']:,.2f}"})
                
                if kardex:
                    df_k = pd.DataFrame(kardex)
                    df_k["Fecha"] = pd.to_datetime(df_k["Fecha"], utc=True, errors='coerce')
                    df_k = df_k.sort_values("Fecha", ascending=False)
                    df_k["Fecha"] = df_k["Fecha"].dt.date
                    st.dataframe(df_k, use_container_width=True)
                else:
                    st.warning("Sin movimientos.")

    # ==========================================
    # ⚠️ MÓDULO: ANULAR / CORREGIR
    # ==========================================
    elif menu == "⚠️ Anular/Corregir":
        st.title("⚠️ Corrección de Errores")
        st.warning("Aquí puedes ANULAR pagos o devoluciones mal registradas. El stock y la deuda se restaurarán.")
        
        tab_cor, tab_log = st.tabs(["↩️ Deshacer Movimiento", "📜 Historial de Anulaciones"])
        
        with tab_cor:
            df_hist = cargar_tabla("historial")
            if not df_hist.empty:
                col_f1, col_f2 = st.columns(2)
                filtro_c = col_f1.selectbox("Filtrar Cliente", ["Todos"] + sorted(df_hist["cliente"].unique().tolist()))
                
                df_view = df_hist.copy()
                if filtro_c != "Todos":
                    df_view = df_view[df_view["cliente"] == filtro_c]
                
                st.write("Últimos movimientos registrados:")
                
                for index, row in df_view.sort_values("fecha_evento", ascending=False).head(20).iterrows():
                    c1, c2, c3, c4, c5 = st.columns([2, 2, 2, 2, 1])
                    c1.write(f"📅 {row['fecha_evento']}")
                    c2.write(f"👤 {row['cliente']}")
                    c3.write(f"📦 {row['producto']} (x{row['cantidad']})")
                    c4.write(f"💰 {row['tipo']} (${row['monto_operacion']})")
                    
                    if c5.button("ANULAR ❌", key=f"del_{row['id']}"):
                        if anular_movimiento(row['id'], usuario_actual):
                            st.success("¡Movimiento anulado y stock restaurado!")
                            time.sleep(1.5)
                            st.rerun()
            else:
                st.info("No hay movimientos para anular.")

        with tab_log:
            df_anul = cargar_tabla("anulaciones")
            if not df_anul.empty:
                st.dataframe(df_anul.sort_values("created_at", ascending=False), use_container_width=True)
            else:
                st.info("Aún no se han realizado anulaciones.")

    # ==========================================
    # 📊 MÓDULO 4: REPORTES FINANCIEROS
    # ==========================================
    elif menu == "📊 Reportes Financieros":
        st.title("📊 Balance General")
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
    # 🛠️ MÓDULO 5: ADMINISTRACIÓN
    # ==========================================
    elif menu == "🛠️ Administración":
        st.title("🛠️ Administración")
        t1, t2, t3, t4 = st.tabs(["📂 Directorio", "➕ Crear", "✏️ Editar", "💾 Backup"])
        
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
                    n=st.text_input("Nombre *"); t=st.text_input("Tienda"); tel=st.text_input("Tel"); d=st.text_input("Dir"); r1=st.text_input("RUC1"); r2=st.text_input("RUC2")
                    if st.form_submit_button("Crear Cliente"):
                        insertar_registro("clientes", {"nombre":n, "tienda":t, "telefono":tel, "direccion":d, "ruc1":r1, "ruc2":r2}); st.rerun()
            with c2:
                with st.form("fp"):
                    n=st.text_input("Prod *"); c=st.selectbox("Cat", ["Varios", "Focos", "Cables"]); p=st.number_input("Precio Base")
                    if st.form_submit_button("Crear Prod"):
                        insertar_registro("productos", {"nombre":n, "categoria":c, "precio_base":p}); st.rerun()

        with t3:
            mod = st.radio("Editar:", ["Clientes", "Productos"], horizontal=True)
            if mod == "Clientes" and not df_cli.empty:
                s = st.selectbox("Cli", df_cli["nombre"].unique())
                d = df_cli[df_cli["nombre"]==s].iloc[0]
                with st.form("fe"):
                    nn=st.text_input("Nom", d["nombre"]); nt=st.text_input("Tie", d.get("tienda","")); ntel=st.text_input("Tel", d.get("telefono","")); nd=st.text_input("Dir", d.get("direccion","")); nr1=st.text_input("RUC1", d.get("ruc1","")); nr2=st.text_input("RUC2", d.get("ruc2",""))
                    if st.form_submit_button("Actualizar"):
                        editar_cliente_global(int(d["id"]), {"nombre":nn, "tienda":nt, "telefono":ntel, "direccion":nd, "ruc1":nr1, "ruc2":nr2}, d["nombre"])
                        st.success("Actualizado"); time.sleep(1); st.rerun()
            elif mod == "Productos" and not df_prod.empty:
                s = st.selectbox("Prod", df_prod["nombre"].unique())
                d = df_prod[df_prod["nombre"]==s].iloc[0]
                with st.form("fep"):
                    nn=st.text_input("Nom", d["nombre"]); np=st.number_input("Pre", float(d["precio_base"])); nc=st.text_input("Cat", d["categoria"])
                    if st.form_submit_button("Actualizar"):
                        editar_producto_global(int(d["id"]), {"nombre":nn, "precio_base":np, "categoria":nc}, d["nombre"])
                        st.success("Actualizado"); time.sleep(1); st.rerun()

        with t4:
            st.info("Descarga Excel limpia.")
            def clean_csv(df, map_cols): return df.rename(columns=map_cols).to_csv(index=False).encode('utf-8')
            c1, c2 = st.columns(2)
            
            # CARGA DE DATOS PARA BACKUP (FIX NAME ERROR)
            df_p_full = cargar_tabla("prestamos")
            df_h_full = cargar_tabla("historial")
            
            if not df_cli.empty: c1.download_button("📥 Clientes", clean_csv(df_cli, {"nombre": "Cliente", "ruc1": "RUC"}), "cli.csv", "text/csv")
            if not df_p_full.empty: c1.download_button("📥 Préstamos", clean_csv(df_p_full, {"cliente": "Cliente", "total_pendiente": "Deuda"}), "prest.csv", "text/csv")
            if not df_h_full.empty: c2.download_button("📥 Historial", clean_csv(df_h_full, {"fecha_evento": "Fecha", "monto_operacion": "Monto"}), "hist.csv", "text/csv")
            if not df_prod.empty: c2.download_button("📥 Productos", clean_csv(df_prod, {"nombre": "Producto"}), "prod.csv", "text/csv")

# --- INICIO ---
if check_login():
    main_app()