from flask import Flask, render_template, request, flash, url_for, redirect, jsonify, send_file
from werkzeug.exceptions import HTTPException
from num2words import num2words
import psycopg2
from datetime import datetime, timedelta
import modulPDF
import os
import getpass
import json
import hashlib, itertools, string, functools


app = Flask(__name__)
app.secret_key = 'key'
CONFIG_FILE = "config.json"

# Разрешаем текущему пользователю подключаться к X-серверу
os.system(f"xhost +si:localuser:{getpass.getuser()} >/dev/null 2>&1")
print(getpass.getuser())

# Функция возвращает MD5-хеш строки
def hash_md5(value):
    return "md5" + hashlib.md5(value.encode()).hexdigest()

# Загружаем настройки из JSON файла
def load_config():
    with open(CONFIG_FILE, "r") as file:
        config = json.load(file)

    user = config["DB_CONFIG"]["user"]
    password = config["DB_CONFIG"]["password"]
    updated = False  # Флаг изменений

    # Хешируем логин, если он ещё не хеширован
    if not user.startswith("md5"):
        config["DB_CONFIG"]["user"] = hash_md5(user)
        updated = True  # Устанавливаем флаг, что конфиг изменился

    # Хешируем пароль, если он ещё не хеширован
    if not password.startswith("md5"):
        config["DB_CONFIG"]["password"] = hash_md5(password)
        updated = True  # Устанавливаем флаг, что конфиг изменился

    # Если были изменения, сохраняем обновленный конфиг
    if updated:
        with open(CONFIG_FILE, "w") as file:
            json.dump(config, file, indent=4)
        print("Хеширование логина и пароля завершено!")

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
DB_CONFIG["user"] = brute_force_md5(config["DB_CONFIG"]["user"])

