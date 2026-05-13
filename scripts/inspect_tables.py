import pymysql

conn = pymysql.connect(host='127.0.0.1', user='root', password='', db='del_campo_al_algoritomo', port=3306, charset='utf8mb4')
cur = conn.cursor()
for t in ['consultas', 'blog_user', 'consulta_queries']:
    try:
        cur.execute(f"SHOW CREATE TABLE {t}")
        row = cur.fetchone()
        print('\n----', t, '----\n')
        print(row[1])
    except Exception as e:
        print('ERROR mostrando', t, e)
cur.close()
conn.close()
