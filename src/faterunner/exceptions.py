class FateError(Exception):
    pass


class ActionError(FateError):
    def __init__(self, err: Exception) -> None:
        self.err = err
        super().__init__(err)

    def __str__(self) -> str:
        return self.err.__str__()


class DependencyError(FateError):
    pass


class GuessError(FateError):
    pass
