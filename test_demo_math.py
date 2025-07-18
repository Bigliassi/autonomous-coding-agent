"""
Test file for demo_math.py
This demonstrates how the agent can work with existing test files.
"""

import pytest
import math
from demo_math import add, subtract, multiply, divide, calculate_area_circle, factorial

def test_add():
    """Test addition function."""
    assert add(2, 3) == 5
    assert add(-1, 1) == 0
    assert add(0, 0) == 0
    assert add(-5, -3) == -8

def test_subtract():
    """Test subtraction function."""
    assert subtract(5, 3) == 2
    assert subtract(1, 1) == 0
    assert subtract(0, 5) == -5
    assert subtract(-3, -1) == -2

def test_multiply():
    """Test multiplication function."""
    assert multiply(3, 4) == 12
    assert multiply(0, 5) == 0
    assert multiply(-2, 3) == -6
    assert multiply(-2, -3) == 6

def test_divide():
    """Test division function."""
    assert divide(10, 2) == 5
    assert divide(7, 2) == 3.5
    assert divide(-6, 3) == -2
    assert divide(-8, -2) == 4

def test_divide_by_zero():
    """Test division by zero raises ValueError."""
    with pytest.raises(ValueError, match="Cannot divide by zero"):
        divide(5, 0)

def test_calculate_area_circle():
    """Test circle area calculation."""
    # Test with radius 1
    assert abs(calculate_area_circle(1) - math.pi) < 0.0001
    
    # Test with radius 0
    assert calculate_area_circle(0) == 0
    
    # Test with radius 2
    expected_area = math.pi * 4  # π * r²
    assert abs(calculate_area_circle(2) - expected_area) < 0.0001

def test_calculate_area_circle_negative_radius():
    """Test circle area with negative radius raises ValueError."""
    with pytest.raises(ValueError, match="Radius cannot be negative"):
        calculate_area_circle(-1)

def test_factorial():
    """Test factorial function."""
    assert factorial(0) == 1
    assert factorial(1) == 1
    assert factorial(5) == 120
    assert factorial(6) == 720

def test_factorial_negative():
    """Test factorial with negative number raises ValueError."""
    with pytest.raises(ValueError, match="Factorial is not defined for negative numbers"):
        factorial(-1)

def test_basic_integration():
    """Test that functions work together."""
    # Test a simple calculation: (5 + 3) * 2 / 4
    result = divide(multiply(add(5, 3), 2), 4)
    assert result == 4.0 