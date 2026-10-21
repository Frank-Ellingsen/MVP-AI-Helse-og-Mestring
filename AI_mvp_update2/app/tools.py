import sqlite3
import pandas as pd
from typing import Dict, Any
from app.visual_sandbox import get_time_visual_recommendation

def query_erp_transactions_secure(db_path: str, user_role: str, user_ansvar: str, query_sql: str) -> pd.DataFrame:
    conn = sqlite3.connect(db_path)
    # RBAC Enforcement
    if user_role == "enhetsleder":
        if "WHERE" in query_sql.upper():
            query_sql += f" AND ansvar_id = '{user_ansvar}'"
        else:
            query_sql += f" WHERE ansvar_id = '{user_ansvar}'"
    df = pd.read_sql_query(query_sql, conn)
    conn.close()
    return df

def log_to_audit(db_path: str, user_id: str, role: str, category: str, query: str, summary: str):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO audit_log (bruker_id, rolle, handling_kategori, sporring_tekst, ai_respons_sammendrag)
        VALUES (?, ?, ?, ?, ?)
    """, (user_id, role, category, query, summary))
    conn.commit()
    conn.close()

def rag_search_documents(db_path: str, query: str, sektor: str = "Helse og mestring", ansvar_id: str = None) -> list:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    sql = """
        SELECT title, document_type, content 
        FROM rag_documents 
        WHERE (sektor = ? OR sektor = 'Konsern' OR sektor IS NULL)
    """
    params = [sektor]
    if ansvar_id and ansvar_id != '*':
        sql += " AND (ansvar_id = ? OR ansvar_id = '*' OR ansvar_id IS NULL)"
        params.append(ansvar_id)
    
    cursor.execute(sql, params)
    rows = cursor.fetchall()
    conn.close()
    
    # Filter rows based on query relevance
    matched = []
    q_words = [w.lower() for w in query.split() if len(w) > 3]
    for row in rows:
        title, doc_type, content = row
        if any(w in content.lower() for w in q_words) or not q_words:
            matched.append({'title': title, 'doc_type': doc_type, 'content': content[:400]})
    return matched[:5]

def recommend_visual_for_chat_response(query: str, data_summary: Dict[str, Any]) -> Dict[str, Any]:
    """
    AI Chat Engine Tool: Anbefaler og konfigurerer Time-Visuals (Time-Visuals.pdf 60 Suite)
    eller FT Visual Vocabulary for å forklare dataforhold visuelt i chaten.
    """
    rec = get_time_visual_recommendation(query, data_summary)
    return {
        'visual_recommendation': rec,
        'chat_prompt_addon': f"

📊 **Visuelt forslag ({rec['chart_type']}):**
*Anbefalt diagram:* {rec['chart_type']} (Time-Visuals #{rec['time_visual_id']})
*Begrunnelse:* {rec['reasoning']}"
    }
