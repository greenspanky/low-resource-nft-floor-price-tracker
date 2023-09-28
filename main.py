import sys
import asyncio
import httpx
import cProfile
import pstats
from PyQt5.QtCore import Qt, QObject, pyqtSignal, QTimer, QThread
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QWidget,
    QTextEdit, QPushButton, QTableWidget, QTableWidgetItem
)

class FloorPriceWorker(QObject):
    result_signal = pyqtSignal(str, str)

    def __init__(self):
        super().__init__()

    async def fetch_floor_price(self, collection_name):
        url = f"https://api.opensea.io/api/v1/collection/{collection_name}"
        headers = {
            "accept": "application/json",
            "X-API-KEY": ""  # Add your API key here
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, headers=headers)
                data = response.json()

                collection = data.get("collection")
                if collection:
                    floor_price = collection.get("stats", {}).get("floor_price", 0)
                    return collection_name, f"{floor_price} ETH"
                else:
                    return collection_name, None
        except Exception as e:
            return collection_name, None

class FetchThread(QThread):
    fetch_completed = pyqtSignal(str, str)

    def __init__(self, worker, collection_name):
        super().__init__()
        self.worker = worker
        self.collection_name = collection_name

    def run(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(self.worker.fetch_floor_price(self.collection_name))
        loop.close()
        self.fetch_completed.emit(result[0], result[1])

class FloorPriceApp(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Floor Price App")
        self.setWindowFlags(Qt.WindowStaysOnTopHint)

        self.layout = QVBoxLayout()

        self.urls_textbox = QTextEdit()
        self.urls_textbox.setFixedHeight(30)
        self.urls_textbox.setPlaceholderText("Enter Collection Name")
        self.layout.addWidget(self.urls_textbox)

        self.add_button = QPushButton("Add Collection")
        self.add_button.clicked.connect(self.on_add_collection)
        self.layout.addWidget(self.add_button)

        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Collection Name", "Floor Price", "Actions"])
        self.layout.addWidget(self.table)

        central_widget = QWidget(self)
        central_widget.setLayout(self.layout)
        self.setCentralWidget(central_widget)

        self.worker = FloorPriceWorker()

        self.fetch_threads = []

        self.update_timer = QTimer(self)
        self.update_timer.timeout.connect(self.update_batch)
        self.batch_size = 2
        self.current_batch = 0
        self.update_timer.start(2000)

        self.load_urls()

    def update_batch(self):
        if self.urls_to_fetch:
            start = self.current_batch * self.batch_size
            end = (self.current_batch + 1) * self.batch_size
            urls_batch = self.urls_to_fetch[start:end]

            for url in urls_batch:
                fetch_thread = FetchThread(self.worker, url)
                fetch_thread.fetch_completed.connect(self.update_table)
                self.fetch_threads.append(fetch_thread)
                fetch_thread.start()

            self.current_batch = (self.current_batch + 1) % ((len(self.urls_to_fetch) + self.batch_size - 1) // self.batch_size)

    def on_add_collection(self):
        collection_name = self.urls_textbox.toPlainText().strip()
        if collection_name:
            self.urls_textbox.clear()
            self.urls_to_fetch.append(collection_name)
            self.save_urls()

    def update_table(self, collection_name, floor_price):
        row_count = self.table.rowCount()

        for row in range(row_count):
            item = self.table.item(row, 0)
            if item and item.text() == collection_name:
                current_floor_price_item = self.table.item(row, 1)
                if floor_price is not None and floor_price != "":
                    if current_floor_price_item is not None:
                        current_floor_price = current_floor_price_item.text()
                        if current_floor_price:
                            current_price = float(current_floor_price.split()[0])
                            new_price = float(floor_price.split()[0])
                            if new_price > current_price:
                                floor_price += " ↑"
                            elif new_price < current_price:
                                floor_price += " ↓"
                            else:
                                floor_price = current_floor_price
                    self.table.setItem(row, 1, QTableWidgetItem(floor_price))
                    self.save_urls()
                return
        self.add_new_row(collection_name, floor_price)


    def add_new_row(self, collection_name, floor_price):
        row_count = self.table.rowCount()
        self.table.insertRow(row_count)

        item_collection_name = QTableWidgetItem(collection_name)
        item_floor_price = QTableWidgetItem(floor_price if floor_price is not None else "Error fetching data")

        remove_button = QPushButton("Close")
        remove_button.clicked.connect(self.remove_row)

        self.table.setItem(row_count, 0, item_collection_name)
        self.table.setItem(row_count, 1, item_floor_price)
        self.table.setCellWidget(row_count, 2, remove_button)

    def remove_row(self):
        button = self.sender()
        if button:
            index = self.table.indexAt(button.pos())
            if index.isValid():
                collection_name_item = self.table.item(index.row(), 0)
                if collection_name_item:
                    collection_name = collection_name_item.text()
                    self.urls_to_fetch.remove(collection_name)
                    self.table.removeRow(index.row())
                    self.save_urls()

    def closeEvent(self, event):
        self.save_urls()

    def load_urls(self):
        try:
            with open("urls.txt", "r") as file:
                self.urls_to_fetch = [line.strip() for line in file.readlines()]
        except FileNotFoundError:
            self.urls_to_fetch = []

    def save_urls(self):
        with open("urls.txt", "w") as file:
            for url in self.urls_to_fetch:
                file.write(url + "\n")

if __name__ == "__main__":
    # Run the app with cProfile
    pr = cProfile.Profile()
    pr.enable()

    app = QApplication(sys.argv)
    window = FloorPriceApp()
    window.show()

    sys.exit(app.exec_())

    pr.disable()
    stats = pstats.Stats(pr)
    stats.sort_stats('cumulative')
    stats.print_stats()
