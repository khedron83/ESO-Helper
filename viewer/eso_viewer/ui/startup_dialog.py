from PySide6.QtWidgets import QDialog, QInputDialog, QLabel, QLineEdit, QPushButton, QVBoxLayout

from eso_viewer.sync import config as sync_config


class StartupModeDialog(QDialog):
    """Asked only the very first time this app runs on a machine (no
    `sync/mode` saved yet) -- see the `if not self._settings.contains(
    'sync/mode'):` guard in MainWindow.__init__, before the first _reload().
    Every later launch just reuses whatever was picked (or whatever Settings
    changed it to since); popping this up on top of whatever's on screen
    every single launch was disruptive on zeus, where it can appear over the
    game mid-session. See settings_dialog.py and viewer/CLAUDE.md's "Sync"
    section for the equivalent Settings control to change modes later.

    "Read Local Data" is what zeus itself needs (the game and this app on the
    same machine, reading ESOHelper.lua straight off disk -- "This PC" mode).
    "Sync Server" is read-only: pulls whatever's already on the sync server
    instead of touching any local save file at all, for a machine that isn't
    running the game.

    Closing the dialog without picking either (Escape, the window's own close
    button) leaves `sync/mode` unset -- the dialog will just ask again next
    launch, since the guard above only skips it once something's actually
    been saved -- see the `if dlg.exec() and dlg.mode:` guard at the call site.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("ESO Helper")
        self.setModal(True)
        self.mode: str | None = None

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        label = QLabel("How should ESO Helper get its data this session?")
        layout.addWidget(label)

        local_btn = QPushButton("Read Local Data")
        local_btn.setToolTip(
            "\"This PC\" mode -- reads ESOHelper.lua straight off disk. "
            "Use this on the machine that actually runs the game."
        )
        local_btn.clicked.connect(lambda: self._choose("this_pc"))
        layout.addWidget(local_btn)

        server_btn = QPushButton("Sync Server (client only)")
        server_btn.setToolTip(
            "Read-only -- pulls characters/achievements/set collections from "
            "the sync server configured in ~/.config/eso-helper/sync.json "
            "instead of any local save file."
        )
        server_btn.clicked.connect(lambda: self._choose("server"))
        layout.addWidget(server_btn)

    def _choose(self, mode: str):
        if mode == "server" and not sync_config.load().get("server_url"):
            # First-ever "Sync Server" pick with nothing configured yet (see
            # settings_dialog.py for the full Settings-dialog equivalent of
            # this field) -- ask right here instead of failing later in
            # _reload() with an opaque SyncServerError.
            url, ok = QInputDialog.getText(
                self, "Sync Server Address",
                "Server address (e.g. http://192.168.1.x:8091):",
                QLineEdit.EchoMode.Normal,
            )
            url = url.strip()
            if not ok or not url:
                return  # stay on this dialog -- nothing changed
            sync_config.save({"server_url": url})
        self.mode = mode
        self.accept()
