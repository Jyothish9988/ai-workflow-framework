"""Control-flow signals. They are exceptions so they can unwind out of deeply nested node execution."""


class LoopBreak(Exception):
    """Raised by a Break node; caught by the nearest enclosing loop."""


class LoopContinue(Exception):
    """Raised by a Continue node; caught by the nearest enclosing loop."""


class CancelledExecution(Exception):
    """Raised when a cancel signal is detected mid-execution."""
