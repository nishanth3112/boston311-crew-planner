from boston311.api.fixtures import load_fixture
from boston311.api.schemas import AskResponse, ChatMessage


def run_ask(messages: list[ChatMessage]) -> AskResponse:
    """Answer a planning question from tool results, flagging numbers no tool returned."""
    # stub: BOS-8 replaces this body
    return load_fixture("ask", AskResponse)
