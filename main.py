import struct
from pathlib import Path
from tabulate import tabulate
import plistlib
import sys
import os

from PyQt5.QtGui import QDragEnterEvent, QDropEvent
from PyQt5.QtWidgets import (QApplication, QWidget, QHBoxLayout, QVBoxLayout, QLabel,
                             QLineEdit, QPushButton, QTableWidget, QTableWidgetItem,
                             QHeaderView, QFileDialog, QMessageBox, QStackedWidget,
                             QListWidget, QListWidgetItem)
from PyQt5.QtGui import QFont
from PyQt5.QtCore import Qt



if getattr(sys, 'frozen', False):
    # Если приложение запущено как executable
    application_path = sys._MEIPASS
else:
    application_path = os.path.dirname(os.path.abspath(__file__))

# Класс для обработки файлов
class Chunk:
    def __init__(self, header, data):
        self.header = header
        self.data = data

        self.type = self.header[0:4].decode()[::-1]

        #        --?-- ---??????-- ---OID??---         type/subtype???       always the same--  ---size of chunk data--
        # MSeq   02 00 03 00 00 00 00 00 00 00    ff ff ff ff ff ff ff ff    02 00 00 00 01 00  2c 01 00 00 00 00 00 00 (300 bytes)

        self.m1 = int.from_bytes(self.header[4:6], "little", signed=False)  # 02 00 above, think this is 16 bit int
        self.m2 = int.from_bytes(self.header[6:10], "little", signed=False)
        self.m3 = int.from_bytes(self.header[10:14], "little",
                                 signed=False)  # there is correlation here in environment objs
        self.m4 = int.from_bytes(self.header[14:18], "little", signed=False)  # sometimes a number, sometimes f
        self.m5 = int.from_bytes(self.header[18:22], "little", signed=False)  # mostly ff ff ff ff sometimes ff ff ff 7f

        chunkSizeBytes = self.header[28:36]  # pull the size (64 bit unsigned int)
        chunkSize = int.from_bytes(chunkSizeBytes, "little", signed=False)  # convert to int

    def __str__(self):
        return ("its shit")

    def __repr__(self):
        return self.header[0:4].decode()[::-1]

