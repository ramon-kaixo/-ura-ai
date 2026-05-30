from app import suma, resta


def test_suma():
    assert suma(2, 3) == 5


def test_resta():
    assert resta(10, 4) == 6
