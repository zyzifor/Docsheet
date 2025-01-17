Установка зависимостей
pip install flask, werkzeug, psycopg2
Подключаем базу
    'dbname': 'dbname', название базы
    'user': 'user', имя пользователя psql
    'password': 'password', пароль psql
    'host': '0.0.0.0', ip psql
    'port': 5432
Настраиваем сервер
  app.run(host='0.0.0.0', debug=True, port=5000)
Вводим IP или оставляем локальный, если порт занят выбираем другой