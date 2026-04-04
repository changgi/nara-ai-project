"""LangGraph 오케스트레이터 (langgraph 설치 시 사용 가능)"""

def create_orchestrator(*args, **kwargs):
    from .graph import create_orchestrator as _create
    return _create(*args, **kwargs)

def build_orchestrator_graph(*args, **kwargs):
    from .graph import build_orchestrator_graph as _build
    return _build(*args, **kwargs)
