import sys
import os
import json
import datetime

# PyQt5 modülleri
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QTabWidget, QWidget, QVBoxLayout, QHBoxLayout,
    QTableWidget, QTableWidgetItem, QPushButton, QDialog, QFormLayout, QLineEdit,
    QTextEdit, QDateEdit, QDateTimeEdit, QLabel, QMessageBox, QPlainTextEdit,
    QCalendarWidget, QDialogButtonBox, QCheckBox
)
from PyQt5 import QtCore

# ---------------------------
# YARDIMCI FONKSİYON: Gelen JSON yanıtını temizle
# ---------------------------
def clean_json_response(response):
    """
    Gemini API'dan gelen yanıtta, eğer yanıt ```json ... ``` şeklinde gelmişse,
    bu işaretleri kaldırarak geçerli JSON formatına dönüştürür.
    """
    response = response.strip()
    if response.startswith("```json"):
        # İlk satır "```json" ise kaldır
        lines = response.splitlines()
        if lines and lines[0].strip() == "```json":
            lines = lines[1:]
        # Son satır "```" ise kaldır
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        response = "\n".join(lines)
    return response.strip()

# ---------------------------
# KONFIGÜRASYON DOSYASI & VERİ DOSYALARI
# ---------------------------
CONFIG_FILE = "config.json"
TASKS_FILE = "tasks.json"
EVENTS_FILE = "events.json"
# Artık ayrı liste dosyası kullanılmıyor.

if not os.path.exists(CONFIG_FILE):
    default_config = {
        "gemini_api_key": "YOUR_API_KEY",      # Kendi API anahtarınızı girin.
        "model": "gemini-2.0-flash"              # Doğru model adı.
    }
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(default_config, f, indent=4)
    app = QApplication(sys.argv)
    QMessageBox.critical(None, "Config Eksik",
                         "config dosyası oluşturuldu.\nLütfen dosyayı düzenleyip yeniden başlatın.")
    sys.exit(1)

with open(CONFIG_FILE, "r", encoding="utf-8") as f:
    config = json.load(f)

