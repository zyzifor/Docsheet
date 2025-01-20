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