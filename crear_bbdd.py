import sqlite3
import pandas as pd
import os
import warnings
warnings.filterwarnings('ignore')

excel_path = 'Planilla Propiedades IA.xlsx'
db_path = 'modelo_definitivo.db'

if not os.path.exists(excel_path):
    print(f"❌ ERROR: No se encontró '{excel_path}'")
    exit()

df_raw = pd.read_excel(excel_path, sheet_name='Activos Detalles')
df_data = df_raw.iloc[1:].copy()

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

ddl = """
DROP TABLE IF EXISTS canones_arriendo;
DROP TABLE IF EXISTS contratos_arriendo;
DROP TABLE IF EXISTS arrendatarios;
DROP TABLE IF EXISTS gastos_propiedad;
DROP TABLE IF EXISTS compras_financiamiento;
DROP TABLE IF EXISTS propiedades;

CREATE TABLE propiedades (
    id INTEGER PRIMARY KEY, dueno TEXT NOT NULL, edificio TEXT, direccion TEXT,
    comuna TEXT, tipo_original TEXT, sigla_original TEXT, num_propiedad TEXT,
    piso TEXT, rol_avaluo TEXT, m2 REAL
);

CREATE TABLE compras_financiamiento (
    id INTEGER PRIMARY KEY AUTOINCREMENT, propiedad_id INTEGER UNIQUE,
    precio_total_uf REAL, banco_acreedor TEXT,
    FOREIGN KEY(propiedad_id) REFERENCES propiedades(id)
);

CREATE TABLE gastos_propiedad (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    propiedad_id INTEGER,
    seguro_anual_uf REAL,
    contribuciones_anual_clp REAL,
    gasto_comun_anual_clp REAL,
    fecha_inicio TEXT,
    fecha_fin TEXT,
    FOREIGN KEY(propiedad_id) REFERENCES propiedades(id)
);

CREATE TABLE arrendatarios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre_arrendatario TEXT UNIQUE NOT NULL,
    tipo_arrendatario TEXT,
    representante_legal TEXT
);

CREATE TABLE contratos_arriendo (
    id INTEGER PRIMARY KEY AUTOINCREMENT, propiedad_id INTEGER, arrendatario_id INTEGER,
    fecha_arriendo TEXT, fecha_vencimiento_original TEXT, fecha_fin TEXT,
    impuesto_estado TEXT DEFAULT 'Exento', monto_garantia_uf REAL DEFAULT 0.0,
    contrato_ok_estado TEXT,
    FOREIGN KEY(propiedad_id) REFERENCES propiedades(id),
    FOREIGN KEY(arrendatario_id) REFERENCES arrendatarios(id)
);

CREATE TABLE canones_arriendo (
    id INTEGER PRIMARY KEY AUTOINCREMENT, contrato_id INTEGER, arriendo_neto_uf REAL,
    monto_iva_uf REAL, valor_arriendo_total_uf REAL, valor_arriendo_total_clp REAL, comentarios TEXT,
    FOREIGN KEY(contrato_id) REFERENCES contratos_arriendo(id)
);
"""
cursor.executescript(ddl)

def safe_float(val):
    try: return float(val) if pd.notna(val) else 0.0
    except: return 0.0

def safe_str(val): return str(val) if pd.notna(val) else None
def safe_date(val): return str(val)[:10] if pd.notna(val) else None

arrendatario_map = {}

