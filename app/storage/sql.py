
def to_sql(index, time, min, max, query=""):
    sql = """SELECT * FROM "{}" WHERE {} BETWEEN '{}' AND '{}'""".format(index, time, min.isoformat(),
                                                                                max.isoformat())

    if query:
        query = query.replace('"', "'")
        sql += " AND {}".format(query)

    query = {
        "query": sql
    }
    print(query)
    return query
