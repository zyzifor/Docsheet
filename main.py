from flask import Flask, render_template, request, flash, url_for, redirect
from werkzeug.exceptions import HTTPException
import psycopg2
from datetime import datetime, timedelta
import modulPDF
import os
import json

app = Flask(__name__)
app.secret_key = 'key'

# Загружаем настройка из JSON файла
with open("config.json", "r") as file:
    config = json.load(file)

# Подключение к базе данных и серверу
DB_CONFIG = config["DB_CONFIG"]
SERVER_CONFIG = config["SERVER_CONFIG"]

def get_data_from_db(query, params=None):

    # Выполняет запрос к базе данных и возвращает результат
    try:
        connection = psycopg2.connect(**DB_CONFIG)
        cursor = connection.cursor()
        cursor.execute(query, params or {})
        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        cursor.close()
        connection.close()
        ok_message = "Подключен к базе данных"
        print(ok_message) # Для дебагинка базы данных
        return rows, None
    except Exception as e:
        error_message = f"Ошибка подключения к базе данных: {e}"
        print(error_message) # Для дебагинка базы данных
        return None, error_message

@app.route('/', methods=['GET', 'POST'])
def main_menu():
    filters = {
        "start_date": request.form.get('start_date'),
        "end_date": request.form.get('end_date'),
        "post": request.form.get('post'),
        "numReport": request.form.get('numReport'),
    }

    # Преобразование дат
    try:
        if filters["start_date"]:
            filters["start_date"] = datetime.strptime(filters["start_date"], "%Y-%m-%d").date()
        if filters["end_date"]:
            filters["end_date"] = datetime.strptime(filters["end_date"], "%Y-%m-%d").date()
    except ValueError:
        flash("Некорректный формат даты. Используйте формат YYYY-MM-DD.", 'error')
        filters["start_date"] = None
        filters["end_date"] = None

    # Загрузка истории отчетов
    query = """ SELECT sh."numReport", (TO_TIMESTAMP(sh."dDate") AT TIME ZONE 'UTC'), sh.operator, sh."numSm", dir.txt AS direction, 
                       sh.post, sh.product, sh.dens, sh.temp, sh.mass, sh.volume, 
                       sh."massAccum", sh."volumeAccum"
                FROM shipments sh
                JOIN direction dir ON sh.directing = dir.id
            """

    conditions = []
    params = {}

    # Добавление фильтров
    if filters["start_date"]:
        conditions.append('"dDate" >= %(start_date)s')
        params["start_date"] = filters["start_date"]
    if filters["end_date"]:
        conditions.append('"dDate" <= %(end_date)s')
        params["end_date"] = filters["end_date"]
    if filters["post"]:
        conditions.append('sh.post = %(post)s')
        params["post"] = filters["post"]
    if filters["numReport"]:
        conditions.append('sh."numReport" = %(numReport)s')
        params["numReport"] = filters["numReport"]

    # Добавление условий в запрос
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY sh.\"dDate\" DESC"

    # Выполнение запроса
    history, error = get_data_from_db(query, params)
    if error:
        flash(f"Ошибка загрузки истории отчётов: {error}", 'error')
        history = None

    return render_template('main_menu.html', filters=filters, history=history, now=datetime.now, timedelta=timedelta)


@app.route('/report/<report_name>', methods=['GET', 'POST'])
def report(report_name):

    # Страница отчёта
    filters = {
        "start_date": request.form.get('start_date'),
        "end_date": request.form.get('end_date'),
        "numReport": request.form.get('numReport'),
        "post": request.form.get('post'),
    }

    # SQL-запросы для отчётов
    queries = {
        "all_data": """SELECT sh."numReport", (TO_TIMESTAMP(sh."dDate") AT TIME ZONE 'UTC'), sh.operator, sh."numSm", dir.txt AS direction, 
                       sh.post, sh.product, sh.dens, sh.temp, sh.mass, sh.volume, 
                       sh."massAccum", sh."volumeAccum"
                FROM shipments sh
                JOIN direction dir ON sh.directing = dir.id
        """
    }

    # Получение базового SQL-запроса
    base_query = queries.get(report_name, queries["all_data"])

    # Добавление фильтров
    params = {}
    conditions = []

    if filters["start_date"]:
        conditions.append("date >= %(start_date)s")
        params["start_date"] = filters["start_date"]
    if filters["end_date"]:
        conditions.append("date <= %(end_date)s")
        params["end_date"] = filters["end_date"]
    if filters["post"]:
        conditions.append("post = %(post)s")
        params["post"] = filters["post"]

    # Соединение базового запроса и условий
    if conditions:
        if "WHERE" in base_query.upper():
            query = f"{base_query} AND {' AND '.join(conditions)}"
        else:
            query = f"{base_query} WHERE {' AND '.join(conditions)}"
    else:
        query = base_query

    data, error = get_data_from_db(query, params)
    if error:
        flash(f"Ошибка выполнения запроса: {error}", 'error')
        return redirect(url_for('main_menu'))

    # Генерация HTML-файла для PDF
    temp_html_file = "temp_report.html"
    output_pdf = os.path.join(r"C:\dll" if os.name == "nt" else "/opt/Doc",
                              f"{report_name}_{datetime.now().strftime('%Y-%m-%d')}.pdf")

    # Генерируем временный HTML-файл
    report_html = render_template(f'report_{report_name}.html', data=data, filters=filters, now=datetime.now(), timedelta=timedelta)
    with open(temp_html_file, 'w', encoding='utf-8') as f:
        f.write(report_html)

    # Генерация PDF
    modulPDF.convert_html_to_pdf(temp_html_file, output_pdf)

    # Открытие PDF
    modulPDF.open_pdf(output_pdf)

    # Удаляем временный HTML-файл
    modulPDF.delete_temp_html(temp_html_file)

    # Возвращаем страницу с отчетом
    return render_template(f'report_{report_name}.html', data=data, filters=filters, now=datetime.now(), timedelta=timedelta)

