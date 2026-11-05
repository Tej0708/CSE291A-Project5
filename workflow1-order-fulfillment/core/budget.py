from dataclasses import dataclass


class BudgetExceeded(RuntimeError):
    pass


@dataclass
class RunBudget:
    """One budget shared by all attempts of a logical experiment."""

    max_model_calls: int = 10
    max_tool_calls: int = 40
    model_calls: int = 0
    tool_calls: int = 0

    def model(self) -> None:
        if self.model_calls >= self.max_model_calls:
            raise BudgetExceeded('Model-call budget exhausted')
        self.model_calls += 1

    def tool(self) -> None:
        if self.tool_calls >= self.max_tool_calls:
            raise BudgetExceeded('Tool-call budget exhausted')
        self.tool_calls += 1
