def compute_factorial(n: int) -> int:
    """Compute the factorial of a non-negative integer.

    Args:
        n: A non-negative integer.

    Returns:
        The factorial of n (n!).

    Raises:
        ValueError: If n is negative.
    """
    if n < 0:
        raise ValueError("Factorial is not defined for negative numbers.")

    if n in {0, 1}:
        return 1

    result = 1
    for i in range(2, n + 1):
        result *= i

    return result
