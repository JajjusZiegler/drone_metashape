from PySide2 import QtWidgets, QtCore
import csv
import os
import Metashape

# Global variable to hold our dialog instance
csvDialogInstance = None

class CSVProjectOpenerDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super(CSVProjectOpenerDialog, self).__init__(parent)
        self.setWindowTitle("Open Project from CSV")
        self.resize(600, 400)
        
        # CSV file selection widgets
        self.csvLineEdit = QtWidgets.QLineEdit(self)
        self.csvBrowseButton = QtWidgets.QPushButton("Browse CSV", self)
        csvLayout = QtWidgets.QHBoxLayout()
        csvLayout.addWidget(QtWidgets.QLabel("CSV File:"))
        csvLayout.addWidget(self.csvLineEdit)
        csvLayout.addWidget(self.csvBrowseButton)
        
        # List widget to display project entries (showing date and site)
        self.projectListWidget = QtWidgets.QListWidget(self)
        self.projectListWidget.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        
        # Action buttons
        self.openButton = QtWidgets.QPushButton("Open Project", self)
        self.returnButton = QtWidgets.QPushButton("Return to CSV", self)
        self.exitButton = QtWidgets.QPushButton("Exit", self)
        buttonLayout = QtWidgets.QHBoxLayout()
        buttonLayout.addWidget(self.openButton)
        buttonLayout.addWidget(self.returnButton)
        buttonLayout.addWidget(self.exitButton)
        
        # Main layout
        mainLayout = QtWidgets.QVBoxLayout()
        mainLayout.addLayout(csvLayout)
        mainLayout.addWidget(self.projectListWidget)
        mainLayout.addLayout(buttonLayout)
        self.setLayout(mainLayout)
        
        # Connections
        self.csvBrowseButton.clicked.connect(self.browseCSV)
        self.openButton.clicked.connect(self.openProject)
        self.returnButton.clicked.connect(self.openReflectanceDialog)
        self.exitButton.clicked.connect(self.reject)
        self.projectListWidget.itemDoubleClicked.connect(self.openProject)
        
        self.csvFilePath = ""
        self.csvData = None  # Will hold the original CSV data
    
    def browseCSV(self):
        fileName, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Select CSV File", "", "CSV Files (*.csv)")
        if fileName:
            self.csvFilePath = fileName
            self.csvLineEdit.setText(fileName)
            self.loadCSV()
    
    def loadCSV(self):
        if not self.csvFilePath or not os.path.exists(self.csvFilePath):
            QtWidgets.QMessageBox.warning(self, "Error", "CSV file not found!")
            return
        
        with open(self.csvFilePath, newline='', encoding='utf-8') as csvfile:
            reader = csv.reader(csvfile)
            rows = list(reader)
        
        if not rows:
            QtWidgets.QMessageBox.warning(self, "Error", "CSV file is empty!")
            return
        
        self.csvData = rows  # Save CSV data in memory
        self.populateListFromData()
    
    def populateListFromData(self):
        self.projectListWidget.clear()
        rows = self.csvData
        if not rows:
            return
        
        headers = rows[0]
        try:
            dateIndex = headers.index("date")
            siteIndex = headers.index("site")
            try:
                projectPathIndex = headers.index("project_path")
            except ValueError:
                projectPathIndex = headers.index("psx_file")
        except ValueError:
            QtWidgets.QMessageBox.warning(self, "Error", "CSV must contain 'date', 'site', and 'project_path' columns!")
            return
        
        for row in rows[1:]:
            if len(row) > projectPathIndex:
                date_val = row[dateIndex]
                site_val = row[siteIndex]
                projectPath = row[projectPathIndex]
                display_text = f"{date_val} - {site_val}"
                item = QtWidgets.QListWidgetItem(display_text)
                # Store full project path in the item data
                item.setData(QtCore.Qt.UserRole, projectPath)
                self.projectListWidget.addItem(item)
    
    def openProject(self):
        currentItem = self.projectListWidget.currentItem()
        if not currentItem:
            QtWidgets.QMessageBox.warning(self, "Error", "No project selected!")
            return
        
        projectPath = currentItem.data(QtCore.Qt.UserRole)
        project_path = r"{}".format(projectPath)
        if not os.path.exists(project_path):
            QtWidgets.QMessageBox.warning(self, "Error", "Project file not found:\n" + project_path)
            return

        
        # Check if the current project has unsaved changes
        doc = Metashape.app.document
        if doc.modified:
            ret = QtWidgets.QMessageBox.question(self, "Save Changes",
                                                 "The current project has unsaved changes. Do you want to save them?",
                                                 QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No | QtWidgets.QMessageBox.Cancel)
            if ret == QtWidgets.QMessageBox.Yes:
                doc.save()
            elif ret == QtWidgets.QMessageBox.Cancel:
                return  # Abort opening
        
        # Open the selected project
        Metashape.app.document.open(project_path)
    
    def openReflectanceDialog(self):
        # Open the ReflectanceUpdateDialog (if CSV data is loaded)
        if not self.csvData:
            QtWidgets.QMessageBox.warning(self, "Error", "No CSV data loaded!")
            return
        dlg = ReflectanceUpdateDialog(self.csvData, self.csvFilePath, self)
        dlg.exec_()
        # Reload CSV to refresh the list after updating
        self.loadCSV()

