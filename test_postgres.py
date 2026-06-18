import psycopg2

conn = psycopg2.connect(
    host="localhost",
    database="search_agent",
    user="postgres",
    password="123"
)

print("Connected Successfully!")

conn.close()