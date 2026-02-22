from core.manager import DBManager
db_m = DBManager()

for db_id in [2, 3, 4]:
    try:
        prov = db_m.get_provider_instance(db_id)
        res = prov.check_connection()
        print(f"DB {db_id} connection test: {res}")
    except Exception as e:
        print(f"DB {db_id} provider init failed: {e}")
