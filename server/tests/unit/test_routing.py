from app.simulation.algorithms.load_balancing import LoadBalancer


def test_round_robin():
    lb = LoadBalancer("round_robin")
    assert lb.select(["a", "b"]) == "a"
    assert lb.select(["a", "b"]) == "b"
    assert lb.select(["a", "b"]) == "a"


def test_least_connections():
    lb = LoadBalancer("least_connections")
    assert lb.select(["a", "b"], active_counts={"a": 10, "b": 2}) == "b"
