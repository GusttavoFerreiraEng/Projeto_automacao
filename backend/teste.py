import psycopg2

try:
    print("Tentando conectar...")
    conn = psycopg2.connect(
        dbname="automacao_db",
        user="admin",
        password="adminpassword",
        host="127.0.0.1",
        port="5432",
        client_encoding='utf8' # Forçamos UTF8 aqui
    )
    print("CONEXÃO BEM SUCEDIDA!")
    conn.close()
except Exception as e:
    # Se der erro, vamos capturar os bytes crus para ver o que tem dentro
    print("ERRO DE CONEXÃO:")
    print(repr(e))