Установка зависимостей<br>
pip install flask, werkzeug, psycopg2<br>
Подключаем базу<br>
    'dbname': 'dbname', название базы<br>
    'user': 'user', имя пользователя psql<br>
    'password': 'password', пароль psql<br>
    'host': '0.0.0.0', ip psql<br>
    'port': 5432<br>
Настраиваем сервер<br>
  app.run(host='0.0.0.0', debug=True, port=5000)<br>
Вводим IP или оставляем локальный, если порт занят выбираем другой<br>

modulePDF:<br>
Модуль для скачивания и открытия из html в pdf файла<br>

Установка:<br>
pip install pdfkit<br>
pip install requests<br>
sudo apt-get install wkhtmltopdf #for linux<br>
https://wkhtmltopdf.org/downloads.html #for Windows<br>

Запуск:<br>
python modulPDF.py ссылка<br>
