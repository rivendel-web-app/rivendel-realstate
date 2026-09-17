import streamlit as st
import sqlite3
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
import streamlit_authenticator as stauth
import bcrypt

st.set_page_config(page_title="Gestión e Históricos Inmobiliarios", page_icon="🏢", layout="wide")

DB_PATH = 'modelo_definitivo.db'
VALOR_UF_CLP = 40865.0

# ------------------------------------------------------------------
# FUNCIONES DE SEGURIDAD Y AUDITORÍA
# ------------------------------------------------------------------
def hash_pw(password: str) -> str:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def registrar_acceso(username, email, evento):
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO auditoria_accesos (username, email, fecha_hora, evento)
            VALUES (?, ?, ?, ?)
        """, (username, email, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), evento))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Error registrando acceso: {e}")

def registrar_edicion(username, propiedad_id, modulo, descripcion):
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO auditoria_ediciones (username, propiedad_id, modulo, descripcion, fecha_hora)
            VALUES (?, ?, ?, ?, ?)
        """, (username, propiedad_id, modulo, descripcion, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Error registrando edición: {e}")

def obtener_config_usuarios():
    conn = sqlite3.connect(DB_PATH)
    query = "SELECT username, nombre, email, password_hash, rol FROM usuarios WHERE activo = 1"
    df_usr = pd.read_sql_query(query, conn)
    conn.close()
    
    credentials = {"usernames": {}}
    for _, row in df_usr.iterrows():
        credentials["usernames"][row["username"]] = {
            "email": row["email"],
            "name": row["nombre"],
            "password": row["password_hash"],
            "role": row["rol"]
        }
    return credentials

# ------------------------------------------------------------------
# AUTENTICACIÓN DINÁMICA
# ------------------------------------------------------------------
credentials = obtener_config_usuarios()

authenticator = stauth.Authenticate(
    credentials,
    'beco_auth_cookie',
    'beco_auth_signature_key_2026',
    30
)

authenticator.login('main', fields={'Form name': '🏢 Acceso al Sistema Inmobiliario'})

if st.session_state["authentication_status"] is False:
    st.error("❌ Usuario o contraseña incorrectos.")
    st.stop()
elif st.session_state["authentication_status"] is None:
    st.info("👋 Por favor, ingrese sus credenciales para acceder al sistema.")
    st.stop()

# Usuario Autenticado Correctamente
username = st.session_state["username"]
user_info = credentials['usernames'].get(username, {})
user_role = user_info.get('role', 'ejecutivo')

if "login_registrado" not in st.session_state:
    registrar_acceso(username, user_info.get('email', '-'), 'LOGIN_EXITOSO')
    st.session_state["login_registrado"] = True

# ------------------------------------------------------------------
# ESTILOS CSS PREMIUM (EXECUTIVE DASHBOARD)
# ------------------------------------------------------------------
st.markdown("""
<style>
    .main {
        background-color: #F8FAFC;
    }
    
    .section-header {
        font-size: 1.35rem !important;
        font-weight: 700 !important;
        color: #0F172A !important;
        margin-top: 1rem !important;
        margin-bottom: 0.8rem !important;
        letter-spacing: -0.02em !important;
        border-left: 4px solid #2563EB;
        padding-left: 10px;
    }
    
    div[data-testid="stMetric"] {
        background: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: 12px;
        padding: 16px 20px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -1px rgba(0, 0, 0, 0.03);
    }
    
    div[data-testid="stMetricLabel"] > div {
        font-size: 0.85rem !important;
        font-weight: 700 !important;
        color: #64748B !important;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    
    div[data-testid="stMetricValue"] > div {
        font-size: 1.75rem !important;
        font-weight: 800 !important;
        color: #0F172A !important;
    }

    .yield-card {
        background-color: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: 12px;
        padding: 18px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.02);
    }
</style>
""", unsafe_allow_html=True)

# ------------------------------------------------------------------
# FUNCIONES AUXILIARES Y CONSULTAS SQL
# ------------------------------------------------------------------
def safe_float(val):
    try:
        if pd.isna(val) or str(val).strip() in ['-', 'nan', 'NaN', '']:
            return 0.0
        return float(val)
    except:
        return 0.0

def cargar_datos_historicos(fecha_consulta):
    conn = sqlite3.connect(DB_PATH)
    str_fecha = fecha_consulta.strftime('%Y-%m-%d')
    
    query = """
    SELECT 
        p.id AS "ID Fila",
        COALESCE(p.dueno, '-') AS "Dueño",
        p.edificio AS "Edificio",
        p.sigla_original AS "Tipo",
        p.num_propiedad AS "N° Prop.",
        COALESCE(p.direccion, '-') AS "Dirección",
        COALESCE(p.comuna, '-') AS "Comuna",
        p.piso AS "Piso",
        p.m2 AS "M²",
        COALESCE(a.nombre_arrendatario, 'Sin Arrendatario') AS "Arrendatario",
        COALESCE(a.tipo_arrendatario, 'Empresa') AS "Tipo Arrendatario",
        COALESCE(a.representante_legal, '-') AS "Representante Legal",
        COALESCE(c.impuesto_estado, 'Exento') AS "Impuesto IVA",
        COALESCE(ca.arriendo_neto_uf, 0.0) AS "Arriendo Neto (UF)",
        COALESCE(ca.monto_iva_uf, 0.0) AS "Monto IVA (UF)",
        COALESCE(ca.valor_arriendo_total_uf, 0.0) AS "Arriendo Total (UF)",
        COALESCE(ca.valor_arriendo_total_clp, 0.0) AS "Arriendo Total ($)",
        COALESCE(c.monto_garantia_uf, 0.0) AS "Garantía (UF)",
        c.fecha_arriendo AS "Inicio Arriendo",
        c.fecha_vencimiento_original AS "Vencimiento",
        COALESCE(c.contrato_ok_estado, 'Vacante') AS "Estado Contrato",
        p.rol_avaluo AS "Rol Avalúo",
        f.precio_total_uf AS "Precio Compra (UF)",
        f.banco_acreedor AS "Banco Acreedor",
        COALESCE(g.seguro_anual_uf, 0.0) AS "Seguro Anual (UF)",
        COALESCE(g.contribuciones_anual_clp, 0.0) AS "Contribuciones Anual ($)",
        COALESCE(g.gasto_comun_anual_clp, 0.0) AS "Gasto Común Anual ($)",
        ca.comentarios AS "Comentarios",
        c.id AS "contrato_id",
        g.id AS "gasto_id"
    FROM propiedades p
    LEFT JOIN compras_financiamiento f ON f.propiedad_id = p.id
    LEFT JOIN gastos_propiedad g ON g.propiedad_id = p.id
        AND (g.fecha_inicio IS NULL OR g.fecha_inicio <= ?)
        AND (g.fecha_fin IS NULL OR g.fecha_fin >= ?)
    LEFT JOIN contratos_arriendo c ON c.propiedad_id = p.id 
        AND (c.fecha_arriendo IS NULL OR c.fecha_arriendo <= ?)
        AND (c.fecha_fin IS NULL OR c.fecha_fin >= ?)
    LEFT JOIN arrendatarios a ON c.arrendatario_id = a.id
    LEFT JOIN canones_arriendo ca ON ca.contrato_id = c.id
    WHERE (
        EXISTS (
            SELECT 1 FROM contratos_arriendo c_sub 
            WHERE c_sub.propiedad_id = p.id AND c_sub.fecha_arriendo <= ?
        )
        OR EXISTS (
            SELECT 1 FROM gastos_propiedad g_sub 
            WHERE g_sub.propiedad_id = p.id AND g_sub.fecha_inicio <= ?
        )
    )
    ORDER BY p.id ASC
    """
    df = pd.read_sql_query(query, conn, params=(str_fecha, str_fecha, str_fecha, str_fecha, str_fecha, str_fecha))
    conn.close()
    
    df["Arriendo Total ($)"] = df["Arriendo Total (UF)"] * VALOR_UF_CLP
    return df

def guardar_cambio_historico(prop_id, contrato_id_ant, gasto_id_ant, fecha_cambio, nuevo_neto_uf, tratamiento_iva, nuevo_arrendatario, tipo_arr, rep_legal, inicio_contrato, venc_contrato, estado_contrato, garantia_uf, comentario, contrib_clp, ggcc_clp, seguro_uf):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    fecha_fin_auto = (fecha_cambio - timedelta(days=1)).strftime('%Y-%m-%d')
    fecha_cambio_str = fecha_cambio.strftime('%Y-%m-%d')

    if gasto_id_ant and pd.notna(gasto_id_ant):
        cursor.execute("UPDATE gastos_propiedad SET fecha_fin = ? WHERE id = ?", (fecha_fin_auto, int(gasto_id_ant)))
    
    cursor.execute("""
    INSERT INTO gastos_propiedad (propiedad_id, seguro_anual_uf, contribuciones_anual_clp, gasto_comun_anual_clp, fecha_inicio, fecha_fin)
    VALUES (?, ?, ?, ?, ?, NULL)
    """, (prop_id, seguro_uf, contrib_clp, ggcc_clp, fecha_cambio_str))
    
    if contrato_id_ant and pd.notna(contrato_id_ant):
        cursor.execute("UPDATE contratos_arriendo SET fecha_fin = ? WHERE id = ?", (fecha_fin_auto, int(contrato_id_ant)))
    
    nombre_arr = nuevo_arrendatario.strip() if nuevo_arrendatario else "Sin Arrendatario"
    cursor.execute("INSERT OR IGNORE INTO arrendatarios (nombre_arrendatario, tipo_arrendatario, representante_legal) VALUES (?, ?, ?)", (nombre_arr, tipo_arr, rep_legal))
    cursor.execute("UPDATE arrendatarios SET tipo_arrendatario = ?, representante_legal = ? WHERE nombre_arrendatario = ?", (tipo_arr, rep_legal, nombre_arr))
    cursor.execute("SELECT id FROM arrendatarios WHERE nombre_arrendatario = ?", (nombre_arr,))
    arr_id = cursor.fetchone()[0]
    
    if tratamiento_iva == "Afecto":
        monto_iva_uf = nuevo_neto_uf * 0.19
        total_uf = nuevo_neto_uf * 1.19
    else:
        monto_iva_uf = 0.0
        total_uf = nuevo_neto_uf

    cursor.execute("""
    INSERT INTO contratos_arriendo (propiedad_id, arrendatario_id, fecha_arriendo, fecha_vencimiento_original, fecha_fin, impuesto_estado, monto_garantia_uf, contrato_ok_estado)
    VALUES (?, ?, ?, ?, NULL, ?, ?, ?)
    """, (prop_id, arr_id, fecha_cambio_str, venc_contrato.strftime('%Y-%m-%d'), tratamiento_iva, garantia_uf, estado_contrato))
    nuevo_contrato_id = cursor.lastrowid
    
    cursor.execute("""
    INSERT INTO canones_arriendo (contrato_id, arriendo_neto_uf, monto_iva_uf, valor_arriendo_total_uf, valor_arriendo_total_clp, comentarios)
    VALUES (?, ?, ?, ?, ?, ?)
    """, (nuevo_contrato_id, nuevo_neto_uf, monto_iva_uf, total_uf, total_uf * VALOR_UF_CLP, f"[{fecha_cambio_str}] {comentario}"))
    
    conn.commit()
    conn.close()
    
    registrar_edicion(username, prop_id, "CONTRATO_Y_GASTOS", f"Nuevo canon {nuevo_neto_uf} UF | Arrendatario: {nombre_arr} | Comentario: {comentario}")
    return fecha_fin_auto

def cargar_excel_incremental(uploaded_file):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    df_raw = pd.read_excel(uploaded_file, sheet_name='Activos Detalles')
    df_data = df_raw.iloc[1:].copy()
    
    nuevos_agregados = 0
    omitidos = 0
    
    for idx, row in df_data.iterrows():
        if pd.isna(row.iloc[2]) or pd.isna(row.iloc[7]) or pd.isna(row.iloc[13]): continue
        
        dueno = str(row.iloc[1]).strip() if pd.notna(row.iloc[1]) else "Sin Sociedad"
        edificio = str(row.iloc[2]).strip()
        tipo_sigla = str(row.iloc[7]).strip()
        num_prop = str(row.iloc[13]).strip()
        
        cursor.execute("""
            SELECT id FROM propiedades 
            WHERE TRIM(edificio) = ? AND TRIM(sigla_original) = ? AND TRIM(num_propiedad) = ?
        """, (edificio, tipo_sigla, num_prop))
        
        if cursor.fetchone():
            omitidos += 1
            continue
            
        cursor.execute("""
            INSERT INTO propiedades (dueno, edificio, direccion, comuna, tipo_original, sigla_original, num_propiedad, piso, rol_avaluo, m2)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            dueno, edificio, str(row.iloc[3]), str(row.iloc[4]),
            str(row.iloc[6]), tipo_sigla, num_prop, str(row.iloc[16]), str(row.iloc[17]), safe_float(row.iloc[18])
        ))
        prop_id = cursor.lastrowid
        
        cursor.execute("INSERT INTO compras_financiamiento VALUES (NULL, ?, ?, ?)", (
            prop_id, safe_float(row.iloc[22]), str(row.iloc[25])
        ))
        
        cursor.execute("INSERT INTO gastos_propiedad VALUES (NULL, ?, ?, ?, ?, date('now'), NULL)", (
            prop_id, safe_float(row.iloc[39]), safe_float(row.iloc[40]), safe_float(row.iloc[53])
        ))
        
        arr_nom = str(row.iloc[41]).strip() if pd.notna(row.iloc[41]) else "Sin Arrendatario"
        tipo_arr = str(row.iloc[42]).strip() if len(row) > 42 and pd.notna(row.iloc[42]) else "Empresa"
        rep_legal = str(row.iloc[46]).strip() if len(row) > 46 and pd.notna(row.iloc[46]) else "-"
        
        cursor.execute("INSERT OR IGNORE INTO arrendatarios (nombre_arrendatario, tipo_arrendatario, representante_legal) VALUES (?, ?, ?)", (arr_nom, tipo_arr, rep_legal))
        cursor.execute("SELECT id FROM arrendatarios WHERE nombre_arrendatario = ?", (arr_nom,))
        arr_id = cursor.fetchone()[0]
        
        neto_uf = safe_float(row.iloc[48])
        total_uf = safe_float(row.iloc[50])
        
        cursor.execute("INSERT INTO contratos_arriendo VALUES (NULL, ?, ?, date('now'), ?, NULL, 'Exento', 0.0, 'OK')", (
            prop_id, arr_id, str(row.iloc[55])[:10] if pd.notna(row.iloc[55]) else None
        ))
        c_id = cursor.lastrowid
        
        cursor.execute("INSERT INTO canones_arriendo VALUES (NULL, ?, ?, 0.0, ?, ?, 'Carga Masiva Excel')", (
            c_id, neto_uf, total_uf, total_uf * VALOR_UF_CLP
        ))
        
        nuevos_agregados += 1
        
    conn.commit()
    conn.close()
    
    registrar_edicion(username, None, "CARGA_MASIVA_EXCEL", f"Carga incremental: {nuevos_agregados} creados | {omitidos} omitidos")
    return nuevos_agregados, omitidos

# ------------------------------------------------------------------
# INTERFAZ PRINCIPAL
# ------------------------------------------------------------------
col_tit, col_usr = st.columns([3, 1])
with col_tit:
    st.markdown("<h1 style='font-size: 2.1rem; font-weight: 800; color: #0F172A; margin-bottom: 0px;'>🏢 Executive Real Estate Dashboard</h1>", unsafe_allow_html=True)
    st.caption("Sistema de Gestión Patrimonial e Histórico Inmobiliario")

with col_usr:
    st.write(f"👤 **{user_info.get('name', username)}** ({user_role.upper()})")
    authenticator.logout('🚪 Cerrar Sesión', 'main')

st.markdown("---")

if "mensaje_exito" in st.session_state:
    st.success(st.session_state["mensaje_exito"])
    del st.session_state["mensaje_exito"]

# SIDEBAR
st.sidebar.header("📅 Consulta Temporal")
fecha_consulta = st.sidebar.date_input("Foto del portafolio al:", value=datetime.today())

st.sidebar.header("🔍 Filtros Dinámicos")
df_base = cargar_datos_historicos(fecha_consulta)

if not df_base.empty:
    filtro_dueno = st.sidebar.multiselect("Sociedad / Dueño:", options=df_base["Dueño"].dropna().unique(), default=[])
    filtro_edificio = st.sidebar.multiselect("Edificio:", options=df_base["Edificio"].dropna().unique(), default=[])
    filtro_arrendatario = st.sidebar.multiselect("Arrendatario:", options=df_base["Arrendatario"].dropna().unique(), default=[])
    filtro_tipo = st.sidebar.multiselect("Tipo de Activo:", options=df_base["Tipo"].dropna().unique(), default=[])
    filtro_texto = st.sidebar.text_input("🔎 Búsqueda rápida:", "")

    df = df_base.copy()
    if filtro_dueno: df = df[df["Dueño"].isin(filtro_dueno)]
    if filtro_edificio: df = df[df["Edificio"].isin(filtro_edificio)]
    if filtro_arrendatario: df = df[df["Arrendatario"].isin(filtro_arrendatario)]
    if filtro_tipo: df = df[df["Tipo"].isin(filtro_tipo)]
    if filtro_texto: df = df[df.apply(lambda row: row.astype(str).str.contains(filtro_texto, case=False).any(), axis=1)]
else:
    df = df_base.copy()

# CONTROL DE PESTAÑAS SEGÚN ROL DE USUARIO
if user_role == 'admin':
    tab_consulta, tab_mantenedor, tab_admin = st.tabs(["📊 Executive Overview", "📝 Mantenedor / Carga Masiva", "⚙️ Gestión de Usuarios & Auditoría"])
else:
    tab_consulta, = st.tabs(["📊 Executive Overview"])

with tab_consulta:
    if df.empty:
        st.warning(f"⚠️ No se registran activos o contratos vigentes con fecha anterior o igual al {fecha_consulta.strftime('%d/%m/%Y')}.")
    else:
        filas_seleccionadas = st.session_state.get("tabla_activos", {}).get("selection", {}).get("rows", [])
        
        if filas_seleccionadas:
            df_kpis = df.iloc[filas_seleccionadas]
            subtitulo_kpis = f"Resumen de Unidades Seleccionadas ({len(df_kpis)} de {len(df)})"
        else:
            df_kpis = df.copy()
            subtitulo_kpis = f"Portafolio al {fecha_consulta.strftime('%d/%m/%Y')} ({len(df_kpis)} Activos)"

        df_of = df_kpis[df_kpis["Tipo"] == "OF"]
        df_bd = df_kpis[df_kpis["Tipo"] == "BD"]
        df_bx = df_kpis[df_kpis["Tipo"] == "BX"]

        total_unidades = len(df_kpis)
        arrendadas = len(df_kpis[df_kpis["Arrendatario"] != "Sin Arrendatario"])
        vacantes = total_unidades - arrendadas
        pct_ocupacion = (arrendadas / total_unidades * 100) if total_unidades > 0 else 0

        ingreso_neto_total_uf = df_kpis['Arriendo Neto (UF)'].sum()
        ingreso_neto_total_clp = ingreso_neto_total_uf * VALOR_UF_CLP

        st.markdown(f"<div class='section-header'>{subtitulo_kpis}</div>", unsafe_allow_html=True)
        
        col_pie_ocu, col_kpis_der = st.columns([1.1, 2])

        with col_pie_ocu:
            df_ocu_pie = pd.DataFrame({
                "Estado": ["Arrendado", "Vacante"],
                "Unidades": [arrendadas, vacantes]
            })
            fig_pie_ocu = px.pie(
                df_ocu_pie,
                names="Estado",
                values="Unidades",
                hole=0.55,
                title=f"<b>Ocupación: {pct_ocupacion:.1f}%</b>",
                color="Estado",
                color_discrete_map={"Arrendado": "#1E3A8A", "Vacante": "#EF4444"}
            )
            
            fig_pie_ocu.update_traces(
                textinfo="value+percent",
                textposition="inside",
                insidetextorientation="horizontal",
                insidetextfont=dict(size=13, color="white")
            )
            
            fig_pie_ocu.update_layout(
                margin=dict(t=30, b=10, l=10, r=10), 
                height=230, 
                legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5)
            )
            st.plotly_chart(fig_pie_ocu, use_container_width=True)

        with col_kpis_der:
            k1, k2 = st.columns(2)
            k1.metric("Activos Totales", f"{total_unidades} Unid.", delta=f"{arrendadas} Arrendadas")
            k2.metric("Ingreso Neto Mensual", f"{ingreso_neto_total_uf:,.2f} UF", f"${ingreso_neto_total_clp:,.0f} CLP")
            
            st.markdown("<div style='margin-top: 10px;'></div>", unsafe_allow_html=True)
            k3, k4 = st.columns(2)
            k3.metric("Superficie Útil (OF + BD)", f"{(df_of['M²'].sum() + df_bd['M²'].sum()):,.2f} m²")
            k4.metric("Estacionamientos (BX)", f"{len(df_bx)} Unidades")

        st.markdown("---")

        st.markdown("<div class='section-header'>Concentración de Ingresos Netos</div>", unsafe_allow_html=True)
        col_g1, col_g2 = st.columns(2)

        with col_g1:
            df_edif = df_kpis.groupby("Edificio")["Arriendo Neto (UF)"].sum().reset_index()
            df_edif = df_edif.sort_values(by="Arriendo Neto (UF)", ascending=True)
            fig_bar_edif = px.bar(
                df_edif,
                x="Arriendo Neto (UF)",
                y="Edificio",
                orientation="h",
                title="<b>Ingreso Neto por Edificio (UF)</b>",
                text_auto=".2f",
                color_discrete_sequence=["#2563EB"]
            )
            fig_bar_edif.update_layout(
                margin=dict(t=30, b=10, l=10, r=10), 
                height=250, 
                xaxis=dict(showgrid=False, title=""),
                yaxis=dict(title="")
            )
            st.plotly_chart(fig_bar_edif, use_container_width=True)

        with col_g2:
            df_cli = df_kpis.groupby("Arrendatario")["Arriendo Neto (UF)"].sum().reset_index()
            df_cli = df_cli.sort_values(by="Arriendo Neto (UF)", ascending=True)
            fig_bar_cli = px.bar(
                df_cli,
                x="Arriendo Neto (UF)",
                y="Arrendatario",
                orientation="h",
                title="<b>Ingreso Neto por Cliente (UF)</b>",
                text_auto=".2f",
                color_discrete_sequence=["#059669"]
            )
            fig_bar_cli.update_layout(
                margin=dict(t=30, b=10, l=10, r=10), 
                height=250, 
                xaxis=dict(showgrid=False, title=""),
                yaxis=dict(title="")
            )
            st.plotly_chart(fig_bar_cli, use_container_width=True)

        st.markdown("---")

        st.markdown("<div class='section-header'>Análisis por Tipología (Base Neto)</div>", unsafe_allow_html=True)

        def calcular_yields(df_sub):
            m2 = df_sub['M²'].sum()
            renta_neto_uf = df_sub['Arriendo Neto (UF)'].sum()
            precio_uf = df_sub['Precio Compra (UF)'].sum()
            seguro_uf = df_sub['Seguro Anual (UF)'].sum()
            contrib_uf = df_sub['Contribuciones Anual ($)'].sum() / VALOR_UF_CLP
            ggcc_uf = df_sub['Gasto Común Anual ($)'].sum() / VALOR_UF_CLP
            gastos_totales_uf = seguro_uf + contrib_uf + ggcc_uf
            gross_income_annual = renta_neto_uf * 12
            net_income_annual = gross_income_annual - gastos_totales_uf
            gross_yield = (gross_income_annual / precio_uf * 100) if precio_uf > 0 else 0
            net_yield = (net_income_annual / precio_uf * 100) if precio_uf > 0 else 0
            return m2, renta_neto_uf, gross_yield, net_yield

        def get_ocupacion(df_sub):
            tot = len(df_sub)
            arr = len(df_sub[df_sub["Arrendatario"] != "Sin Arrendatario"])
            return (arr / tot * 100) if tot > 0 else 0

        col_of, col_bd, col_bx = st.columns(3)

        with col_of:
            m2, renta, gross, net = calcular_yields(df_of)
            avg_rent = (renta / m2) if m2 > 0 else 0
            ocu = get_ocupacion(df_of)
            st.markdown(f"""
            <div class='yield-card'>
                <h4 style='color: #1E3A8A; margin-bottom: 10px;'>🏢 OFICINAS</h4>
                <p style='margin: 4px 0;'>• <b>Unidades:</b> {len(df_of)} | <b>Ocupación:</b> <span style='color:#2563EB;'>{ocu:.1f}%</span></p>
                <p style='margin: 4px 0;'>• <b>Superficie:</b> {m2:,.2f} m²</p>
                <p style='margin: 4px 0;'>• <b>Renta Promedio:</b> <code>{avg_rent:.2f} UF/m²</code></p>
                <p style='margin: 4px 0;'>• <b>Gross Yield:</b> <code>{gross:.2f}%</code></p>
                <p style='margin: 4px 0;'>• <b>Net Yield:</b> <b style='color:#059669;'>{net:.2f}%</b></p>
            </div>
            """, unsafe_allow_html=True)

        with col_bd:
            m2, renta, gross, net = calcular_yields(df_bd)
            avg_rent = (renta / m2) if m2 > 0 else 0
            ocu = get_ocupacion(df_bd)
            st.markdown(f"""
            <div class='yield-card'>
                <h4 style='color: #065F46; margin-bottom: 10px;'>📦 BODEGAS</h4>
                <p style='margin: 4px 0;'>• <b>Unidades:</b> {len(df_bd)} | <b>Ocupación:</b> <span style='color:#2563EB;'>{ocu:.1f}%</span></p>
                <p style='margin: 4px 0;'>• <b>Superficie:</b> {m2:,.2f} m²</p>
                <p style='margin: 4px 0;'>• <b>Renta Promedio:</b> <code>{avg_rent:.2f} UF/m²</code></p>
                <p style='margin: 4px 0;'>• <b>Gross Yield:</b> <code>{gross:.2f}%</code></p>
                <p style='margin: 4px 0;'>• <b>Net Yield:</b> <b style='color:#059669;'>{net:.2f}%</b></p>
            </div>
            """, unsafe_allow_html=True)

        with col_bx:
            cant = len(df_bx)
            m2, renta, gross, net = calcular_yields(df_bx)
            avg_rent_unit = (renta / cant) if cant > 0 else 0
            ocu = get_ocupacion(df_bx)
            st.markdown(f"""
            <div class='yield-card'>
                <h4 style='color: #334155; margin-bottom: 10px;'>🚗 ESTACIONAMIENTOS</h4>
                <p style='margin: 4px 0;'>• <b>Unidades:</b> {cant} | <b>Ocupación:</b> <span style='color:#2563EB;'>{ocu:.1f}%</span></p>
                <p style='margin: 4px 0;'>• <b>Base:</b> N/A (Unitario)</p>
                <p style='margin: 4px 0;'>• <b>Renta Promedio:</b> <code>{avg_rent_unit:.2f} UF/Unid</code></p>
                <p style='margin: 4px 0;'>• <b>Gross Yield:</b> <code>{gross:.2f}%</code></p>
                <p style='margin: 4px 0;'>• <b>Net Yield:</b> <b style='color:#059669;'>{net:.2f}%</b></p>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("---")

        st.markdown("<div class='section-header'>Tabla General de Activos (Vista Completa)</div>", unsafe_allow_html=True)
        
        columnas_vista = [col for col in df.columns if col not in ["contrato_id", "gasto_id"]]
        
        st.dataframe(
            df[columnas_vista], 
            use_container_width=True, 
            hide_index=True,
            on_select="rerun",
            selection_mode="multi-row",
            key="tabla_activos",
            column_config={
                "M²": st.column_config.NumberColumn(format="%.2f m²"),
                "Arriendo Neto (UF)": st.column_config.NumberColumn(format="%.2f UF"),
                "Monto IVA (UF)": st.column_config.NumberColumn(format="%.2f UF"),
                "Arriendo Total (UF)": st.column_config.NumberColumn(format="%.2f UF"),
                "Arriendo Total ($)": st.column_config.NumberColumn(format="$ %,d CLP"),
                "Garantía (UF)": st.column_config.NumberColumn(format="%.2f UF"),
                "Precio Compra (UF)": st.column_config.NumberColumn(format="%.2f UF"),
                "Seguro Anual (UF)": st.column_config.NumberColumn(format="%.2f UF"),
                "Contribuciones Anual ($)": st.column_config.NumberColumn(format="$ %,d CLP"),
                "Gasto Común Anual ($)": st.column_config.NumberColumn(format="$ %,d CLP")
            }
        )

        if filas_seleccionadas and user_role == 'admin':
            ultimo_sel = df.iloc[filas_seleccionadas[-1]]
            st.success(f"📌 Activo Seleccionado: **ID {ultimo_sel['ID Fila']} | {ultimo_sel['Tipo']} {ultimo_sel['N° Prop.']} ({ultimo_sel['Edificio']})**")
            if st.button("📝 Ir a Editar este Activo en el Mantenedor"):
                st.session_state["activo_a_editar"] = ultimo_sel["ID Fila"]

if user_role == 'admin':
    with tab_mantenedor:
        st.subheader("🛠️ Mantenedor de Registro Histórico y Operativo")
        
        with st.expander("📥 Carga Masiva de Nuevos Activos desde Excel", expanded=False):
            st.markdown("Suba una planilla Excel (`Planilla Propiedades IA.xlsx`). El sistema registrará únicamente los **activos nuevos** por la combinación **`Edificio + Tipo + N° Propiedad`**.")
            file_excel = st.file_uploader("Seleccionar Planilla Excel:", type=["xlsx", "xls"])
            
            if file_excel:
                if st.button("🚀 Cargar / Anexar Nuevos Activos"):
                    agregados, omitidos = cargar_excel_incremental(file_excel)
                    st.session_state["mensaje_exito"] = f"✅ Proceso Finalizado: {agregados} activos nuevos registrados | {omitidos} existentes protegidos."
                    st.rerun()

        st.markdown("---")

        if not df_base.empty:
            id_defecto = st.session_state.get("activo_a_editar", df_base["ID Fila"].iloc[0])
            opciones_prop = [f"ID {r['ID Fila']} | {r['Tipo']} {r['N° Prop.']} ({r['Edificio']}) - Arrendatario: {r['Arrendatario']}" for _, r in df_base.iterrows()]
            idx_defecto = next((i for i, opt in enumerate(opciones_prop) if opt.startswith(f"ID {id_defecto} |")), 0)
            
            prop_sel = st.selectbox("Seleccionar Activo a Modificar:", opciones_prop, index=idx_defecto)
            if prop_sel:
                id_sel = int(prop_sel.split(" | ")[0].replace("ID ", ""))
                fila_sel = df_base[df_base["ID Fila"] == id_sel].iloc[0]
                
                st.caption(f"Ficha Referencia | Contrato ID: `{fila_sel['contrato_id']}` | Gasto ID: `{fila_sel['gasto_id']}` | Rol: `{fila_sel['Rol Avalúo']}`")
                st.markdown("---")

                with st.form("form_mantenedor"):
                    st.markdown("#### 1️⃣ Módulo A: Gestión Contractual y Comercial")
                    col_a1, col_a2 = st.columns(2)
                    
                    with col_a1:
                        nuevo_arrendatario = st.text_input("Arrendatario (Razón Social):", value=str(fila_sel['Arrendatario']) if fila_sel['Arrendatario'] != 'Sin Arrendatario' else "")
                        tipo_arr = st.selectbox("Tipo de Arrendatario:", ["Empresa", "Persona Natural"], index=0 if fila_sel['Tipo Arrendatario'] == 'Empresa' else 1)
                        rep_legal = st.text_input("Representante Legal (Nombre Persona):", value=str(fila_sel['Representante Legal']) if fila_sel['Representante Legal'] != '-' else "")
                        tratamiento_iva = st.radio("Tratamiento Tributario:", ["Exento", "Afecto"], index=0 if fila_sel['Impuesto IVA'] == 'Exento' else 1, horizontal=True)
                        nuevo_neto_uf = st.number_input("Canon de Arriendo NETO Mensual (UF):", value=float(fila_sel['Arriendo Neto (UF)']), step=0.1)
                        garantia_uf = st.number_input("Garantía Retenida (UF):", value=float(fila_sel['Garantía (UF)']), step=0.1)

                    with col_a2:
                        inicio_contrato = st.date_input("Fecha Inicio Arriendo / Contrato:", value=datetime.today())
                        venc_contrato = st.date_input("Fecha Vencimiento del Contrato:", value=datetime.today())
                        fecha_cambio = st.date_input("Fecha Inicio de Cambio (Hito Histórico):", value=datetime.today())
                        estado_contrato = st.selectbox("Estado del Contrato:", ["OK", "En Salida", "Renovado", "Vacante"], index=0)
                        
                        fecha_fin_sugerida = fecha_cambio - timedelta(days=1)
                        st.info(f"💡 Cierre automático del registro previo: **{fecha_fin_sugerida.strftime('%d/%m/%Y')}**")

                    comentario = st.text_area("Motivo del Cambio / Observación:", "")

                    st.markdown("---")
                    st.markdown("#### 2️⃣ Módulo B: Gastos Fijos Operativos")
                    col_b1, col_b2, col_b3 = st.columns(3)
                    
                    with col_b1:
                        contrib_clp = st.number_input("Contribuciones Anuales ($ CLP):", value=float(fila_sel['Contribuciones Anual ($)']), step=1000.0)
                    with col_b2:
                        ggcc_clp = st.number_input("Gasto Común Anual / Vacancia ($ CLP):", value=float(fila_sel['Gasto Común Anual ($)']), step=1000.0)
                    with col_b3:
                        seguro_uf = st.number_input("Seguro Anual (UF):", value=float(fila_sel['Seguro Anual (UF)']), step=0.1)

                    st.markdown("---")
                    btn_guardar = st.form_submit_button("💾 Guardar Cambios con Trazabilidad Completa")

                    if btn_guardar:
                        fecha_cerrada = guardar_cambio_historico(
                            prop_id=id_sel,
                            contrato_id_ant=fila_sel['contrato_id'],
                            gasto_id_ant=fila_sel['gasto_id'],
                            fecha_cambio=fecha_cambio,
                            nuevo_neto_uf=nuevo_neto_uf,
                            tratamiento_iva=tratamiento_iva,
                            nuevo_arrendatario=nuevo_arrendatario,
                            tipo_arr=tipo_arr,
                            rep_legal=rep_legal,
                            inicio_contrato=inicio_contrato,
                            venc_contrato=venc_contrato,
                            estado_contrato=estado_contrato,
                            garantia_uf=garantia_uf,
                            comentario=comentario,
                            contrib_clp=contrib_clp,
                            ggcc_clp=ggcc_clp,
                            seguro_uf=seguro_uf
                        )
                        st.session_state["mensaje_exito"] = f"✅ ¡Guardado Exitoso! Modificación guardada para ID {id_sel}. Registros previos cerrados al {fecha_cerrada}."
                        st.rerun()

    with tab_admin:
        st.subheader("⚙️ Gestión de Usuarios & Trazabilidad")
        
        # TABLA DE USUARIOS EXISTENTES
        st.markdown("### 👥 Usuarios Registrados en el Sistema")
        conn_u = sqlite3.connect(DB_PATH)
        df_usr_all = pd.read_sql_query("SELECT id, username, nombre, email, rol, activo FROM usuarios ORDER BY id ASC", conn_u)
        conn_u.close()
        
        df_usr_display = df_usr_all.copy()
        df_usr_display["activo"] = df_usr_display["activo"].apply(lambda x: "✅ Activo" if x == 1 else "🚫 Inactivo")
        st.dataframe(df_usr_display, use_container_width=True, hide_index=True)
        
        st.markdown("---")
        
        # 1. CREAR NUEVO USUARIO
        col_admin1, col_admin2 = st.columns(2)
        
        with col_admin1:
            with st.expander("➕ Crear Nuevo Usuario", expanded=False):
                with st.form("form_nuevo_usuario"):
                    new_user = st.text_input("Nombre de Usuario (Login):")
                    new_name = st.text_input("Nombre Completo:")
                    new_email = st.text_input("Correo Electrónico:")
                    new_pass = st.text_input("Contraseña:", type="password")
                    new_role = st.selectbox("Rol Asignado:", ["ejecutivo", "admin"])
                    
                    btn_crear_usr = st.form_submit_button("👤 Registrar Usuario")
                    
                    if btn_crear_usr:
                        if new_user and new_pass and new_email:
                            conn = sqlite3.connect(DB_PATH)
                            cursor = conn.cursor()
                            try:
                                cursor.execute("""
                                    INSERT INTO usuarios (username, nombre, email, password_hash, rol, activo)
                                    VALUES (?, ?, ?, ?, ?, 1)
                                """, (new_user.strip(), new_name.strip(), new_email.strip(), hash_pw(new_pass), new_role))
                                conn.commit()
                                st.success(f"✅ Usuario **{new_user}** registrado con éxito.")
                                registrar_edicion(username, None, "USUARIOS", f"Usuario creado: {new_user} ({new_role})")
                                st.rerun()
                            except sqlite3.IntegrityError:
                                st.error("❌ El nombre de usuario ya existe.")
                            finally:
                                conn.close()
                        else:
                            st.warning("⚠️ Rellene todos los campos.")

        # 2. RESTABLECER CONTRASEÑA
        with col_admin2:
            with st.expander("🔑 Restablecer Contraseña", expanded=False):
                target_usr = st.selectbox("Seleccionar Usuario:", options=df_usr_all["username"].tolist(), key="sel_usr_pwd")
                change_pass = st.text_input("Nueva Contraseña:", type="password", key="new_pwd_input")
                
                if st.button("💾 Actualizar Clave"):
                    if change_pass.strip():
                        conn_up = sqlite3.connect(DB_PATH)
                        cursor_up = conn_up.cursor()
                        cursor_up.execute("UPDATE usuarios SET password_hash = ? WHERE username = ?", (hash_pw(change_pass.strip()), target_usr))
                        conn_up.commit()
                        conn_up.close()
                        st.success(f"✅ Contraseña de **{target_usr}** actualizada.")
                        registrar_edicion(username, None, "USUARIOS", f"Cambio de clave para: {target_usr}")
                    else:
                        st.warning("⚠️ Ingrese una contraseña válida.")

        st.markdown("---")
        
        # 3. ACTIVAR / DESACTIVAR / ELIMINAR USUARIO
        with st.expander("🗑️ Desactivar / Eliminar Usuario", expanded=False):
            col_d1, col_d2, col_d3 = st.columns([2, 1, 1])
            with col_d1:
                user_to_mod = st.selectbox("Seleccionar Usuario a Gestionar:", options=[u for u in df_usr_all["username"].tolist() if u != username])
            
            if user_to_mod:
                estado_actual = df_usr_all[df_usr_all["username"] == user_to_mod]["activo"].values[0]
                
                with col_d2:
                    st.markdown("<div style='margin-top: 28px;'></div>", unsafe_allow_html=True)
                    btn_label = "🚫 Desactivar Acceso" if estado_actual == 1 else "✅ Reactivar Acceso"
                    if st.button(btn_label):
                        nuevo_est = 0 if estado_actual == 1 else 1
                        conn_est = sqlite3.connect(DB_PATH)
                        cursor_est = conn_est.cursor()
                        cursor_est.execute("UPDATE usuarios SET activo = ? WHERE username = ?", (nuevo_est, user_to_mod))
                        conn_est.commit()
                        conn_est.close()
                        st.success(f"✅ Estado de **{user_to_mod}** actualizado.")
                        registrar_edicion(username, None, "USUARIOS", f"Usuario {user_to_mod} cambiado a activo={nuevo_est}")
                        st.rerun()

                with col_d3:
                    st.markdown("<div style='margin-top: 28px;'></div>", unsafe_allow_html=True)
                    if st.button("🗑️ Eliminar Definitivamente", type="secondary"):
                        conn_del = sqlite3.connect(DB_PATH)
                        cursor_del = conn_del.cursor()
                        cursor_del.execute("DELETE FROM usuarios WHERE username = ?", (user_to_mod,))
                        conn_del.commit()
                        conn_del.close()
                        st.success(f"✅ Usuario **{user_to_mod}** eliminado permanentemente.")
                        registrar_edicion(username, None, "USUARIOS", f"Usuario eliminado: {user_to_mod}")
                        st.rerun()

        st.markdown("---")
        
        # 4. LOGS Y AUDITORÍA
        st.markdown("### 📋 Registros de Auditoría y Control")
        col_log1, col_log2 = st.columns(2)
        
        conn = sqlite3.connect(DB_PATH)
        df_acc = pd.read_sql_query("SELECT id, username, email, fecha_hora, evento FROM auditoria_accesos ORDER BY id DESC LIMIT 50", conn)
        df_edi = pd.read_sql_query("SELECT id, username, propiedad_id, modulo, descripcion, fecha_hora FROM auditoria_ediciones ORDER BY id DESC LIMIT 50", conn)
        conn.close()

        with col_log1:
            st.markdown("#### 🔑 Log de Accesos (Últimos 50)")
            st.dataframe(df_acc, use_container_width=True, hide_index=True)

        with col_log2:
            st.markdown("#### ✏️ Log de Ediciones (Trazabilidad)")
            st.dataframe(df_edi, use_container_width=True, hide_index=True)