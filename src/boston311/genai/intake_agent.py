from boston311.api.fixtures import load_fixture
from boston311.api.schemas import ChatMessage, IntakeResponse


def run_intake(messages: list[ChatMessage]) -> IntakeResponse:
    """Route the conversation's problems to request types; the server fills department and queue."""
    # stub: BOS-4 replaces this body
    return load_fixture("intake", IntakeResponse)
