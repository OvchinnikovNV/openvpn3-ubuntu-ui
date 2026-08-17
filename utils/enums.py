import enum


class ConnectButtonText(enum.Enum):
    connect = "Connect"
    disconnect = "Disconnect"
    cancel = "Cancel"


class VpnUiState(enum.Enum):
    disconnected = "disconnected"
    connecting = "connecting"
    authenticating = "authenticating"
    connected = "connected"
    disconnecting = "disconnecting"