@app.route('/report/shift_report<int:numReport>', methods=['GET'])
def shift_report(numReport):
        # SQL-запрос для получения данных отчёта
        query = """SELECT sh."numReport", (TO_TIMESTAMP(sh."dDate") AT TIME ZONE 'UTC'), sh.operator, sh."numSm", dir.txt AS direction, 
                       sh.post, sh.product, sh.dens, sh.temp, sh.mass, sh.volume, 
                       sh."massAccum", sh."volumeAccum"
                FROM shipments sh
                JOIN direction dir ON sh.directing = dir.id
        WHERE sh."numReport" = %s"""
        print(f"Запрос выполняется: {query} с помощью numReport={numReport}")  # Отладка

        report_data, error = get_data_from_db(query, (numReport,))
        if error or not report_data:
            flash(f"Ошибка загрузки сменного отчёта с ID {numReport}: {error}", 'error')
            return redirect(url_for('main_menu'))

        return render_template('shift_report.html', report=report_data[0], numReport=numReport)

@app.route('/report/ttn<int:report_id>', methods=['GET'])
def ttn(report_id):
        # SQL-запрос для получения данных отчёта
        query = """SELECT sh."numReport", (TO_TIMESTAMP(sh."dDate") AT TIME ZONE 'UTC'), sh.operator, sh."numSm", dir.txt AS direction, 
                sh.post, sh.product, sh.dens, sh.temp, sh.mass, sh.volume, 
                sh."massAccum", sh."volumeAccum"
                FROM shipments sh
                JOIN direction dir ON sh.directing = dir.id
        WHERE sh."numReport" = %s"""
        print(f"Запрос выполняется: {query} с помощью report_id={report_id}")  # Отладка

        report_data, error = get_data_from_db(query, (report_id,))
        if error or not report_data:
            flash(f"Ошибка загрузки сменного отчёта с ID {report_id}: {error}", 'error')
            return redirect(url_for('main_menu'))

        return render_template('ttn.html', report=report_data[0], report_id=report_id)


@app.route('/save_pdf/<int:report_id>', methods=['POST'])
def save_pdf(report_id):
    query = """SELECT sh."numReport", (TO_TIMESTAMP(sh."dDate") AT TIME ZONE 'UTC'), sh.operator, sh."numSm", dir.txt AS direction, 
                sh.post, sh.product, sh.dens, sh.temp, sh.mass, sh.volume, 
                sh."massAccum", sh."volumeAccum"
                FROM shipments sh
                JOIN direction dir ON sh.directing = dir.id
        WHERE sh."numReport" = %s"""
    report_data, error = get_data_from_db(query, (report_id,))
    if error or not report_data:
        flash(f"Ошибка загрузки отчета для PDF: {error}", 'error')
        return redirect(url_for('main_menu'))

    temp_html_file = "temp_ttn.html"
    output_pdf = os.path.join(r"C:\dll" if os.name == "nt" else "/opt/Doc",
                              f"ttn_{datetime.now().strftime('%Y-%m-%d')}.pdf")

    report_html = render_template('ttn.html', report=report_data[0], report_id=report_id, now=datetime.now())
    with open(temp_html_file, 'w', encoding='utf-8') as f:
        f.write(report_html)

    modulPDF.convert_html_to_pdf(temp_html_file, output_pdf)
    modulPDF.open_pdf(output_pdf)
    modulPDF.delete_temp_html(temp_html_file)

    flash(f"PDF-файл сохранен: {output_pdf}", 'success')
    return redirect(url_for('ttn', report_id=report_id))

@app.errorhandler(Exception)
def handle_exception(e):

    # Страница с ошибкой
    if isinstance(e, HTTPException):
        return e
    return render_template("err.html", e=e), 500

if __name__ == '__main__':
    app.run(host=SERVER_CONFIG["host"], debug=SERVER_CONFIG["debug"], port=SERVER_CONFIG["port"])