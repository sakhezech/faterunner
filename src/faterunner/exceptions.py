class FateError(Exception):
    pass


class ActionError(FateError):
    pass


class DependencyError(FateError):
    pass


class GuessError(FateError):
    pass
