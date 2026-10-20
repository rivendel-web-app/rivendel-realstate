import sqlite3
import pandas as pd
import streamlit as st
from google import genai

# Configuración de la página en Streamlit
st.set_page_config(page_title="Asistente Beco IA", page_icon="🤖", layout="wide")

st.title("🤖 Asistente Conversacional Beco Real Estate")
st.write("Haz preguntas en lenguaje natural sobre el portafolio, ocupación o cánones de arriendo.")

# 1. Inicializar cliente Gemini leyendo la clave de secrets
client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])

# 2. Función para obtener la estructura (esquema) de modelo_definitivo.db
def obtener_esquema_db():
    conn = sqlite3.connect("modelo_definitivo.db")
    cursor = conn.cursor()
    cursor.execute("SELECT sql FROM sqlite_master WHERE type='table';")
    tablas = cursor.fetchall()
    conn.close()
    esquema = "\n".join([t[0] for t in tablas if t[0] is not None])
    return esquema

# 3. Función para ejecutar la consulta SQL de manera segura (solo lectura)
def ejecutar_consulta_sql(sql_query):
    conn = sqlite3.connect("modelo_definitivo.db")
    try:
        # Bloqueo de seguridad básico: solo permitir SELECT
        query_clean = sql_query.strip().upper()
        if not query_clean.startswith("SELECT"):
            return None, "Por seguridad, solo se permiten consultas de lectura (SELECT)."
        
        df = pd.read_sql_query(sql_query, conn)
        conn.close()
        return df, None
    except Exception as e:
        conn.close()
        return None, str(e)

# 4. Historial de Chat
if "messages" not in st.session_state:
    st.session_state.messages = []

# Mostrar mensajes anteriores
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# 5. Entrada del usuario
if prompt := st.chat_input("Ej: ¿Cuántas oficinas tenemos y cuál es su tasa de ocupación?"):
    # Mostrar mensaje del usuario
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Procesar respuesta con la IA
    with st.chat_message("assistant"):
        with st.spinner("Consultando la base de datos..."):
            esquema = obtener_esquema_db()
            
            # Prompt de instrucción para el LLM
            system_prompt = f"""
            Eres un experto analista SQL para un sistema inmobiliario (Beco Real Estate).
            Dada la siguiente estructura de la base de datos SQLite:
            
            {esquema}
            
            Transforma la siguiente pregunta del usuario en una consulta SQL SQLite estricta y válida.
            REGLAS IMPORTANTES:
            1. Devuelve ÚNICAMENTE el código SQL sin explicaciones, sin formato markdown (sin ```sql ... ```).
            2. Usa solo sentencias SELECT.
            3. Si la pregunta no se refiere a los datos de la base, responde la pregunta de forma amigable sin SQL.
            """

            full_prompt = f"{system_prompt}\n\nPregunta del usuario: {prompt}"

            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=full_prompt
            )
            
            sql_generada = response.text.strip().replace("```sql", "").replace("```", "").strip()

            # Intentar ejecutar la consulta en la BBDD
            if sql_generada.upper().startswith("SELECT"):
                df_resultado, error = ejecutar_consulta_sql(sql_generada)
                
                if error:
                    st.error(f"Error al ejecutar SQL: {error}")
                    st.code(sql_generada, language="sql")
                elif df_resultado is not None:
                    st.write("📊 **Resultado:**")
                    st.dataframe(df_resultado, use_container_width=True)
                    
                    with st.expander("Ver consulta SQL generada"):
                        st.code(sql_generada, language="sql")
                    
                    st.session_state.messages.append({
                        "role": "assistant", 
                        "content": f"He ejecutado la consulta para responder tu pregunta. Se encontraron {len(df_resultado)} registros."
                    })
            else:
                st.write(response.text)
                st.session_state.messages.append({"role": "assistant", "content": response.text})
