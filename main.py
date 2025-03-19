from flask import Flask, render_template, request, flash, url_for, redirect
from werkzeug.exceptions import HTTPException
import psycopg2
from datetime import datetime, timedelta
import modulPDF
import os
import json
import hashlib, itertools, string

app = Flask(__name__)
app.secret_key = 'key'
CONFIG_FILE = "config.json"

# Функция возвращает MD5-хеш пароля
def hash_password(md5pu):
    return "md5" + hashlib.md5(md5pu.encode()).hexdigest()

# Загружаем настройки из JSON файла
def load_config():
    with open(CONFIG_FILE, "r") as file:
        config = json.load(file)

    # Проверяем, зашифрован ли пароль
    password = config["DB_CONFIG"]["password"]

    if not password.startswith("md5"):  # Если пароль не хеширован
        print("Пароль в config.json не хеширован. Хешируем...")  # Отладка
        config["DB_CONFIG"]["password"] = hash_password(password)  # Передаём password

        # Сохраняем обновлённый конфиг
        with open(CONFIG_FILE, "w") as file:
            json.dump(config, file, indent=4)
        print("Пароль зашифрован и сохранён!")

    return config

# Функция дешифрует MD5-хеш
def md5_hash(word):
    return hashlib.md5(word.encode()).hexdigest()

def brute_force_md5(md5_hash_value):
    # Проверка на префикс md5
    if md5_hash_value.startswith("md5"):
        md5_hash_value = md5_hash_value[3:]  # Убираем префикс md5

    alphabet = string.ascii_lowercase  # Латинские буквы
    for combo in itertools.product(alphabet, repeat=3):
        word = ''.join(combo)
        if md5_hash(word) == md5_hash_value:  # Сверяем хеш
            return word
    return "Не удалось расшифровать хеш!"

# Подключение к базе данных и серверу
config = load_config()
DB_CONFIG = config["DB_CONFIG"]
SERVER_CONFIG = config["SERVER_CONFIG"]
DB_CONFIG["password"] = brute_force_md5(config["DB_CONFIG"]["password"])

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
        "start_date": request.form.get('start_date') or request.args.get('start_date'),
        "end_date": request.form.get('end_date') or request.args.get('end_date'),
        "numSm": request.form.get('numSm') or request.args.get('numSm'),
        "post": request.form.get('post') or request.args.get('post'),
        "product": request.form.get('product') or request.args.get('product'),
    }

    print(f"Фильтры: {filters}")

    # Проверяем, был ли POST-запрос
    if request.method == 'POST':
        conditions = []
        params = {}

        try:
            if filters["start_date"]:
                filters["start_date"] = datetime.strptime(filters["start_date"], "%Y-%m-%d").timestamp()
            if filters["end_date"]:
                filters["end_date"] = datetime.strptime(filters["end_date"], "%Y-%m-%d").timestamp()
        except ValueError:
            flash("Некорректный формат даты.", 'error')
            filters["start_date"] = None
            filters["end_date"] = None

        if filters["start_date"]:
            conditions.append('"dDate" >= %(start_date)s')
            params["start_date"] = filters["start_date"]
        if filters["end_date"]:
            conditions.append('"dDate" <= %(end_date)s')
            params["end_date"] = filters["end_date"]
        if filters["post"]:
            conditions.append('sh.post = %(post)s')
            params["post"] = filters["post"]
        if filters["product"]:
            conditions.append('sh.product = %(product)s')
            params["product"] = filters["product"]

        query = """ SELECT sh."numReport", (TO_TIMESTAMP(sh."dDate") AT TIME ZONE 'UTC'), sh.operator, sh."numSm", 
                           dir.txt AS direction, sh.post, sh.product, sh.dose, sh.dens, sh.temp, sh.mass, sh.volume, 
                           sh."massAccum", sh."volumeAccum"
                    FROM shipments sh
                    JOIN direction dir ON sh.directing = dir.id
                """

        # Добавление условий в запрос
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY sh.\"dDate\" DESC"

        # Выполнение запроса
        history, error = get_data_from_db(query, params)
        if error:
            flash(f"Ошибка загрузки истории отчётов: {error}", 'error')
            history = None
    else:
        history = None  # При запросе данные не загружаем

    return render_template('main_menu.html', filters=filters, history=history, now=datetime.now, timedelta=timedelta)

