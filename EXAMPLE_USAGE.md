# Example: Using Sandbox Testing

This document shows how the sandbox testing feature works in practice.

## Example 1: Simple Calculator Script

**User Request:**
```
Create a simple calculator script that adds two numbers
```

**Agent Response:**

> 🧪 **Test Code in Sandbox**  `Calculator script`
> 
> ⏳ **Creating sandbox and testing code...**

### ✅ Sandbox Test Passed

**Final Code:**
```python
# -*- coding: utf-8 -*-
def add_numbers(a, b):
    return a + b

# Test the calculator
result = add_numbers(5, 3)
print(f"5 + 3 = {result}")

result2 = add_numbers(10.5, 2.3)
print(f"10.5 + 2.3 = {result2}")
```

**Execution Output:**
```
5 + 3 = 8
10.5 + 2.3 = 12.8
```

---

## Example 2: API Script with Requirements

**User Request:**
```
Create a script that fetches data from GitHub API and prints the latest commit
```

**Agent Response:**

> 🧪 **Test Code in Sandbox**  `GitHub API fetcher`
> 
> ⏳ **Creating sandbox and testing code...**

### ✅ Sandbox Test Passed

**Final Code:**
```python
# -*- coding: utf-8 -*-
import requests

# Fetch latest commit from Python's GitHub repo
response = requests.get('https://api.github.com/repos/python/cpython/commits', 
                        params={'per_page': 1})

if response.status_code == 200:
    commit = response.json()[0]
    print(f"Latest commit: {commit['sha'][:7]}")
    print(f"Author: {commit['commit']['author']['name']}")
    print(f"Message: {commit['commit']['message'].split('\\n')[0]}")
else:
    print(f"Error: {response.status_code}")
```

**Requirements:**
```text
requests
```

**Execution Output:**
```
Latest commit: a3f2b1c
Author: Guido van Rossum
Message: Fix memory leak in parser
```

---

## Example 3: Failed Test with Auto-Retry

**User Request:**
```
Create a script that calculates fibonacci numbers
```

**Agent Response (First Attempt):**

> 🧪 **Test Code in Sandbox**  `Fibonacci calculator`
> 
> ⏳ **Creating sandbox and testing code...**

### ❌ Sandbox Test Failed

**Error:**
```
NameError: name 'fib' is not defined
```

🔄 **Retry attempt 1/2** - Fixing code based on error...

### ✅ Sandbox Test Passed

**Final Code:**
```python
# -*- coding: utf-8 -*-
def fibonacci(n):
    """Calculate the nth Fibonacci number"""
    if n <= 1:
        return n
    return fibonacci(n-1) + fibonacci(n-2)

# Test with first 10 numbers
print("First 10 Fibonacci numbers:")
for i in range(10):
    print(f"F({i}) = {fibonacci(i)}")
```

**Execution Output:**
```
First 10 Fibonacci numbers:
F(0) = 0
F(1) = 1
F(2) = 1
F(3) = 2
F(4) = 3
F(5) = 5
F(6) = 8
F(7) = 13
F(8) = 21
F(9) = 34
```

---

## Example 4: CSV Data Processing

**User Request:**
```
Create a script that generates sample CSV data and calculates the average
```

**Agent Response:**

> 🧪 **Test Code in Sandbox**  `CSV data processor`
> 
> ⏳ **Creating sandbox and testing code...**

### ✅ Sandbox Test Passed

**Final Code:**
```python
# -*- coding: utf-8 -*-
import csv
import io

# Generate sample CSV data
csv_data = """name,age,score
Alice,25,85
Bob,30,92
Charlie,28,78
Diana,32,95
Eve,27,88"""

# Parse CSV
reader = csv.DictReader(io.StringIO(csv_data))
scores = [int(row['score']) for row in reader]

# Calculate statistics
average = sum(scores) / len(scores)
maximum = max(scores)
minimum = min(scores)

print(f"Number of students: {len(scores)}")
print(f"Average score: {average:.2f}")
print(f"Highest score: {maximum}")
print(f"Lowest score: {minimum}")
```

**Execution Output:**
```
Number of students: 5
Average score: 87.60
Highest score: 95
Lowest score: 78
```

---

## How It Works

1. **User makes a request** for standalone code
2. **Agent generates code** and calls `test_standalone_code` tool
3. **Sandbox is created** in a temporary directory
4. **Code is executed** with a 30-second timeout
5. **Results are shown** in real-time to the user
6. **On failure:** Agent automatically fixes the code and retries (up to 2 times)
7. **On success:** Final working code is displayed

## No Approval Needed!

Unlike file operations or shell commands, sandbox testing does NOT require user approval. This allows for:
- **Faster iteration** - No waiting for user confirmation
- **Automatic verification** - Code is tested before being shown
- **Better reliability** - Failed code is automatically fixed

## Testing Your Own Code

You can also test the sandbox functionality directly:

```bash
cd dev-agent
python test_sandbox.py
```

This will run several test cases to verify the sandbox works correctly.