# ---------------------------
# VERİ YÖNETİMİ: TASKS ve EVENTS
# ---------------------------
def load_tasks():
    if os.path.exists(TASKS_FILE):
        try:
            with open(TASKS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []

def save_tasks(tasks):
    with open(TASKS_FILE, "w", encoding="utf-8") as f:
        json.dump(tasks, f, indent=4, ensure_ascii=False)

def load_events():
    if os.path.exists(EVENTS_FILE):
        try:
            with open(EVENTS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []

def save_events(events):
    with open(EVENTS_FILE, "w", encoding="utf-8") as f:
        json.dump(events, f, indent=4, ensure_ascii=False)

# ---------------------------
# GOOGLE GENERATIVE AI ENTEGRASYONU
# ---------------------------
try:
    import google.generativeai as genai
except ImportError:
    raise ImportError("google.generativeai modülü bulunamadı. Lütfen 'pip install google-generativeai' komutuyla kurulum yapın.")

genai.configure(api_key=config["gemini_api_key"])

def call_gemini_api(prompt):
    """
    Verilen prompt'u Google Generative AI Gemini API'sine gönderir ve yanıtı döndürür.
    """
    try:
        generation_config = {
            "temperature": 1,
            "top_p": 0.95,
            "top_k": 40,
            "max_output_tokens": 8192,
        }
        model = genai.GenerativeModel(
            model_name=config.get("model", "gemini-2.0-flash"),
            generation_config=generation_config,
        )
        chat_session = model.start_chat(history=[])
        response = chat_session.send_message(prompt)
        return response.text
    except Exception as e:
        return json.dumps({"error": str(e)})

# ---------------------------
# GEMINI İŞ PARÇACIĞI (WORKER)
# ---------------------------
class GeminiWorker(QtCore.QThread):
    finished = QtCore.pyqtSignal(str)  # API yanıtı string olarak dönecek

    def __init__(self, prompt, parent=None):
        super().__init__(parent)
        self.prompt = prompt

    def run(self):
        result = call_gemini_api(self.prompt)
        self.finished.emit(result)

# ---------------------------
# ÖZEL DİYALOGLAR: Görev ve Etkinlik Formları
# ---------------------------
class TaskDialog(QDialog):
    def __init__(self, parent=None, task=None):
        super().__init__(parent)
        self.setWindowTitle("Görev " + ("Düzenle" if task else "Ekle"))
        self.resize(400, 300)
        layout = QFormLayout(self)

        self.title_edit = QLineEdit(self)
        self.desc_edit = QTextEdit(self)
        self.due_date_edit = QDateEdit(self)
        self.due_date_edit.setCalendarPopup(True)
        self.due_date_edit.setDisplayFormat("yyyy-MM-dd")

        if task:
            self.title_edit.setText(task.get("title", ""))
            self.desc_edit.setPlainText(task.get("description", ""))
            due_date_str = task.get("saved_due_date", task.get("due_date", ""))
            if due_date_str:
                try:
                    date_obj = datetime.datetime.strptime(due_date_str, "%Y-%m-%d").date()
                    self.due_date_edit.setDate(QtCore.QDate(date_obj.year, date_obj.month, date_obj.day))
                except Exception:
                    self.due_date_edit.setDate(QtCore.QDate.currentDate())
            else:
                self.due_date_edit.setDate(QtCore.QDate.currentDate())
        else:
            self.due_date_edit.setDate(QtCore.QDate.currentDate())

        layout.addRow("Başlık:", self.title_edit)
        layout.addRow("Açıklama:", self.desc_edit)
        layout.addRow("Bitiş Tarihi:", self.due_date_edit)

        btn_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btn_box.accepted.connect(self.accept)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

    def get_data(self):
        return {
            "title": self.title_edit.text(),
            "description": self.desc_edit.toPlainText(),
            "due_date": self.due_date_edit.date().toString("yyyy-MM-dd")
        }

class EventDialog(QDialog):
    def __init__(self, parent=None, event=None):
        super().__init__(parent)
        self.setWindowTitle("Etkinlik " + ("Düzenle" if event else "Ekle"))
        self.resize(400, 300)
        layout = QFormLayout(self)

        self.title_edit = QLineEdit(self)
        self.desc_edit = QTextEdit(self)
        self.datetime_edit = QDateTimeEdit(self)
        self.datetime_edit.setCalendarPopup(True)
        self.datetime_edit.setDisplayFormat("yyyy-MM-dd HH:mm")

        if event:
            self.title_edit.setText(event.get("title", ""))
            self.desc_edit.setPlainText(event.get("description", ""))
            datetime_str = event.get("datetime", "")
            if datetime_str:
                try:
                    dt_obj = datetime.datetime.strptime(datetime_str, "%Y-%m-%d %H:%M")
                    self.datetime_edit.setDateTime(QtCore.QDateTime(dt_obj.year, dt_obj.month, dt_obj.day, dt_obj.hour, dt_obj.minute))
                except Exception:
                    self.datetime_edit.setDateTime(QtCore.QDateTime.currentDateTime())
            else:
                self.datetime_edit.setDateTime(QtCore.QDateTime.currentDateTime())
        else:
            self.datetime_edit.setDateTime(QtCore.QDateTime.currentDateTime())

        layout.addRow("Başlık:", self.title_edit)
        layout.addRow("Açıklama:", self.desc_edit)
        layout.addRow("Tarih & Saat:", self.datetime_edit)

        btn_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btn_box.accepted.connect(self.accept)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

    def get_data(self):
        return {
            "title": self.title_edit.text(),
            "description": self.desc_edit.toPlainText(),
            "datetime": self.datetime_edit.dateTime().toString("yyyy-MM-dd HH:mm")
        }

# ---------------------------
# ANA UYGULAMA PENCERESİ (PyQt5)
# ---------------------------
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Görev Listesi ve Takvim Programı")
        self.resize(1000, 700)
        self.tasks = load_tasks()
        self.events = load_events()
        # Yapay zekadan alınan görev listesi yanıtını saklamak için:
        self.last_task_list_data = None
        self.last_program_data = None  # Program takvimi yanıtı için
        self.initUI()

    def initUI(self):
        self.tab_widget = QTabWidget(self)
        self.setCentralWidget(self.tab_widget)

        self.tasks_tab = QWidget()
        self.calendar_tab = QWidget()
        self.gemini_tab = QWidget()

        self.tab_widget.addTab(self.tasks_tab, "Görev Listesi")
        self.tab_widget.addTab(self.calendar_tab, "Takvim")
        self.tab_widget.addTab(self.gemini_tab, "Yapay Zeka")

        self.init_tasks_tab()
        self.init_calendar_tab()
        self.init_gemini_tab()

    # ----- Görev Listesi Sekmesi -----
    def init_tasks_tab(self):
        layout = QVBoxLayout(self.tasks_tab)
        self.tasks_table = QTableWidget(self)
        self.tasks_table.setColumnCount(4)
        self.tasks_table.setHorizontalHeaderLabels(["Başlık", "Açıklama", "Bitiş Tarihi", "Tamamlandı"])
        self.tasks_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.tasks_table.setEditTriggers(QTableWidget.NoEditTriggers)
        layout.addWidget(self.tasks_table)

        btn_layout = QHBoxLayout()
        add_btn = QPushButton("Yeni Görev Ekle")
        edit_btn = QPushButton("Düzenle")
        delete_btn = QPushButton("Sil")
        toggle_btn = QPushButton("Tamamlandı/İptal")
        btn_layout.addWidget(add_btn)
        btn_layout.addWidget(edit_btn)
        btn_layout.addWidget(delete_btn)
        btn_layout.addWidget(toggle_btn)
        layout.addLayout(btn_layout)

        add_btn.clicked.connect(self.add_task)
        edit_btn.clicked.connect(self.edit_task)
        delete_btn.clicked.connect(self.delete_task)
        toggle_btn.clicked.connect(self.toggle_task_completion)

        self.refresh_tasks_table()

    def refresh_tasks_table(self):
        self.tasks_table.setRowCount(0)
        for task in self.tasks:
            row = self.tasks_table.rowCount()
            self.tasks_table.insertRow(row)
            self.tasks_table.setItem(row, 0, QTableWidgetItem(task.get("title", "")))
            self.tasks_table.setItem(row, 1, QTableWidgetItem(task.get("description", "")))
            self.tasks_table.setItem(row, 2, QTableWidgetItem(task.get("due_date", "")))
            completed_text = "Evet" if task.get("completed", False) else "Hayır"
            self.tasks_table.setItem(row, 3, QTableWidgetItem(completed_text))
            self.tasks_table.item(row, 0).setData(QtCore.Qt.UserRole, task.get("id"))

    def add_task(self):
        dialog = TaskDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            data = dialog.get_data()
            new_task = {
                "id": str(QtCore.QDateTime.currentMSecsSinceEpoch()),
                "title": data["title"],
                "description": data["description"],
                "due_date": data["due_date"],
                "completed": False
            }
            self.tasks.append(new_task)
            save_tasks(self.tasks)
            self.refresh_tasks_table()

    def edit_task(self):
        selected_items = self.tasks_table.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "Uyarı", "Düzenlenecek görevi seçiniz.")
            return
        task_id = selected_items[0].data(QtCore.Qt.UserRole)
        task = next((t for t in self.tasks if t.get("id") == task_id), None)
        if not task:
            QMessageBox.warning(self, "Hata", "Görev bulunamadı.")
            return
        dialog = TaskDialog(self, task)
        if dialog.exec_() == QDialog.Accepted:
            data = dialog.get_data()
            task["title"] = data["title"]
            task["description"] = data["description"]
            if task.get("completed", False):
                task["saved_due_date"] = data["due_date"]
            else:
                task["due_date"] = data["due_date"]
            save_tasks(self.tasks)
            self.refresh_tasks_table()

    def delete_task(self):
        selected_items = self.tasks_table.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "Uyarı", "Silinecek görevi seçiniz.")
            return
        task_id = selected_items[0].data(QtCore.Qt.UserRole)
        self.tasks = [t for t in self.tasks if t.get("id") != task_id]
        save_tasks(self.tasks)
        self.refresh_tasks_table()

    def toggle_task_completion(self):
        selected_items = self.tasks_table.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "Uyarı", "Görevi seçiniz.")
            return
        task_id = selected_items[0].data(QtCore.Qt.UserRole)
        task = next((t for t in self.tasks if t.get("id") == task_id), None)
        if not task:
            QMessageBox.warning(self, "Hata", "Görev bulunamadı.")
            return
        if not task.get("completed", False):
            task["completed"] = True
            if "saved_due_date" not in task:
                task["saved_due_date"] = task.get("due_date", "")
                task["due_date"] = ""
        else:
            task["completed"] = False
            if "saved_due_date" in task:
                task["due_date"] = task["saved_due_date"]
                del task["saved_due_date"]
        save_tasks(self.tasks)
        self.refresh_tasks_table()

    # ----- Takvim Sekmesi -----
    def init_calendar_tab(self):
        layout = QHBoxLayout(self.calendar_tab)
        self.calendar_widget = QCalendarWidget(self)
        self.calendar_widget.setGridVisible(True)
        layout.addWidget(self.calendar_widget, 1)

        right_widget = QWidget(self)
        right_layout = QVBoxLayout(right_widget)
        self.events_table = QTableWidget(self)
        self.events_table.setColumnCount(3)
        self.events_table.setHorizontalHeaderLabels(["Başlık", "Tarih & Saat", "Açıklama"])
        self.events_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.events_table.setEditTriggers(QTableWidget.NoEditTriggers)
        right_layout.addWidget(self.events_table)

        btn_layout = QHBoxLayout()
        add_event_btn = QPushButton("Yeni Etkinlik Ekle")
        edit_event_btn = QPushButton("Düzenle")
        delete_event_btn = QPushButton("Sil")
        btn_layout.addWidget(add_event_btn)
        btn_layout.addWidget(edit_event_btn)
        btn_layout.addWidget(delete_event_btn)
        right_layout.addLayout(btn_layout)

        layout.addWidget(right_widget, 2)

        add_event_btn.clicked.connect(self.add_event)
        edit_event_btn.clicked.connect(self.edit_event)
        delete_event_btn.clicked.connect(self.delete_event)
        self.calendar_widget.selectionChanged.connect(self.refresh_events_table)
        self.refresh_events_table()

    def refresh_events_table(self):
        self.events_table.setRowCount(0)
        selected_date = self.calendar_widget.selectedDate().toString("yyyy-MM-dd")
        events_for_date = [ev for ev in self.events if ev.get("datetime", "").startswith(selected_date)]
        for ev in events_for_date:
            row = self.events_table.rowCount()
            self.events_table.insertRow(row)
            self.events_table.setItem(row, 0, QTableWidgetItem(ev.get("title", "")))
            self.events_table.setItem(row, 1, QTableWidgetItem(ev.get("datetime", "")))
            self.events_table.setItem(row, 2, QTableWidgetItem(ev.get("description", "")))
            self.events_table.item(row, 0).setData(QtCore.Qt.UserRole, ev.get("id"))

    def add_event(self):
        dialog = EventDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            data = dialog.get_data()
            new_event = {
                "id": str(QtCore.QDateTime.currentMSecsSinceEpoch()),
                "title": data["title"],
                "description": data["description"],
                "datetime": data["datetime"]
            }
            self.events.append(new_event)
            save_events(self.events)
            self.refresh_events_table()

    def edit_event(self):
        selected_items = self.events_table.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "Uyarı", "Düzenlenecek etkinliği seçiniz.")
            return
        event_id = selected_items[0].data(QtCore.Qt.UserRole)
        event = next((ev for ev in self.events if ev.get("id") == event_id), None)
        if not event:
            QMessageBox.warning(self, "Hata", "Etkinlik bulunamadı.")
            return
        dialog = EventDialog(self, event)
        if dialog.exec_() == QDialog.Accepted:
            data = dialog.get_data()
            event["title"] = data["title"]
            event["description"] = data["description"]
            event["datetime"] = data["datetime"]
            save_events(self.events)
            self.refresh_events_table()

    def delete_event(self):
        selected_items = self.events_table.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "Uyarı", "Silinecek etkinliği seçiniz.")
            return
        event_id = selected_items[0].data(QtCore.Qt.UserRole)
        self.events = [ev for ev in self.events if ev.get("id") != event_id]
        save_events(self.events)
        self.refresh_events_table()

    # ----- Yapay Zeka / Gemini Sekmesi (3 alt bölüm) -----
    def init_gemini_tab(self):
        layout = QVBoxLayout(self.gemini_tab)
        self.gemini_sub_tabs = QTabWidget(self.gemini_tab)
        layout.addWidget(self.gemini_sub_tabs)

        # Bölüm 1: Program Takvimi Oluşturma
        self.program_tab = QWidget()
        self.init_gemini_program_tab(self.program_tab)
        self.gemini_sub_tabs.addTab(self.program_tab, "Program Takvimi")

        # Bölüm 2: Görev Listesi Oluşturma (yapay zekadan gelen görevler, mevcut görevlerin üzerine eklenecek)
        self.list_tab = QWidget()
        self.init_gemini_list_tab(self.list_tab)
        self.gemini_sub_tabs.addTab(self.list_tab, "Liste Oluşturma")

        # Bölüm 3: Soru & Cevap
        self.qa_tab = QWidget()
        self.init_gemini_qa_tab(self.qa_tab)
        self.gemini_sub_tabs.addTab(self.qa_tab, "Soru & Cevap")

    def init_gemini_program_tab(self, widget):
        layout = QVBoxLayout(widget)
        instructions = QLabel(
            "Lütfen program takvimi oluşturmak için aşağıdaki format talimatlarına kesinlikle uyunuz:\n\n"
            "Format:\n"
            "{\n"
            '  "program": {\n'
            '      "günler": [\n'
            "          {\n"
            '             "tarih": "YYYY-MM-DD",\n'
            '             "etkinlikler": [\n'
            '                  {"saat": "HH:MM", "başlık": "Etkinlik Başlığı", "açıklama": "Etkinlik Açıklaması"}\n'
            "             ]\n"
            "          },\n"
            "          ...\n"
            "      ]\n"
            "  },\n"
            '  "yorum": "Program oluşturulurken dikkate alınan önemli noktalar veya özet."\n'
            "}\n\n"
            "Lütfen yanıtınızı yalnızca geçerli JSON formatında ve markdown biçimlendirme olmadan veriniz. Ekstra açıklama veya yorum eklemeyiniz.\n"
        )
        layout.addWidget(instructions)
        self.program_input = QPlainTextEdit(widget)
        self.program_input.setPlaceholderText("Eklemek istediğiniz ekstra detayları buraya yazınız...")
        layout.addWidget(self.program_input)
        self.program_send_btn = QPushButton("Gönder", widget)
        layout.addWidget(self.program_send_btn)
        self.program_send_btn.clicked.connect(self.send_program_message)
        # Sadece yorum göster seçeneği
        self.program_only_comment_checkbox = QCheckBox("Sadece Yorum Göster", widget)
        layout.addWidget(self.program_only_comment_checkbox)
        self.program_output = QPlainTextEdit(widget)
        self.program_output.setReadOnly(True)
        layout.addWidget(self.program_output)
        self.program_only_comment_checkbox.toggled.connect(self.update_program_output)

    def init_gemini_list_tab(self, widget):
        layout = QVBoxLayout(widget)
        instructions = QLabel(
            "Lütfen aşağıdaki kurallara kesinlikle uyularak, kullanıcının istediği görev listesini oluşturun:\n\n"
            "Format:\n"
            "{\n"
            '  "gorev_listesi": [\n'
            '      {"id": "benzersiz_id (örn: milisaniye timestamp, isteğe bağlı)", "title": "Görev Başlığı", "description": "Görev Açıklaması", "due_date": "YYYY-MM-DD", "completed": false},\n'
            "      ...\n"
            "  ],\n"
            '  "yorum": "Görev listesi oluşturulurken dikkate alınan önemli noktalar veya özet."\n'
            "}\n\n"
            "Lütfen yanıtınızı yalnızca geçerli JSON formatında ve markdown biçimlendirme olmadan veriniz. Ekstra açıklama veya yorum eklemeyiniz."
        )
        layout.addWidget(instructions)
        self.list_input = QPlainTextEdit(widget)
        self.list_input.setPlaceholderText("Görev listesine eklemek istediğiniz detayları buraya yazınız...")
        layout.addWidget(self.list_input)
        self.list_send_btn = QPushButton("Gönder", widget)
        layout.addWidget(self.list_send_btn)
        self.list_send_btn.clicked.connect(self.send_list_message)
        # Yorum kısmını göstermek için checkbox (program sekmesindeki gibi)
        self.list_only_comment_checkbox = QCheckBox("Sadece Yorum Göster", widget)
        layout.addWidget(self.list_only_comment_checkbox)
        self.list_output = QPlainTextEdit(widget)
        self.list_output.setReadOnly(True)
        layout.addWidget(self.list_output)
        self.list_only_comment_checkbox.toggled.connect(self.update_list_output)

    def init_gemini_qa_tab(self, widget):
        layout = QVBoxLayout(widget)
        instructions = QLabel(
            "Lütfen aşağıdaki mevcut program takvimi ve görev listesi verilerine dayanarak, sorduğunuz soruya cevap veriniz.\n"
            "Bu bölümde yalnızca cevap verilecektir."
        )
        layout.addWidget(instructions)
        self.qa_input = QPlainTextEdit(widget)
        self.qa_input.setPlaceholderText("Sormak istediğiniz soruyu buraya yazınız...")
        layout.addWidget(self.qa_input)
        self.qa_send_btn = QPushButton("Gönder", widget)
        layout.addWidget(self.qa_send_btn)
        self.qa_send_btn.clicked.connect(self.send_qa_message)
        self.qa_output = QPlainTextEdit(widget)
        self.qa_output.setReadOnly(True)
        layout.addWidget(self.qa_output)

    # --- Gemini Mesaj Fonksiyonları ---
    def send_program_message(self):
        user_message = self.program_input.toPlainText().strip()
        if not user_message:
            QMessageBox.warning(self, "Uyarı", "Lütfen bir mesaj giriniz.")
            return
        base_prompt = (
            "Lütfen aşağıdaki kurallara kesinlikle uyularak, kullanıcının istediği program takvimini hazırlayın:\n\n"
            "Format:\n"
            "{\n"
            '  "program": {\n'
            '      "günler": [\n'
            "          {\n"
            '             "tarih": "YYYY-MM-DD",\n'
            '             "etkinlikler": [\n'
            '                  {"saat": "HH:MM", "başlık": "Etkinlik Başlığı", "açıklama": "Etkinlik Açıklaması"}\n'
            "             ]\n"
            "          },\n"
            "          ...\n"
            "      ]\n"
            "  },\n"
            '  "yorum": "Program oluşturulurken dikkate alınan önemli noktalar veya özet."\n'
            "}\n\n"
            "Lütfen yanıtınızı yalnızca geçerli JSON formatında ve markdown biçimlendirme olmadan veriniz. Ekstra açıklama veya yorum eklemeyiniz.\n"
        )
        prompt = base_prompt + "\nKullanıcının eklemek istediği detay: " + user_message
        self.program_output.setPlainText("İşleniyor...")
        self.program_worker = GeminiWorker(prompt)
        self.program_worker.finished.connect(self.handle_program_response)
        self.program_worker.start()

    def handle_program_response(self, response):
        response = clean_json_response(response)
        try:
            data = json.loads(response)
        except Exception:
            data = None
        if data and "program" in data:
            program_data = data["program"]
            # "yorum" dışındaki verilerden etkinlikler ekleniyor.
            for day in program_data.get("günler", []):
                tarih = day.get("tarih", "")
                for et in day.get("etkinlikler", []):
                    new_event = {
                        "id": str(QtCore.QDateTime.currentMSecsSinceEpoch()),
                        "title": et.get("başlık", "Yeni Etkinlik"),
                        "description": et.get("açıklama", ""),
                        "datetime": tarih + " " + et.get("saat", "00:00")
                    }
                    self.events.append(new_event)
            save_events(self.events)
            self.last_program_data = data  # Son yanıtı sakla
            self.update_program_output()    # Checkbox durumuna göre çıktı güncelle
        else:
            self.program_output.setPlainText("Alınan yanıt geçerli JSON formatında değil:\n" + response)
        self.program_input.clear()
        self.refresh_events_table()

    def update_program_output(self):
        if self.last_program_data is None:
            return
        comment = self.last_program_data.get("yorum", "")
        if self.program_only_comment_checkbox.isChecked():
            output_text = comment if comment else "Yorum bulunamadı."
        else:
            output_text = "Program Oluşturuldu.\nYorum: " + comment + "\n\nJSON:\n" + json.dumps(self.last_program_data, indent=2, ensure_ascii=False)
        self.program_output.setPlainText(output_text)

    def send_list_message(self):
        user_message = self.list_input.toPlainText().strip()
        if not user_message:
            QMessageBox.warning(self, "Uyarı", "Lütfen bir mesaj giriniz.")
            return
        base_prompt = (
            "Lütfen aşağıdaki kurallara kesinlikle uyularak, kullanıcının istediği görev listesini oluşturun.\n\n"
            "Format:\n"
            "{\n"
            '  "gorev_listesi": [\n'
            '      {"id": "benzersiz_id (örn: milisaniye timestamp, isteğe bağlı)", "title": "Görev Başlığı", "description": "Görev Açıklaması", "due_date": "YYYY-MM-DD", "completed": false},\n'
            "      ...\n"
            "  ],\n"
            '  "yorum": "Görev listesi oluşturulurken dikkate alınan önemli noktalar veya özet."\n'
            "}\n\n"
            "Lütfen yanıtınızı yalnızca geçerli JSON formatında ve markdown biçimlendirme olmadan veriniz. Ekstra açıklama veya yorum eklemeyiniz."
        )
        prompt = base_prompt + "\nKullanıcının eklemek istediği detay: " + user_message
        self.list_output.setPlainText("İşleniyor...")
        self.list_worker = GeminiWorker(prompt)
        self.list_worker.finished.connect(self.handle_list_response)
        self.list_worker.start()

    def handle_list_response(self, response):
        response = clean_json_response(response)
        try:
            data = json.loads(response)
        except Exception:
            data = None
        # Beklenen yanıt, "gorev_listesi" ve "yorum" bilgilerini içeren bir dict olmalıdır.
        if data and isinstance(data, dict) and "gorev_listesi" in data:
            new_tasks = data["gorev_listesi"]
            # Mevcut görevler silinmeden, yeni görevler ekleniyor.
            for item in new_tasks:
                if "id" not in item:
                    item["id"] = str(QtCore.QDateTime.currentMSecsSinceEpoch())
                if "completed" not in item:
                    item["completed"] = False
                self.tasks.append(item)
            save_tasks(self.tasks)
            self.last_task_list_data = data  # Son yanıtı sakla
            self.update_list_output()         # Checkbox durumuna göre çıktı güncelle
        else:
            self.list_output.setPlainText("Alınan yanıt geçerli JSON formatında değil:\n" + response)
        self.list_input.clear()
        self.refresh_tasks_table()

    def update_list_output(self):
        if self.last_task_list_data is None:
            return
        comment = self.last_task_list_data.get("yorum", "")
        if self.list_only_comment_checkbox.isChecked():
            output_text = comment if comment else "Yorum bulunamadı."
        else:
            output_text = "Görev Listesi Oluşturuldu.\nYorum: " + comment + "\n\nJSON:\n" + json.dumps(self.last_task_list_data, indent=2, ensure_ascii=False)
        self.list_output.setPlainText(output_text)

    def send_qa_message(self):
        user_message = self.qa_input.toPlainText().strip()
        if not user_message:
            QMessageBox.warning(self, "Uyarı", "Lütfen bir soru giriniz.")
            return
        # Mevcut program (etkinlikler) ve görev listesi (tasks) verileri modele ekleniyor.
        current_events = json.dumps(self.events, indent=2, ensure_ascii=False)
        current_tasks = json.dumps(self.tasks, indent=2, ensure_ascii=False)
        base_prompt = (
            "Aşağıdaki mevcut program takvimi ve görev listesi verilerine dayanarak, sorunuza cevap verin:\n\n"
            "Program Takvimi:\n" + current_events + "\n\nGörev Listesi:\n" + current_tasks + "\n\nSorunuz: "
        )
        prompt = base_prompt + user_message
        self.qa_output.setPlainText("İşleniyor...")
        self.qa_worker = GeminiWorker(prompt)
        self.qa_worker.finished.connect(self.handle_qa_response)
        self.qa_worker.start()

    def handle_qa_response(self, response):
        self.qa_output.setPlainText(response)
        self.qa_input.clear()

# ---------------------------
# UYGULAMAYI BAŞLAT
# ---------------------------
def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
