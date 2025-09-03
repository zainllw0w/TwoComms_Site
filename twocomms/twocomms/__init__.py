import os

# Использовать PyMySQL только если явно указано в переменной окружения
if os.environ.get("MYSQL_USE_PYMYSQL") == "1":
    try:
        import pymysql
        pymysql.install_as_MySQLdb()
    except Exception:
        pass