class ReflectanceUpdateDialog(QtWidgets.QDialog):
    def __init__(self, csvData, csvFilePath, parent=None):
        super(ReflectanceUpdateDialog, self).__init__(parent)
        self.setWindowTitle("Update Reflectance Panels Info")
        self.resize(400, 200)
        
        self.csvData = csvData
        self.csvFilePath = csvFilePath
        
        # Extract unique sites from CSV
        headers = self.csvData[0]
        try:
            siteIndex = headers.index("site")
        except ValueError:
            QtWidgets.QMessageBox.warning(self, "Error", "CSV does not contain a 'site' column!")
            self.reject()
            return
        
        sites = set()
        for row in self.csvData[1:]:
            if len(row) > siteIndex:
                sites.add(row[siteIndex])
        sites = sorted(list(sites))
        
        # Create dropdown for sites
        self.siteCombo = QtWidgets.QComboBox(self)
        self.siteCombo.addItems(sites)
        
        # Create checkbox for reflectance panels identified
        self.reflectanceCheckbox = QtWidgets.QCheckBox("Reflectance Panels identified!", self)
        
        # Buttons
        self.applyButton = QtWidgets.QPushButton("Apply", self)
        self.cancelButton = QtWidgets.QPushButton("Cancel", self)
        buttonLayout = QtWidgets.QHBoxLayout()
        buttonLayout.addWidget(self.applyButton)
        buttonLayout.addWidget(self.cancelButton)
        
        # Layout
        mainLayout = QtWidgets.QVBoxLayout()
        mainLayout.addWidget(QtWidgets.QLabel("Select Site:"))
        mainLayout.addWidget(self.siteCombo)
        mainLayout.addWidget(self.reflectanceCheckbox)
        mainLayout.addLayout(buttonLayout)
        self.setLayout(mainLayout)
        
        # Connections
        self.applyButton.clicked.connect(self.applyUpdate)
        self.cancelButton.clicked.connect(self.reject)
    
    def applyUpdate(self):
        selected_site = self.siteCombo.currentText()
        is_checked = self.reflectanceCheckbox.isChecked()
        
        # Define new column header name
        new_column_header = "ReflectancePanels"
        headers = self.csvData[0]
        if new_column_header not in headers:
            headers.append(new_column_header)
            # Append empty value for all existing rows
            for i in range(1, len(self.csvData)):
                self.csvData[i].append("")
        else:
            new_col_index = headers.index(new_column_header)
        
        # Find the index of the "site" column
        try:
            siteIndex = headers.index("site")
        except ValueError:
            QtWidgets.QMessageBox.warning(self, "Error", "CSV does not contain a 'site' column!")
            self.reject()
            return
        
        # Get the index of the new column
        new_col_index = headers.index(new_column_header)
        # For each row matching the selected site, update reflectance info
        for row in self.csvData[1:]:
            if len(row) > siteIndex and row[siteIndex] == selected_site:
                row[new_col_index] = "Yes" if is_checked else ""
        
        # Write the updated CSV data back to the original file
        try:
            with open(self.csvFilePath, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerows(self.csvData)
            QtWidgets.QMessageBox.information(self, "Success", "CSV updated successfully.")
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", "Failed to update CSV:\n" + str(e))
        
        self.accept()

def open_csv_project_opener():
    global csvDialogInstance
    if csvDialogInstance is None:
        app = QtWidgets.QApplication.instance()
        parent = app.activeWindow() if app else None
        csvDialogInstance = CSVProjectOpenerDialog(parent)
    csvDialogInstance.show()
    csvDialogInstance.raise_()

def resume_proc():
    global csvDialogInstance
    if csvDialogInstance:
        # Open the ReflectanceUpdateDialog via the main CSV dialog
        csvDialogInstance.openReflectanceDialog()
    else:
        open_csv_project_opener()

# Add the primary menu item to open the CSV Project Opener dialog
main_menu_label = "Scripts/Select Project from CSV"
Metashape.app.addMenuItem(main_menu_label, open_csv_project_opener)
print("To execute this script press {}".format(main_menu_label))

# Add a menu item to resume to CSV (with reflectance update) using remove/add pattern
resume_menu_label = "Scripts/Resume to CSV"
Metashape.app.removeMenuItem(resume_menu_label)
Metashape.app.addMenuItem(resume_menu_label, resume_proc)
print("To resume CSV selection press {}".format(resume_menu_label))