def get_data_from_db(query, params=None):
    # Выполняет запрос к базе данных и возвращает результат
    try:
        connection = psycopg2.connect(**DB_CONFIG)
        connection.set_client_encoding('UTF8')
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
    # Получаем список продуктов из базы данных
    query = "SELECT DISTINCT product FROM shipments"
    products, error = get_data_from_db(query)  # Получаем список продуктов из БД
    if error:
        flash(f"Ошибка при получении списка продуктов: {error}", 'error')
        products = []

    # Обработка фильтров
    if request.method == 'POST':
        filters = {
            "start_date": request.form.get('start_date'),
            "end_date": request.form.get('end_date'),
            "numSm": request.form.get('numSm'),
            "post": request.form.get('post'),
            "product": request.form.get('product'),
        }
    else:
        today = datetime.today()
        day_ago = today - timedelta(days=1)
        filters = {
            "start_date": day_ago.strftime('%Y-%m-%d'),
            "end_date": today.strftime('%Y-%m-%d'),
            "numSm": '',
            "post": '',
            "product": '',
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

        query = """ 
            SELECT sh."numReport", sh."dDate", sh.operator, sh."numSm", 
                   dir.txt AS direction, sh.post, sh.product, sh.dose, sh.dens, 
                   sh.temp, sh.mass, sh.volume, sh."massAccum", sh."volumeAccum"
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

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return render_template('table.html', history=history)
    else:
        return render_template('main_menu.html', filters=filters, history=history, products=products, now=datetime.now, timedelta=timedelta)

# Получение доступных принтеров
@app.route('/get_printers', methods=['GET'])
def get_printers():
    printers = modulPDF.get_available_printers()
    return jsonify({"printers": printers})

@app.route('/save_pdf_report/<report_name>', methods=['POST'])
def save_pdf_report(report_name):
    filters = {
        "start_date": request.form.get('start_date'),
        "end_date": request.form.get('end_date'),
        "numReport": request.form.get('numReport'),
        "post": request.form.get('post'),
        "product": request.form.get('product'),
    }

    params = {}
    conditions = []

    try:
        if filters["start_date"]:
            filters["start_date"] = datetime.strptime(filters["start_date"], "%Y-%m-%d").timestamp()
        if filters["end_date"]:
            filters["end_date"] = datetime.strptime(filters["end_date"], "%Y-%m-%d").timestamp()
    except ValueError:
        flash("Ошибка в формате даты", "error")
        return jsonify({"success": False, "message": "Ошибка в формате даты"})

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
    if filters["product"]:
        conditions.append('sh.product = %(product)s')
        params["product"] = filters["product"]

    query = f"""
        SELECT sh."numReport", sh."dDate", sh.operator, sh."numSm", dir.txt AS direction, 
               sh.post, sh.product, sh.dose, sh.dens, sh.temp, sh.mass, sh.volume, 
               sh."massAccum", sh."volumeAccum"
        FROM shipments sh
        JOIN direction dir ON sh.directing = dir.id
    """
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += ' ORDER BY sh."dDate" DESC'

    data, error = get_data_from_db(query, params)
    if error:
        return jsonify({"success": False, "message": f"Ошибка при получении данных: {error}"})

    temp_html_file = "temp_report.html"
    output_pdf = os.path.join(r"C:\dll" if os.name == "nt" else "/opt/Doc",
                              f"{report_name}_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.pdf")

    try:
        html = render_template(f'report_{report_name}.html', data=data, filters=filters, now=datetime.now(),
                               timedelta=timedelta)
        with open(temp_html_file, 'w', encoding='utf-8') as f:
            f.write(html)

        modulPDF.convert_html_to_pdf(temp_html_file, output_pdf)
        flash(f"PDF успешно сохранён : {output_pdf}", "success")

        # Получаем принтер из формы
        selected_printer = request.form.get('printer')
        if request.form.get('print') == 'true':
            print(f"Печать {output_pdf} на принтере {selected_printer}")
            modulPDF.print_pdf(output_pdf, selected_printer)

        return jsonify({"success": True, "message": "PDF успешно сохранён", "pdf_url": output_pdf})

    except Exception as e:
        return jsonify({"success": False, "message": f"Ошибка при создании PDF: {str(e)}"})

    finally:
        if os.path.exists(temp_html_file):
            os.remove(temp_html_file)

@app.route('/report/ttn<int:numReport>', methods=['GET'])
def ttn(numReport):
        # SQL-запрос для получения данных отчёта
        query = """SELECT sh."numReport", sh."dDate", sh.operator, sh."numSm", dir.txt AS direction, sh.post, sh.product, sh.dens, sh.temp, sh.mass, sh.volume, sh."massAccum", sh."volumeAccum", sh.typeunit,
    CASE 
        WHEN sh.operation = 1 THEN cr."number"
        ELSE NULL 
    END AS car_number,
    CASE 
        WHEN sh.operation = 1 THEN cr.driver
        ELSE NULL 
    END AS driver,
    CASE 
        WHEN sh.operation = 1 THEN cr."nameCar"
        ELSE NULL 
    END AS nameCar,
    
    CASE 
        WHEN sh.operation = 1 THEN cr.count
        ELSE NULL 
    END AS nameCar,
    t0.name AS sender_name, t0.address AS sender_address, t0.tel AS sender_tel,
    t1.name AS receiver_name, t1.address AS receiver_address, t1.tel AS receiver_tel,
    t2.name AS payer_name, t2.address AS payer_address, t2.tel AS payer_tel

FROM shipments sh
JOIN direction dir ON sh.directing = dir.id

LEFT JOIN car_carriers cr ON cr.id = sh.car_id AND sh.operation = 1

LEFT JOIN ttn t0 ON t0.id = sh.ttntype0
LEFT JOIN ttn t1 ON t1.id = sh.ttntype1
LEFT JOIN ttn t2 ON t2.id = sh.ttntype2

WHERE sh."numReport" = %s;"""

        report_data, error = get_data_from_db(query, (numReport,))
        if error or not report_data:
            flash(f"Ошибка загрузки сменного отчёта с ID {numReport}: {error}", 'error')
            return redirect(url_for('main_menu'))

        return render_template('ttn.html', report=report_data[0], numReport=numReport)

@app.route('/save_pdf_ttn/<int:numReport>', methods=['POST'])
def save_pdf_ttn(numReport):
    try:
        print_flag = request.form.get('print') == 'true'  # Проверка, нужно ли печатать

        query = """SELECT sh."numReport", sh."dDate", sh.operator, sh."numSm", dir.txt AS direction, sh.post, sh.product, sh.dens, sh.temp, sh.mass, sh.volume, sh."massAccum", sh."volumeAccum", sh.typeunit,
    CASE 
        WHEN sh.operation = 1 THEN cr."number"
        ELSE NULL 
    END AS car_number,
    CASE 
        WHEN sh.operation = 1 THEN cr.driver
        ELSE NULL 
    END AS driver,
    CASE 
        WHEN sh.operation = 1 THEN cr."nameCar"
        ELSE NULL 
    END AS nameCar,
    
    CASE 
        WHEN sh.operation = 1 THEN cr.count
        ELSE NULL 
    END AS nameCar,
    t0.name AS sender_name, t0.address AS sender_address, t0.tel AS sender_tel,
    t1.name AS receiver_name, t1.address AS receiver_address, t1.tel AS receiver_tel,
    t2.name AS payer_name, t2.address AS payer_address, t2.tel AS payer_tel

FROM shipments sh
JOIN direction dir ON sh.directing = dir.id

LEFT JOIN car_carriers cr ON cr.id = sh.car_id AND sh.operation = 1

LEFT JOIN ttn t0 ON t0.id = sh.ttntype0
LEFT JOIN ttn t1 ON t1.id = sh.ttntype1
LEFT JOIN ttn t2 ON t2.id = sh.ttntype2

WHERE sh."numReport" = %s;"""

        report_data, error = get_data_from_db(query, (numReport,))
        if error or not report_data:
            return jsonify({"success": False, "message": f"Ошибка загрузки отчета: {error}"}), 500

        # Путь к файлу
        output_pdf = os.path.join(
            r"C:\dll" if os.name == "nt" else "/opt/Doc",
            f"ttn{numReport}_{datetime.now().strftime('%Y-%m-%d')}.pdf"
        )

        # Генерация HTML и сохранение во временный файл
        report_html = render_template('ttn1.html', report=report_data[0], numReport=numReport, now=datetime.now())
        temp_html_file = "temp_ttn.html"
        with open(temp_html_file, 'w', encoding='utf-8') as f:
            f.write(report_html)

        # Конвертация в PDF
        modulPDF.convert_html_to_pdf(temp_html_file, output_pdf)

        # Получаем принтер из формы
        selected_printer = request.form.get('printer')
        if request.form.get('print') == 'true':
            print(f"Печать {output_pdf} на принтере {selected_printer}")
            modulPDF.print_pdf(output_pdf, selected_printer)

        # Удаление временного файла
        modulPDF.delete_temp_html(temp_html_file)

        return jsonify({"success": True, "message": f"PDF {'отправлен на печать' if print_flag else 'сохранён'}: {output_pdf}"})

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "message": f"Внутренняя ошибка: {str(e)}"}), 500

@app.template_filter('timestamp_to_date')
def timestamp_to_date(value):
    return datetime.fromtimestamp(value).strftime('%Y-%m-%d %H:%M:%S')

@app.template_filter('timestamp_to_day')
def timestamp_to_day(value):
    return datetime.fromtimestamp(value).strftime('%d')

@app.template_filter('timestamp_to_month')
def timestamp_to_month(value):
    return datetime.fromtimestamp(value).strftime('%m')

@app.template_filter('timestamp_to_year')
def timestamp_to_year(value):
    return datetime.fromtimestamp(value).strftime('%Y')

@app.template_filter('month_name')
def month_name(value):
    months = [
        "января", "февраля", "марта", "апреля", "мая", "июня",
        "июля", "августа", "сентября", "октября", "ноября", "декабря"
    ]
    month_index = int(value) - 1
    return months[month_index]

@app.template_filter('number_to_words')
def number_to_words(value):
    if not isinstance(value, (int, float)):
        return "Ошибка в данных"

    value = round(value, 2)
    int_part = int(value)
    frac_part = round((value - int_part) * 100)

    result = num2words(int_part, lang='ru')

    if frac_part > 0:
        result += f" целых {num2words(frac_part, lang='ru')} сотых"

    return result

@app.template_filter('number_to_words_unit')
def number_to_words_unit(value, unit_code):

    if not isinstance(value, (int, float)) or unit_code not in [0, 1, 2]:
        return "Ошибка в данных"

    value = round(value, 2)  # Округляем до 2 знаков
    int_part = int(value)  # Целая часть
    frac_part = round((value - int_part) * 100)  # Дробная часть (копейки, мл и т. д.)

    # Соответствие кода и единицы измерения (сокращенные формы)
    units = {
        0: "кг",  # 0 → кг
        1: "л",   # 1 → литры
        2: "т"    # 2 → тонны
    }

    # Собираем строку
    result = num2words(int_part, lang='ru') + " " + units[unit_code]

    if frac_part > 0:
        result += f" {num2words(frac_part, lang='ru')} сотых"

    return result

@app.template_filter('unit_name')
def unit_name(unit_code):
    units = {
        0: "кг",   # килограммы
        1: "л",    # литры
        2: "т"     # тонны
    }
    return units.get(unit_code, "неизвестно")

@app.template_filter('count_names')
def count_names(names):
    if isinstance(names, list):
        return len(names)
    elif isinstance(names, str):
        return 1 if names.strip() else 0
    return 0


@app.errorhandler(Exception)
def handle_exception(e):
    # Страница с ошибкой
    if isinstance(e, HTTPException):
        return e
    return render_template("err.html", e=e), 500

if __name__ == '__main__':
    app.run(host=SERVER_CONFIG["host"], debug=SERVER_CONFIG["debug"], port=SERVER_CONFIG["port"])