@app.route('/report/<report_name>', methods=['GET', 'POST'])
def report(report_name):
    filters = {
        "start_date": request.form.get('start_date') or request.args.get('start_date'),
        "end_date": request.form.get('end_date') or request.args.get('end_date'),
        "numReport": request.form.get('numReport') or request.args.get('numReport'),
        "post": request.form.get('post') or request.args.get('post'),
    }

    print(f"Фильтры: {filters}")
    # SQL-запросы для отчётов
    queries = {
        "all_data": """SELECT sh."numReport", sh."dDate", sh.operator, sh."numSm", dir.txt AS direction, 
                              sh.post, sh.product, sh.dose, sh.dens, sh.temp, sh.mass, sh.volume, 
                              sh."massAccum", sh."volumeAccum"
                       FROM shipments sh
                       JOIN direction dir ON sh.directing = dir.id"""
    }

    base_query = queries.get(report_name, queries["all_data"])

    # Фильтрация
    params = {}
    conditions = []

    try:
        if filters["start_date"]:
            filters["start_date"] = datetime.strptime(filters["start_date"], "%Y-%m-%d").timestamp()
        if filters["end_date"]:
            filters["end_date"] = datetime.strptime(filters["end_date"], "%Y-%m-%d").timestamp()
    except ValueError:
        flash("Некорректный формат даты.", 'error')
        filters["start_date"] = None
        filters["end_date"] = None

    if filters["start_date"]:
        conditions.append('"dDate" >= %(start_date)s')
        params["start_date"] = filters["start_date"]
    if filters["end_date"]:
        conditions.append('"dDate" <= %(end_date)s')
        params["end_date"] = filters["end_date"]
    if filters["numReport"]:
        conditions.append('sh."numReport" = %(numReport)s')
        params["numReport"] = filters["numReport"]
    if filters["post"]:
        conditions.append('sh.post = %(post)s')
        params["post"] = filters["post"]

    # Соединение базового запроса и условий
    if conditions:
        query = f"{base_query} WHERE {' AND '.join(conditions)} ORDER BY sh.\"dDate\" DESC, sh.\"numReport\" DESC"
    else:
        query = f"{base_query} ORDER BY sh.\"dDate\" DESC"

    # Выполнение запроса
    data, error = get_data_from_db(query, params)
    if error:
        flash(f"Ошибка выполнения запроса: {error}", 'error')
        return redirect(url_for('main_menu'))

    # Генерация HTML-файла для PDF
    temp_html_file = "temp_report.html"
    output_pdf = os.path.join(r"C:\dll" if os.name == "nt" else "/opt/Doc",
                              f"{report_name}_{datetime.now().strftime('%Y-%m-%d')}.pdf")

    try:
        report_html = render_template(f'report_{report_name}.html', data=data, filters=filters, now=datetime.now(), timedelta=timedelta)
        with open(temp_html_file, 'w', encoding='utf-8') as f:
            f.write(report_html)

        modulPDF.convert_html_to_pdf(temp_html_file, output_pdf)
        modulPDF.open_pdf(output_pdf)

    finally:
        if os.path.exists(temp_html_file):
            os.remove(temp_html_file)

    return render_template(f'report_{report_name}.html', data=data, filters=filters, now=datetime.now(), timedelta=timedelta)

@app.route('/report/ttn<int:numReport>', methods=['GET'])
def ttn(numReport):
        # SQL-запрос для получения данных отчёта
        query = """SELECT sh."numReport", (TO_TIMESTAMP(sh."dDate") AT TIME ZONE 'UTC'), sh.operator, sh."numSm", dir.txt AS direction, 
                sh.post, sh.product, sh.dens, sh.temp, sh.mass, sh.volume, 
                sh."massAccum", sh."volumeAccum"
                FROM shipments sh
                JOIN direction dir ON sh.directing = dir.id
        WHERE sh."numReport" = %s"""

        report_data, error = get_data_from_db(query, (numReport,))
        if error or not report_data:
            flash(f"Ошибка загрузки сменного отчёта с ID {numReport}: {error}", 'error')
            return redirect(url_for('main_menu'))

        return render_template('ttn.html', report=report_data[0], numReport=numReport)

@app.route('/save_pdf/<int:numReport>', methods=['POST'])
def save_pdf(numReport):
    query = """SELECT sh."numReport", (TO_TIMESTAMP(sh."dDate") AT TIME ZONE 'UTC'), sh.operator, sh."numSm", dir.txt AS direction, 
                sh.post, sh.product, sh.dens, sh.temp, sh.mass, sh.volume, 
                sh."massAccum", sh."volumeAccum"
                FROM shipments sh
                JOIN direction dir ON sh.directing = dir.id
        WHERE sh."numReport" = %s"""
    report_data, error = get_data_from_db(query, (numReport,))
    if error or not report_data:
        flash(f"Ошибка загрузки отчета для PDF: {error}", 'error')
        return redirect(url_for('main_menu'))

    temp_html_file = "temp_ttn.html"
    output_pdf = os.path.join(r"C:\dll" if os.name == "nt" else "/opt/Doc",
                              f"ttn_{datetime.now().strftime('%Y-%m-%d')}.pdf")

    report_html = render_template('ttn1.html', report=report_data[0], numReport=numReport, now=datetime.now())
    with open(temp_html_file, 'w', encoding='utf-8') as f:
        f.write(report_html)

    modulPDF.convert_html_to_pdf(temp_html_file, output_pdf)
    modulPDF.open_pdf(output_pdf)
    modulPDF.delete_temp_html(temp_html_file)

    flash(f"PDF-файл сохранен: {output_pdf}", 'success')
    return redirect(url_for('ttn', numReport=numReport))

@app.template_filter('timestamp_to_date')
def timestamp_to_date(value):
        return datetime.utcfromtimestamp(value).strftime('%Y-%m-%d %H:%M:%S')

@app.errorhandler(Exception)
def handle_exception(e):

    # Страница с ошибкой
    if isinstance(e, HTTPException):
        return e
    return render_template("err.html", e=e), 500

if __name__ == '__main__':
    app.run(host=SERVER_CONFIG["host"], debug=SERVER_CONFIG["debug"], port=SERVER_CONFIG["port"])