class LogicxFileHandler:
    def __init__(self):
        self.chunks = []
    def readFile(self, fileName, chunkDestination):
        # Проверяем, является ли fileName директорией
        if os.path.isdir(fileName):
            # Формируем путь к файлу ProjectData
            project_data_path = os.path.join(fileName, "Alternatives", "000", "ProjectData")
            fileName = project_data_path

        with open(fileName, mode='rb') as file:
            fc = bytearray(file.read())  # read entire file into byte array
            filesize = os.path.getsize(fileName)  # get size in bytes from OS

            fp = 0x18  # move the file pointer 24 bytes, skipping over the entire header
            found_count = 0

            while (fp < filesize):
                chunkStart = fp
                chunkHeader = fc[fp:fp + 36]  # byte array, whole chunk header
                chunkSizeBytes = chunkHeader[28:36]  # pull the size (64 bit unsigned int)
                chunkSize = int.from_bytes(chunkSizeBytes, "little", signed=False)  # convert to int
                fp += 36  # fp now points at the frst byte of the chunk's data
                chunkData = fc[fp:fp + chunkSize]  # pull the chunk's data
                fp += chunkSize  # skip over all the chunk's data, should be at 1st byte of next chunk descriptor now
                nc = Chunk(chunkHeader, chunkData)
                chunkDestination.append(nc)
                found_count += 1


    def readLayers(self, chunk, layersDestination, dumpDetails=True):
        first16 = chunk.data[0:16]
        numItems = (first16[1] - (first16[1]) / 16) / 2
        if (dumpDetails):
            print("First 16 bytes: %s" % first16.hex(sep=' '))
            print("%d %d ---- %d layers predicted: (byte2 - byte2 / 16) / 2" % (first16[0], first16[1], numItems + 1))

        fp = 0x10  # start of first short name
        layerCount = 0
        lines = []

        while layerCount < numItems:
            shortNameBytes = chunk.data[fp + 1:fp + 16]
            shortName = shortNameBytes.decode()
            shortName = shortName.split("\x00")[0]
            fp += 16
            longNameLength = int.from_bytes(chunk.data[fp:fp + 2], "little", signed=False)
            fp += 2
            longNameBytes = chunk.data[fp:fp + longNameLength]
            longName = longNameBytes.decode()
            fp += longNameLength
            if longNameLength % 2 == 0:
                fp += 16
            else:
                fp += 17

            lines.append([layerCount, shortName, longName, longNameLength])
            layersDestination.append(longName)
            layerCount += 1

        if (dumpDetails):
            print(tabulate(lines, headers=["index", "shortname", "longname", "longname_length"], tablefmt="pretty",
                       stralign="left"))

    def getObjType(self, b):
        switcher = {
            0x18: "ornament",
            0x13: "monitor",
            0x04: "channel split",
            0x06: "fader/button",
            0x07: "keyboard",
            0x0F: "tranfsormer",
            0x0D: "physical in",
            0x0E: "sequencer in",
            0x00: "midi inst",
            0x11: "channel strip",
            0x12: "multi inst",
            0x05: "mapped inst",
            0x09: "MIDI Click"
        }
        return switcher.get(b, f'unknown (0x{b:02X})')

    def extract_objID(self, chunk):
        objID_start = 0x0A  # Начальное смещение objID
        objID_length = 4  # Длина objID
        objID_bytes = chunk.header[objID_start:objID_start + objID_length]  # Извлекаем байты
        objID = int.from_bytes(objID_bytes, "little", signed=False)
        return objID

    def process_aucu_chunk(self, chunk, count = 0):
        a = []
        t = []
        counter = 1
        num = ''
        if chunk.type == 'AuCU':

            # objID_start = 0x04  # Начальное смещение objID
            objID_start = 16  # Начальное смещение objID
            objID_length = 4  # Длина objID
            objID_bytes = chunk.header[objID_start:objID_start + objID_length]  # Извлекаем байты
            objID = int.from_bytes(objID_bytes, "little", signed=False)
            print("Data (hex):", chunk.data)
            serum_offset = 0x78

            # Извлекаем длину имени из 2 байт перед началом имени
            longNameLength = int.from_bytes(chunk.data[0x76:serum_offset], "little", signed=False)
            # print(f"Длина имени: {longNameLength}")
            longNameBytes = chunk.data[serum_offset:serum_offset + longNameLength]
            # print(f"Байты имени: {longNameBytes}")
            # Обрезаем до первого нулевого байта
            try:
                shortName = longNameBytes.split(b'\x00')[0].decode()
            except:
                shortName = ''


            # Находим смещение для "Untitled.aupreset"
            filename_offset = 0xe  # Примерное начальное предположение

            # Извлекаем длину имени файла из 2 байт перед началом имени
            filename_length = int.from_bytes(chunk.data[filename_offset - 4:filename_offset], "little", signed=False)
            # print(f"Длина имени файла: {filename_length}")

            # Извлекаем байты имени файла
            filename_bytes = chunk.data[filename_offset:filename_offset + filename_length]


            # Обрезаем до первого нулевого байта
            try:
                presets = filename_bytes.split(b'\x00')[0].decode()
            except:
                presets = ''
            if objID == 262144:
                count += 1
                num = f'Track{count}'
                print(num)

            # Добавляем запись в a ТОЛЬКО если все значения не пустые
            if shortName and presets and presets:
                partial_entry = [num, objID, shortName, presets, None, None, None, None, None, None, None]
                a.append(partial_entry)
        # print(a)
        return a

    def process_envi_chunk(self, chunk, counter):
        t = []

        objID_start = 10  # Начальное смещение objID
        objID_length = 4  # Длина objID
        objID_bytes = chunk.header[objID_start:objID_start + objID_length]  # Извлекаем байты
        objID = int.from_bytes(objID_bytes, "little", signed=False)
        posX = int.from_bytes(chunk.data[0x52:0x54], "little", signed=False)
        posY = int.from_bytes(chunk.data[0x54:0x56], "little", signed=False)
        width = int.from_bytes(chunk.data[0x56:0x58], "little", signed=False)
        height = int.from_bytes(chunk.data[0x58:0x5A], "little", signed=False)

        layer = int.from_bytes(chunk.data[0x5A:0x5E], "little", signed=False)
        objType = self.getObjType(chunk.data[0x51])

        longNameLength = int.from_bytes(chunk.data[0x9E:0xA0], "little", signed=False)
        longNameBytes = chunk.data[0xA0:0xA0 + longNameLength]
        longName = longNameBytes.decode()

        oTypeBytes = chunk.data[0x70:0x72]

        # Добавляем запись в t
        t.append([objID, longName, objType, f'{posX},{posY}', f'{width}x{height}',
                  oTypeBytes.hex(sep=' '), chunk.data[0x9B]])
        return t

    def process_logicx_file(self, fileName):
        self.chunks = []
        self.readFile(fileName, self.chunks)
        print(f"ProjectData: {Path(fileName).name}\t{len(self.chunks)} chunks")

        a = []  # Список для плагинов и пресетов
        t = []  # Список для окружения
        count = 0
        counter = 1

        # Фильтрация и обработка chunks
        aucu_chunks = [c for c in self.chunks if c.type == 'AuCU']
        envi_chunks = [c for c in self.chunks if c.type == 'Envi']

        print(f"Found {len(aucu_chunks)} AuCU chunks")
        print(f"Found {len(envi_chunks)} Envi chunks")

        # Обработка AuCU chunks
        for chunk in aucu_chunks:
            result = self.process_aucu_chunk(chunk, count)
            a.extend(result)
            count += 1

        # Обработка Envi chunks
        for chunk in envi_chunks:
            result = self.process_envi_chunk(chunk, counter)
            t.extend(result)
            counter += 1

        print(f"Extracted {len(a)} plugins/presets")
        print(f"Extracted {len(t)} environment items")

        return a, t

