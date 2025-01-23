from flask import Flask, render_template, request, flash, url_for, redirect
from werkzeug.exceptions import HTTPException
import psycopg2

app = Flask(__name__)
app.secret_key = 'key'

# Подключение к базе данных
DB_CONFIG = {
    'dbname': 'dbname',
    'user': 'user',
    'password': 'password',
    'host': '0.0.0.0',
    'port': 5432
}

def get_data_from_db(query, params=None):

    # Выполняет запрос к базе данных и возвращает результат
    try:
        connection = psycopg2.connect(**DB_CONFIG)
        cursor = connection.cursor()
        cursor.execute(query, params or {})
        rows = cursor.fetchall()
        cursor.close()
        connection.close()
        ok_message = "Подключен к базе данных"
        print(ok_message) # Для дебагинка базы данных
        return rows

    except Exception as e:
        error_message = f"Ошибка подключения к базе данных: {e}"
        print(error_message) # Для дебагинка базы данных
        return None, error_message

@app.route('/', methods=['GET', 'POST'])
def main_menu():

    filters = {
        "start_date": request.form.get('start_date'),
        "end_date": request.form.get('end_date'),
        "type": request.form.get('type'),
        "id": request.form.get('id'),
    }

    # Загрузка истории отчетов
    query = """ SELECT r.id, rd.id, r.type, r.date FROM report r JOIN report_data rd ON r.id = rd.report_id"""

    conditions = []
    params = {}

    # Добавление фильтров
    if filters["start_date"]:
        conditions.append("date >= %(start_date)s")
        params["start_date"] = filters["start_date"]
    if filters["end_date"]:
        conditions.append("date <= %(end_date)s")
        params["end_date"] = filters["end_date"]
    if filters["type"]:
        conditions.append("type = %(type)s")
        params["type"] = filters["type"]


    # Добавление условий в запрос
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY date DESC"
    history = get_data_from_db(query, params)

    return render_template('main_menu.html', filters=filters, history=history)

@app.errorhandler(Exception)
def handle_exception(e):

    # Страница с ошибкой
    if isinstance(e, HTTPException):
        return e
    return render_template("err.html", e=e), 500

@app.route('/report/<report_name>', methods=['GET', 'POST'])
def report(report_name):

    # Страница отчёта
    filters = {
        "start_date_report": request.form.get('start_date_report'),
        "end_date_report": request.form.get('end_date_report'),
        "id": request.form.get('id'),
        "report_id": request.form.get('report_id'),
    }

    # SQL-запросы для отчётов
    queries = {"all_data": "SELECT rd.id, rd.report_id, rd.temp, rd.pres, rd.volume, rd.volume20, r.date FROM report_data rd JOIN report r ON rd.report_id = r.id "}

    # Получение базового SQL-запроса
    base_query = queries.get(report_name, queries["all_data"])
    params = {}

    # Добавление фильтров
    conditions = []
    if filters["start_date_report"]:
        conditions.append("date >= %(start_date_report)s")
        params["start_date_report"] = filters["start_date_report"]
    if filters["end_date_report"]:
         conditions.append("date <= %(end_date_report)s")
         params["end_date_report"] = filters["end_date_report"]
    if filters["id"]:
        conditions.append("id = %(id)s")
        params["id"] = filters["id"]
    if filters["report_id"]:
        conditions.append("report_id = %(report_id)s")
        params["report_id"] = filters["report_id"]

    # Соединение базового запроса и условий
    if conditions:
        if "WHERE" in base_query.upper():
             query = f"{base_query} AND {' AND '.join(conditions)}"
        else:
            query = f"{base_query} WHERE {' AND '.join(conditions)}"
    else:
        query = base_query

    @app.route('/report/shift_report<int:report_id>.html', methods=['GET'])
    def shift_report(report_id):
        # SQL-запрос для получения данных отчёта
        query = """SELECT r.id, r.type, r.date
        FROM report r
        JOIN report_data rd
        ON r.id=rd.report_id"""
        print(f"Executing query: {query} with report_id={report_id}")  # Отладка

        report_data, error = get_data_from_db(query, (report_id,))
        if error:
            print(f"Error while fetching data: {error}")  # Логирование ошибки
            flash(f"Ошибка загрузки сменного отчёта с ID {report_id}: {error}", 'error')
            return redirect(url_for('main_menu'))

        if not report_data:
            print(f"No data found for report_id={report_id}")  # Логирование пустых данных
            flash(f"Данные для отчёта с ID {report_id} отсутствуют.", 'error')
            return redirect(url_for('main_menu'))

        # Передача данных в шаблон
        print(f"Data fetched successfully: {report_data}")  # Отладка данных
        return render_template('shift_report.html', report=report_data[0], report_id=report_id)

    # Получение данных
    data, error = get_data_from_db(query, params)
    if error: # (можно убрать после выпуска)
        flash(error, 'error')  # Передача сообщения об ошибке
        return redirect(url_for('err'))  # Возвращаемся в основное меню
    return render_template(f'report_{report_name}.html', data=data, filters=filters)

if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True, port=5000)