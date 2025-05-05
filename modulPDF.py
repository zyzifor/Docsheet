import os
import platform, getpass, pdfkit, win32print, subprocess

def get_wkhtmltopdf_path():
    system = platform.system()
    if system == "Windows":
        return r"C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe"
    elif system == "Linux":
        return "/usr/bin/wkhtmltopdf"
    else:
        raise Exception("Операционная система не поддерживается!")

def convert_html_to_pdf(html_file, output_pdf):
    try:
        wkhtmltopdf_path = get_wkhtmltopdf_path()
        config = pdfkit.configuration(wkhtmltopdf=wkhtmltopdf_path)
        options = {
            'orientation': 'Landscape',  # Альбомная ориентация
            'page-size': 'A4'
        }
        pdfkit.from_file(html_file, output_pdf, configuration=config, options=options)
        print(f"PDF создан: {output_pdf}")
    except OSError as e:
        print(f"Ошибка при создании PDF: {e}")

def delete_temp_html(temp_html_file):
    if os.path.exists(temp_html_file):
        os.remove(temp_html_file)
        print(f"🗑️ Временный HTML файл удален: {temp_html_file}")
    else:
        print(f"⚠️ Файл {temp_html_file} не найден!")

def open_pdf(output_pdf):
    system = platform.system()
    if system == "Windows":
        os.startfile(output_pdf)
    elif system == "Linux":
        current_user = getpass.getuser()

        # Настраиваем переменные окружения для X-сессии
        os.environ["DISPLAY"] = ":0"
        os.environ["XAUTHORITY"] = f"/home/{current_user}/.Xauthority"
        os.environ["XDG_RUNTIME_DIR"] = f"/run/user/{os.getuid()}"

        # Проверка файла и доступов
        if os.path.exists(output_pdf):
            print(f"📂 Открываем PDF: {output_pdf}")

            # Добавляем `xhost` для разрешения доступа к X-серверу
            os.system(f"xhost +si:localuser:{current_user} >/dev/null 2>&1")

            # Открываем PDF через xdg-open с поддержкой всех пользователей
            result = os.system(f"xdg-open {output_pdf} >/dev/null 2>&1 &")
            if result != 0:
                print("⚠️ Ошибка при открытии PDF. Проверьте доступ к X-серверу или xdg-open.")
        else:
            print(f"❌ Файл {output_pdf} не найден!")
    else:
        print("⚠️ Не поддерживаемая операционная система!")

def get_available_printers():
    system = platform.system()
    printers = []

    if system == "Windows":
        for printer_info in win32print.EnumPrinters(win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS):
            printer_name = printer_info[2]
            printers.append(printer_name)

    elif system == "Linux":
        try:
            output = subprocess.check_output(["lpstat", "-a"]).decode("utf-8")
            printers = [line.split()[0] for line in output.strip().split("\n")]
        except Exception as e:
            print(f"Ошибка при получении принтеров: {e}")

    return printers

def print_pdf(pdf_path, printer_name=None):
    system = platform.system()

    if system == 'Windows':
        acroread_path = r"C:\Program Files (x86)\Adobe\Acrobat Reader DC\Reader\AcroRd32.exe"
        if not os.path.exists(acroread_path):
            print("Adobe Reader не найден!")
            return

        try:
            import subprocess
            command = f'"{acroread_path}" /t "{pdf_path}" "{printer_name}"'
            subprocess.run(command, shell=True)
        except Exception as e:
            print(f"Ошибка при печати через Adobe Reader: {e}")

    elif system == 'Linux':
        import subprocess
        try:
            command = ['lp']
            if printer_name:
                command += ['-d', printer_name]
            command.append(pdf_path)
            subprocess.run(command, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception as e:
            print(f"Ошибка при печати: {e}")

def choose_printer_and_print(pdf_path):
    # Получаем список доступных принтеров
    printers = get_available_printers()

    if not printers:
        print("Ошибка: Не найдены доступные принтеры.")
        return

    print("Доступные принтеры:")
    for i, printer in enumerate(printers, 1):
        print(f"{i}. {printer}")

    # Запрашиваем выбор принтера
    choice = input(f"Выберите принтер (1-{len(printers)}): ")

    try:
        selected_printer = printers[int(choice) - 1]
        print_pdf(pdf_path, selected_printer)
    except (ValueError, IndexError):
        print("Ошибка: Неверный выбор принтера.")