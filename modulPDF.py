import pdfkit
import os
import sys
import platform
import requests

def download_html(url, temp_html_file):
    # Загружаем HTML по URL и сохраняем в файл
    response = requests.get(url)
    with open(temp_html_file, 'w', encoding='utf-8') as f:
        f.write(response.text)
    print(f"HTML файл загружен: {temp_html_file}")

def convert_html_to_pdf(html_file, output_pdf):
    system = platform.system()
    if system == "Windows":
        config = pdfkit.configuration(wkhtmltopdf=r"C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe")
        pdfkit.from_file(html_file, output_pdf, configuration=config)
    elif system == "Linux":
        pdfkit.from_file(html_file, output_pdf)
    print(f"PDF создан: {output_pdf}")

def delete_temp_html(temp_html_file):
    # Удаляем временный PDF
    os.remove(temp_html_file)
    print(f"Временный pdf файл удален: {temp_html_file}")

def open_pdf(output_pdf):
    # Открытие PDF в стандартной программе
    system = platform.system()
    if system == "Windows":
        os.startfile(output_pdf)
    elif system == "Linux":
        os.system(f"xdg-open {output_pdf}")
    else:
        print("Не поддерживаемая операционная система")

if __name__ == "__main__":
    html_file = sys.argv[1] # URL HTML
    temp_html_file = "temp_report.html"  # Временный HTML файл
    output_pdf = "sys.argv[1].pdf"  # Путь для сохранения PDF файла

    download_html(sys.argv[1], temp_html_file)
    convert_html_to_pdf(temp_html_file, output_pdf)
    delete_temp_html(temp_html_file)
    open_pdf(output_pdf)