for idx, row in df_data.iterrows():
    if pd.isna(row.iloc[0]) or pd.isna(row.iloc[1]): continue
    prop_id = int(row.iloc[0])
    
    cursor.execute('INSERT INTO propiedades VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)', (
        prop_id, safe_str(row.iloc[1]), safe_str(row.iloc[2]), safe_str(row.iloc[3]), safe_str(row.iloc[4]),
        safe_str(row.iloc[6]), safe_str(row.iloc[7]), safe_str(row.iloc[13]), safe_str(row.iloc[16]), safe_str(row.iloc[17]), safe_float(row.iloc[18])
    ))
    cursor.execute('INSERT INTO compras_financiamiento VALUES (NULL, ?, ?, ?)', (
        prop_id, safe_float(row.iloc[22]), safe_str(row.iloc[25])
    ))
    
    # Ingesta de gastos inicial con fecha desde 2020
    cursor.execute('INSERT INTO gastos_propiedad VALUES (NULL, ?, ?, ?, ?, "2020-01-01", NULL)', (
        prop_id, safe_float(row.iloc[39]), safe_float(row.iloc[40]), safe_float(row.iloc[53])
    ))

    arr_nom = safe_str(row.iloc[41]).strip() if pd.notna(row.iloc[41]) else "Sin Arrendatario"
    tipo_arr = safe_str(row.iloc[42]).strip() if len(row) > 42 and pd.notna(row.iloc[42]) else "Empresa"
    rep_legal = safe_str(row.iloc[46]).strip() if len(row) > 46 and pd.notna(row.iloc[46]) else "-"
    
    if arr_nom not in arrendatario_map:
        cursor.execute("INSERT OR IGNORE INTO arrendatarios (nombre_arrendatario, tipo_arrendatario, representante_legal) VALUES (?, ?, ?)", (arr_nom, tipo_arr, rep_legal))
        cursor.execute("SELECT id FROM arrendatarios WHERE nombre_arrendatario = ?", (arr_nom,))
        arrendatario_map[arr_nom] = cursor.fetchone()[0]

    arr_id = arrendatario_map[arr_nom]
    neto_uf = safe_float(row.iloc[48])
    iva_uf = safe_float(row.iloc[49])
    total_uf = safe_float(row.iloc[50])
    
    trata_imp = safe_str(row.iloc[52]) if len(row) > 52 and pd.notna(row.iloc[52]) else "Exenta"
    impuesto = "Afecto" if "AFEC" in trata_imp.upper() or iva_uf > 0 else "Exento"

    cursor.execute('INSERT INTO contratos_arriendo VALUES (NULL, ?, ?, ?, ?, NULL, ?, 0.0, ?)', (
        prop_id, arr_id, safe_date(row.iloc[54]) or '2020-01-01', safe_date(row.iloc[55]), impuesto, safe_str(row.iloc[61])
    ))
    c_id = cursor.lastrowid
    cursor.execute('INSERT INTO canones_arriendo VALUES (NULL, ?, ?, ?, ?, ?, ?)', (
        c_id, neto_uf, iva_uf, total_uf, safe_float(row.iloc[51]), safe_str(row.iloc[64])
    ))

# Registros Demo
oficinas_demo = [
    (11, 'Agrícola Beco Ltda.', 'Edificio 1', 'Av Presidente Riesco', 'Las Condes', 'Oficina', 'OF', 'OF 101', 'Piso 10', '00751-00101', 85.50, 4200.0, 'Banco Chile', 28.50, 1162800.0, 'Creación de Valor Ltda.', 'Empresa', 'Marcela Palma'),
    (12, 'Agrícola Beco Ltda.', 'Edificio 1', 'Av Presidente Riesco', 'Las Condes', 'Oficina', 'OF', 'OF 102', 'Piso 10', '00751-00102', 110.00, 5400.0, 'Banco Chile', 38.00, 1550400.0, 'Viña Rick SpA', 'Empresa', 'Leo Veas')
]

for of in oficinas_demo:
    cursor.execute("INSERT OR REPLACE INTO propiedades VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (of[0], of[1], of[2], of[3], of[4], of[5], of[6], of[7], of[8], of[9], of[10]))
    cursor.execute("INSERT OR REPLACE INTO compras_financiamiento VALUES (NULL, ?, ?, ?)", (of[0], of[11], of[12]))
    cursor.execute("INSERT OR REPLACE INTO gastos_propiedad VALUES (NULL, ?, 0, 0, 0, '2020-01-01', NULL)", (of[0],))
    
    arr_nom, tipo_arr, rep_legal = of[15], of[16], of[17]
    if arr_nom not in arrendatario_map:
        cursor.execute("INSERT OR IGNORE INTO arrendatarios (nombre_arrendatario, tipo_arrendatario, representante_legal) VALUES (?, ?, ?)", (arr_nom, tipo_arr, rep_legal))
        cursor.execute("SELECT id FROM arrendatarios WHERE nombre_arrendatario = ?", (arr_nom,))
        arrendatario_map[arr_nom] = cursor.fetchone()[0]
    
    arr_id = arrendatario_map[arr_nom]
    cursor.execute("INSERT INTO contratos_arriendo VALUES (NULL, ?, ?, '2020-01-01', '2028-12-31', NULL, 'Exento', 0.0, 'OK')", (of[0], arr_id))
    c_id = cursor.lastrowid
    cursor.execute("INSERT INTO canones_arriendo VALUES (NULL, ?, ?, 0.0, ?, ?, 'Oficina Demo')", (c_id, of[13], of[13], of[14]))

conn.commit()
print("✅ Trazabilidad de Gastos agregada a la BBDD.")
conn.close()