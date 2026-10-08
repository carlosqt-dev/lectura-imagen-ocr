import json
from pathlib import Path

from PySide6.QtWidgets import QApplication, QFileDialog, QLabel, QPushButton, QVBoxLayout, QWidget

from processing import ImageProcessor, ProcessingError


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Lector de resultados")
        self.resize(540, 220)
        self.paths: list[Path | None] = [None, None]
        self.processor = ImageProcessor()
        layout = QVBoxLayout(self)
        self.labels = [QLabel("Falta captura 1"), QLabel("Falta captura 2")]
        for i in range(2):
            button = QPushButton(f"Cargar captura {i + 1}")
            button.clicked.connect(lambda checked=False, idx=i: self.load(idx))
            layout.addWidget(button)
            layout.addWidget(self.labels[i])
        self.status = QLabel("Seleccione las dos vistas de la misma tabla.")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

    def load(self, index: int):
        selected, _ = QFileDialog.getOpenFileName(self, "Seleccionar captura", "", "Imágenes (*.png *.jpg *.jpeg *.bmp *.tif *.tiff)")
        if not selected:
            return
        self.paths[index] = Path(selected)
        self.labels[index].setText(selected)
        if not all(self.paths):
            self.status.setText(f"Falta captura {2 if index == 0 else 1}.")
            return
        self.status.setText("Procesando capturas...")
        QApplication.processEvents()
        try:
            result = self.processor.process(self.paths[0], self.paths[1])
        except ProcessingError as exc:
            self.status.setText(f"Error: {exc}")
            return
        print(json.dumps(result.como_dict(), ensure_ascii=False, indent=2), flush=True)
        self.status.setText("Resultado mostrado en la consola. " +
                            (f"{len(result.campos_pendientes)} campos pendientes." if result.campos_pendientes else "Lectura completa."))
