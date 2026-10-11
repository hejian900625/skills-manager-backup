import sys
import datetime
from PySide6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QPushButton, QWidget, QLabel, QComboBox, QHBoxLayout, QMessageBox

class DateRangeSelector(QMainWindow):
    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        self.start_date = None
        self.end_date = None

        # Set window size to be larger
        self.resize(700, 300)

        self.setWindowTitle('请选择数据获取的日期范围')
        self.setGeometry(400, 400, 500, 300)  # Set window size

        # 年份范围：从 2003 到当前年份（起止可改这两处常量）
        start_year = 2003
        current_year = datetime.datetime.now().year
        self.years = [str(y) for y in range(start_year, current_year + 1)]
        self.months = [f"{month:02}" for month in range(1, 13)]
        
        # Combo boxes
        self.startYearComboBox = QComboBox(self)
        self.startMonthComboBox = QComboBox(self)
        self.startDayComboBox = QComboBox(self)

        self.endYearComboBox = QComboBox(self)
        self.endMonthComboBox = QComboBox(self)
        self.endDayComboBox = QComboBox(self)

        self.startYearComboBox.addItems(self.years)
        self.startMonthComboBox.addItems(self.months)

        self.endYearComboBox.addItems(self.years)
        self.endMonthComboBox.addItems(self.months)

        # Trigger the update once during initialization
        self.update_days(self.startYearComboBox, self.startMonthComboBox, self.startDayComboBox)
        self.update_days(self.endYearComboBox, self.endMonthComboBox, self.endDayComboBox)

        # Set default end date as today
        today = datetime.datetime.today()
        two_weeks_ago = today - datetime.timedelta(weeks=2)

        # Start date default values (two weeks ago)
        self.startYearComboBox.setCurrentText(str(two_weeks_ago.year))
        self.startMonthComboBox.setCurrentText(f"{two_weeks_ago.month:02}")
        self.update_days(self.startYearComboBox, self.startMonthComboBox, self.startDayComboBox)  # populates the days
        self.startDayComboBox.setCurrentText(f"{two_weeks_ago.day:02}")

        # End date default values (today)
        self.endYearComboBox.setCurrentText(str(today.year))
        self.endMonthComboBox.setCurrentText(f"{today.month:02}")
        self.update_days(self.endYearComboBox, self.endMonthComboBox, self.endDayComboBox)  # populates the days
        self.endDayComboBox.setCurrentText(f"{today.day:02}")

        # Connect signals
        self.startYearComboBox.currentTextChanged.connect(lambda: self.update_days(self.startYearComboBox, self.startMonthComboBox, self.startDayComboBox))
        self.startMonthComboBox.currentTextChanged.connect(lambda: self.update_days(self.startYearComboBox, self.startMonthComboBox, self.startDayComboBox))

        self.endYearComboBox.currentTextChanged.connect(lambda: self.update_days(self.endYearComboBox, self.endMonthComboBox, self.endDayComboBox))
        self.endMonthComboBox.currentTextChanged.connect(lambda: self.update_days(self.endYearComboBox, self.endMonthComboBox, self.endDayComboBox))

        self.resultLabel = QLabel("注意：默认开始日期为两周前，默认结束日期为今天", self)
        self.submitButton = QPushButton('确定', self)
        self.submitButton.clicked.connect(self.pick_dates)

        layout = QVBoxLayout()
        layout.addWidget(QLabel("开始日期（年-月-日）:", self))

        start_date_layout = QHBoxLayout()
        start_date_layout.addWidget(self.startYearComboBox)
        start_date_layout.addWidget(self.startMonthComboBox)
        start_date_layout.addWidget(self.startDayComboBox)

        layout.addLayout(start_date_layout)
        layout.addWidget(QLabel("结束日期（年-月-日）:", self))

        end_date_layout = QHBoxLayout()
        end_date_layout.addWidget(self.endYearComboBox)
        end_date_layout.addWidget(self.endMonthComboBox)
        end_date_layout.addWidget(self.endDayComboBox)

        layout.addLayout(end_date_layout)
        layout.addWidget(self.submitButton)
        layout.addWidget(self.resultLabel)

        central_widget = QWidget()
        central_widget.setLayout(layout)

        self.setCentralWidget(central_widget)

    def update_days(self, year_combobox, month_combobox, day_combobox):
        year = int(year_combobox.currentText())
        month = int(month_combobox.currentText())

        if month in [1, 3, 5, 7, 8, 10, 12]:
            days = 31
        elif month in [4, 6, 9, 11]:
            days = 30
        else:
            # February
            if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0):  # leap year
                days = 29
            else:
                days = 28

        day_combobox.clear()
        day_combobox.addItems([f"{day:02}" for day in range(1, days + 1)])

    def pick_dates(self):
        start_date = datetime.date(int(self.startYearComboBox.currentText()), int(self.startMonthComboBox.currentText()), int(self.startDayComboBox.currentText()))
        end_date = datetime.date(int(self.endYearComboBox.currentText()), int(self.endMonthComboBox.currentText()), int(self.endDayComboBox.currentText()))

        if end_date < start_date:
            self.resultLabel.setText("错误：结束日期不能早于开始日期")
        else:
            self.start_date = start_date.strftime("%Y-%m-%d")
            self.end_date = end_date.strftime("%Y-%m-%d")
            self.resultLabel.setText(f"已选择的日期范围: {self.start_date} 到 {self.end_date}")
            self.close()
            # Return the selected start and end dates as formatted strings
            return self.start_date, self.end_date

def date_select():
    app = QApplication(sys.argv)
    # app = QApplication(sys.argv)
    try:
        # select date range
        window = DateRangeSelector()
        window.show()
        app.exec()
        start_date, end_date = window.pick_dates()
        msg_box = QMessageBox()
        msg_box.setWindowTitle("日期选择结果")
        msg_box.setText(f"开始日期为{start_date}\n结束日期为{end_date}")
        msg_box.exec()
        print(f'chosen date range: {start_date} - {end_date}')
        return start_date, end_date
        
    except Exception as e:
        print(str(e))
        msg_box = QMessageBox()
        msg_box.setWindowTitle("错误")
        msg_box.setText("日期有误!")
        msg_box.exec()

if __name__ == "__main__":
    date_select()
