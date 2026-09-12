def test_task_manager_module_has_retry():
    from backend.task_manager import TaskManager
    assert hasattr(TaskManager, 'retry')

def test_submit_analysis_preserves_question_for_worker(monkeypatch, tmp_path):
    """A lifecycle write must not turn a submitted question into None."""
    import backend.task_manager as module
    from backend.task_manager import TaskManager

    class ImmediateExecutor:
        def submit(self, fn, *args):
            fn(*args)

    manager = TaskManager.__new__(TaskManager)
    manager._lock = __import__("threading").RLock()
    manager._pipeline_running = set()
    manager._executor = ImmediateExecutor()
    analysis_dir = tmp_path / "analysis"
    analysis_dir.mkdir()
    task = {"task_id": "t1", "status": "ready", "question": None,
            "analysis_dir": str(analysis_dir), "answer_history": [],
            "artifacts": {}, "progress": 100}
    manager._tasks = {"t1": task}
    manager._persist = lambda value: None
    monkeypatch.setattr(module, "run_agent", lambda question, path: {
        "report": question, "routing": {}
    })
    result = manager.submit_analysis("t1", "分析运动员A")
    assert result["question"] == "分析运动员A"
    assert manager.get("t1")["status"] == "ready"
    assert manager.get("t1")["answer"] == "分析运动员A"

def test_submit_analysis_rejects_whitespace_question(tmp_path):
    from backend.task_manager import TaskManager
    import threading

    manager = TaskManager.__new__(TaskManager)
    manager._lock = threading.RLock()
    manager._tasks = {"t1": {"task_id": "t1", "status": "ready"}}
    manager._persist = lambda value: None
    try:
        manager.submit_analysis("t1", "   ")
    except ValueError as exc:
        assert str(exc) == "问题不能为空"
    else:
        raise AssertionError("whitespace-only questions must be rejected")
