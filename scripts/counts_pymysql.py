import pymysql
conn = pymysql.connect(host='127.0.0.1', user='root', password='', db='del_campo_al_algoritomo', port=3306, charset='utf8mb4')
cur = conn.cursor()
for t in ('consulta_queries','consulta_summaries','consulta_precios'):
    try:
        cur.execute(f"SELECT COUNT(*) FROM {t}")
        print(t, cur.fetchone()[0])
    except Exception as e:
        print(t, 'ERROR ->', e)
cur.close()
conn.close()
