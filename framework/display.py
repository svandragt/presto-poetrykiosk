class TextScreen:
    def status(self, msg: str) -> None:
        raise NotImplementedError

    def show_text(self, text: str) -> None:
        raise NotImplementedError

    def show_error(self, err: Exception) -> None:
        raise NotImplementedError
