from PySide6.QtWidgets import QApplication


def create_app(argv: list[str]) -> QApplication:
    app = QApplication(argv)
    app.setApplicationName("ESO Build Manager")
    app.setOrganizationName("CubicSerenity")
    app.setApplicationVersion("1.0.0")
    app.setQuitOnLastWindowClosed(False)  # tray icon keeps the app alive when the window is hidden
    return app
