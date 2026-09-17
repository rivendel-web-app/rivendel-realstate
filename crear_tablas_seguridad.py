import sqlite3
import streamlit_authenticator as stauth

DB_PATH = 'modelo_definitivo.db'

def hash_pw(password: str) -> str:
    """Genera hash bcrypt compatible con las últimas versiones de streamlit-authenticator"""
    try:
        # Intento con API moderna (v0.3.x+)
        return stauth.Hasher.hash_passwords([password])[0]
    except Exception:
        try:
            # Intento con API de métodos estáticos
            return stauth.Hasher([password]).generate()[0]
        except Exception:
            # Fallback a bcrypt directo
            import bcrypt
            return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def inicializar_tablas_seguridad():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 1. Tabla de Usuarios
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS usuarios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        nombre TEXT NOT NULL,
        email TEXT NOT NULL,
        password_hash TEXT NOT NULL,
        rol TEXT NOT NULL,
        activo INTEGER DEFAULT 1
    );
    """)

    # 2. Auditoría de Conexiones (Logins)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS auditoria_accesos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL,
        email TEXT NOT NULL,
        fecha_hora DATETIME DEFAULT CURRENT_TIMESTAMP,
        evento TEXT NOT NULL
    );
    """)

    # 3. Auditoría de Ediciones y Cambios de Contrato
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS auditoria_ediciones (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL,
        propiedad_id INTEGER,
        modulo TEXT NOT NULL,
        descripcion TEXT NOT NULL,
        fecha_hora DATETIME DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # Hashear claves iniciales de forma segura
    hash_admin = hash_pw('admin123')
    hash_ejecutivo = hash_pw('ejecuto123')

    # Insertar usuarios semilla por defecto si no existen
    cursor.execute("""
    INSERT OR IGNORE INTO usuarios (username, nombre, email, password_hash, rol, activo)
    VALUES 
        ('admin', 'Ricardo Narvarte', 'rnarvarte@rivendel.cl', ?, 'admin', 1),
        ('ejecutivo', 'Usuario Ejecutivo', 'contacto@rivendel.cl', ?, 'ejecutivo', 1)
    """, (hash_admin, hash_ejecutivo))

    conn.commit()
    conn.close()
    print("✅ Tablas de seguridad y auditoría creadas exitosamente.")

if __name__ == '__main__':
    inicializar_tablas_seguridad()