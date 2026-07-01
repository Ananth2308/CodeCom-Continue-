"""
Simple test script to verify sandbox functionality works.
Run this directly to test the sandbox without needing the full agent.
"""

import asyncio
import sys
import os

# Add parent directory to path so we can import app modules
sys.path.insert(0, os.path.dirname(__file__))

from app.tools.sandbox import test_code_in_sandbox


async def test_simple_script():
    """Test a simple Python script with no dependencies"""
    print("\n=== Test 1: Simple Python Script ===")

    code = """
print("Hello from sandbox!")
result = 2 + 2
print(f"2 + 2 = {result}")
"""

    result = await test_code_in_sandbox(code, requirements="")

    print(f"Success: {result['success']}")
    print(f"Stdout: {result['stdout']}")
    if result['stderr']:
        print(f"Stderr: {result['stderr']}")
    print(f"Iterations: {result['iterations']}")


async def test_with_requirements():
    """Test a script that requires external packages"""
    print("\n=== Test 2: Script with Requirements ===")

    code = """
import requests

# Test that requests module is available
print("requests module loaded successfully")
print(f"requests version: {requests.__version__}")
"""

    requirements = "requests"

    result = await test_code_in_sandbox(code, requirements=requirements)

    print(f"Success: {result['success']}")
    print(f"Stdout: {result['stdout']}")
    if result['stderr']:
        print(f"Stderr: {result['stderr']}")
    print(f"Iterations: {result['iterations']}")


async def test_failing_script():
    """Test a script that intentionally fails"""
    print("\n=== Test 3: Failing Script (Expected) ===")

    code = """
# This will fail because undefined_variable doesn't exist
print(undefined_variable)
"""

    result = await test_code_in_sandbox(code, requirements="")

    print(f"Success: {result['success']}")
    print(f"Stdout: {result['stdout']}")
    if result['stderr']:
        print(f"Stderr (expected): {result['stderr'][:200]}...")
    print(f"Iterations: {result['iterations']}")


async def test_math_script():
    """Test a simple math script"""
    print("\n=== Test 4: Math Script ===")

    code = """
import math

# Calculate some values
print("Mathematical calculations:")
print(f"π = {math.pi:.4f}")
print(f"e = {math.e:.4f}")
print(f"√2 = {math.sqrt(2):.4f}")

# Fibonacci sequence
def fibonacci(n):
    if n <= 1:
        return n
    return fibonacci(n-1) + fibonacci(n-2)

print(f"First 10 Fibonacci numbers: {[fibonacci(i) for i in range(10)]}")
"""

    result = await test_code_in_sandbox(code, requirements="")

    print(f"Success: {result['success']}")
    print(f"Stdout:\n{result['stdout']}")
    if result['stderr']:
        print(f"Stderr: {result['stderr']}")
    print(f"Iterations: {result['iterations']}")


async def main():
    print("=" * 60)
    print("Sandbox Testing - Verification Script")
    print("=" * 60)

    try:
        await test_simple_script()
        await test_with_requirements()
        await test_failing_script()
        await test_math_script()

        print("\n" + "=" * 60)
        print("All tests completed!")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ Error during testing: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