# Класс для GUI
class LogicxGUI(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Logicx File Analyzer")
        self.handler = LogicxFileHandler()
        self.setAcceptDrops(True)
        self.resize(1600, 900)  # Увеличиваем размер окна

        # Создаем главный горизонтальный layout
        main_layout = QHBoxLayout()

        # Создаем боковое меню
        self.menu_list = QListWidget()
        self.menu_list.addItems([
            "Plugins & Presets",
            "Track Names",
            "Audio Files",
            "Project Info"
        ])
        self.menu_list.currentRowChanged.connect(self.change_page)

        # Создаем стек виджетов для основного контента
        self.stacked_widget = QStackedWidget()

        # Создаем виджеты для каждой страницы
        self.plugins_presets_table = QTableWidget()
        self.names_table = QTableWidget()
        self.audio_files_table = QTableWidget()
        self.project_info_widget = self.create_project_info_widget()

        # Добавляем виджеты в стек
        self.stacked_widget.addWidget(self.plugins_presets_table)
        self.stacked_widget.addWidget(self.names_table)
        self.stacked_widget.addWidget(self.audio_files_table)
        self.stacked_widget.addWidget(self.project_info_widget)

        # Создаем верхнюю панель с открытием файла
        top_panel = self.create_top_panel()

        # Создаем вертикальный layout для центральной части
        center_layout = QVBoxLayout()
        center_layout.addWidget(top_panel)
        center_layout.addWidget(self.stacked_widget)

        # Добавляем виджеты в главный layout
        main_layout.addWidget(self.menu_list, 1)
        main_layout.addLayout(center_layout, 5)

        # Устанавливаем главный layout
        self.setLayout(main_layout)

    def create_top_panel(self):
        # Создаем верхнюю панель с открытием файла
        top_panel = QWidget()
        hbox = QHBoxLayout()

        file_label = QLabel("Select or Drag and Drop Logicx file:")
        self.file_path = QLineEdit()
        open_button = QPushButton("Open")
        open_button.clicked.connect(self.open_file)

        hbox.addWidget(file_label)
        hbox.addWidget(self.file_path)
        hbox.addWidget(open_button)

        top_panel.setLayout(hbox)
        return top_panel

    def create_project_info_widget(self):
        # Создаем виджет с информацией о проекте
        project_info_widget = QWidget()
        project_info_layout = QVBoxLayout()

        font = QFont("Arial", 15)

        # Создаем метки заранее
        self.bpm_label = QLabel("BPM: N/A")
        self.sample_rate_label = QLabel("Sample Rate: N/A")
        self.key_label = QLabel("Key: N/A")
        self.signature_label = QLabel("Time Signature: N/A")
        self.tracks_label = QLabel("Total Tracks: N/A")

        labels = [
            "Project Info:",
            self.bpm_label,
            self.sample_rate_label,
            self.key_label,
            self.signature_label,
            self.tracks_label
        ]

        for label in labels:
            if isinstance(label, str):
                qlabel = QLabel(label)
                qlabel.setFont(font)
                project_info_layout.addWidget(qlabel)
            else:
                label.setFont(font)
                project_info_layout.addWidget(label)

        project_info_widget.setLayout(project_info_layout)
        return project_info_widget

    def change_page(self, index):
        # Переключение между страницами
        self.stacked_widget.setCurrentIndex(index)

    def dragEnterEvent(self, event: QDragEnterEvent):
        # Проверяем, что перетаскиваемый объект - это файл или папка
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        # Получаем путь к перетащенному файлу/папке
        for url in event.mimeData().urls():
            file_path = url.toLocalFile()
            self.process_file(file_path)
            break  # Обрабатываем только первый перетащенный файл

    def parse_audio_files(self, logicx_path):
        metadata_path = os.path.join(logicx_path, "Alternatives", "000", "MetaData.plist")

        try:
            # Читаем plist файл
            with open(metadata_path, 'rb') as f:
                metadata = plistlib.load(f)

            # Извлекаем списки аудиофайлов
            audio_files = metadata.get('AudioFiles', [])
            unused_audio_files = metadata.get('UnusedAudioFiles', [])

            # Объединяем списки
            all_audio_files = audio_files + unused_audio_files

            # Настраиваем таблицу
            self.setup_table(self.audio_files_table,
                             [[
                                 "Used" if f in audio_files else "Unused",
                                 os.path.basename(f),
                                 os.path.join(os.path.dirname(logicx_path), f)
                             ] for f in all_audio_files],
                             headers=["Status", "Filename", "Full Path"])

            # Обновляем информацию о проекте
            bpm = metadata.get('BeatsPerMinute', 'N/A')
            sample_rate = metadata.get('SampleRate', 'N/A')
            key = metadata.get('SongKey', 'N/A')
            signature = f"{metadata.get('SongSignatureNumerator', 'N/A')}/{metadata.get('SongSignatureDenominator', 'N/A')}"

            # Получаем количество треков
            num_tracks = metadata.get('NumberOfTracks', 'N/A')

            # Обновляем метки в интерфейсе
            self.bpm_label.setText(f"BPM: {bpm}")
            self.sample_rate_label.setText(f"Sample Rate: {sample_rate}")
            self.key_label.setText(f"Key: {key}")
            self.signature_label.setText(f"Time Signature: {signature}")
            self.tracks_label.setText(f"Total Tracks: {num_tracks}")

            # Дополнительная отладочная информация
            print(f"Project Metadata:")
            print(f"BPM: {bpm}")
            print(f"Sample Rate: {sample_rate}")
            print(f"Key: {key}")
            print(f"Time Signature: {signature}")
            print(f"Total Tracks: {num_tracks}")
            print(f"Total Audio Files: {len(all_audio_files)}")
            print(f"Used Audio Files: {len(audio_files)}")
            print(f"Unused Audio Files: {len(unused_audio_files)}")

        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to parse MetaData.plist: {str(e)}")

    def process_file(self, file_path):
        file_path = file_path.rstrip('/')
        # Существующий код обработки файла

        # Добавляем вызов парсинга аудиофайлов
        if os.path.isdir(file_path) and (file_path.endswith('.logicx') or '.logicx/' in file_path):
            project_data_path = os.path.join(file_path, "Alternatives", "000", "ProjectData")

            if os.path.exists(project_data_path):
                # Существующий код обработки
                a, t = self.handler.process_logicx_file(project_data_path)

                # Настройка существующих таблиц
                self.setup_table(self.plugins_presets_table, a,
                                 headers=["Tracks", "id??", 'Plugins', "Presets",  "type",
                                          "size", "0x70-0x71", "test"])
                self.setup_table(self.names_table, t,
                                 headers=["id?? ", "long name", "on layer", "type", "pos", "size", "0x70-0x71",
                                          "test"])

                # Парсинг аудиофайлов
                self.parse_audio_files(file_path)

                # Отображаем таблицы
                self.plugins_presets_table.resizeColumnsToContents()
                self.names_table.resizeColumnsToContents()
                self.audio_files_table.resizeColumnsToContents()

                # Устанавливаем путь в поле ввода
                self.file_path.setText(project_data_path)
            else:
                QMessageBox.warning(self, "Error", "ProjectData file not found")
        else:
            QMessageBox.warning(self, "Error", "Please select a .logicx project folder")

    def open_file(self):
        file_name, _ = QFileDialog.getOpenFileName(self, "Select Logicx file", "", "Logicx Folders (*.logicx)")
        if file_name:
            self.process_file(file_name)


    def setup_table(self, table, data, headers):
        table.clear()
        table.setColumnCount(len(headers))
        table.setHorizontalHeaderLabels(headers)

        # Растягиваем заголовки по ширине окна
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

        # Делаем заголовки жирными
        font = table.horizontalHeader().font()
        font.setBold(True)
        table.horizontalHeader().setFont(font)

        # Устанавливаем количество строк
        table.setRowCount(len(data))

        # Заполняем таблицу
        for row, row_data in enumerate(data):
            for col, value in enumerate(row_data):
                item = QTableWidgetItem(str(value))
                table.setItem(row, col, item)

        # Автоматическое изменение размера столбцов
        table.resizeColumnsToContents()

# Запускаем приложение
if __name__ == '__main__':
    app = QApplication(sys.argv)
    gui = LogicxGUI()
    gui.show()
    sys.exit(app.exec_())
