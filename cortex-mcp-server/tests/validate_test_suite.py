#!/usr/bin/env python3
"""
Validate that the comprehensive test suite is properly structured.
"""

import ast
import sys
from pathlib import Path


def validate_test_file(file_path):
    """Validate a test file structure."""
    print(f"Validating {file_path.name}...")
    
    try:
        with open(file_path, 'r') as f:
            content = f.read()
        
        # Parse the AST
        tree = ast.parse(content)
        
        # Count test functions and classes
        test_functions = 0
        test_classes = 0
        async_test_functions = 0
        
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                if node.name.startswith('test_'):
                    test_functions += 1
                    # Check if it's async
                    if isinstance(node, ast.AsyncFunctionDef):
                        async_test_functions += 1
            elif isinstance(node, ast.ClassDef):
                if node.name.startswith('Test'):
                    test_classes += 1
        
        print(f"  ✅ {test_classes} test classes")
        print(f"  ✅ {test_functions} test functions")
        print(f"  ✅ {async_test_functions} async test functions")
        
        # Check for required imports
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.append(node.module)
        
        # Check for pytest
        if 'pytest' in imports:
            print("  ✅ pytest imported")
        else:
            print("  ⚠️  pytest not imported")
        
        # Check for asyncio if there are async tests
        if async_test_functions > 0:
            if 'asyncio' in imports:
                print("  ✅ asyncio imported for async tests")
            else:
                print("  ⚠️  asyncio not imported but async tests present")
        
        return True
        
    except SyntaxError as e:
        print(f"  ❌ Syntax error: {e}")
        return False
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False


def main():
    """Validate all test files."""
    test_dir = Path(__file__).parent
    
    # New comprehensive test files
    new_test_files = [
        "test_performance.py",
        "test_end_to_end_workflows.py", 
        "test_load_testing.py",
        "test_requirements_validation.py"
    ]
    
    print("Validating Comprehensive Test Suite")
    print("=" * 50)
    
    all_valid = True
    
    for test_file in new_test_files:
        file_path = test_dir / test_file
        if file_path.exists():
            valid = validate_test_file(file_path)
            all_valid = all_valid and valid
        else:
            print(f"❌ {test_file} not found")
            all_valid = False
        print()
    
    # Validate configuration files
    config_files = ["conftest.py", "run_comprehensive_tests.py"]
    
    print("Validating Configuration Files")
    print("=" * 50)
    
    for config_file in config_files:
        file_path = test_dir / config_file
        if file_path.exists():
            print(f"✅ {config_file} exists")
            
            # Check if it's executable (for run script)
            if config_file.endswith('.py') and 'run' in config_file:
                if file_path.stat().st_mode & 0o111:
                    print(f"  ✅ {config_file} is executable")
                else:
                    print(f"  ⚠️  {config_file} is not executable")
        else:
            print(f"❌ {config_file} not found")
            all_valid = False
    
    print("\n" + "=" * 50)
    if all_valid:
        print("🎉 All test files are properly structured!")
        print("\nTo run the comprehensive test suite:")
        print("  python tests/run_comprehensive_tests.py")
        print("\nTo run specific test categories:")
        print("  python tests/run_comprehensive_tests.py --unit-only")
        print("  python tests/run_comprehensive_tests.py --performance-only")
        print("  python tests/run_comprehensive_tests.py --e2e-only")
        return 0
    else:
        print("❌ Some test files have issues. Please review and fix.")
        return 1


if __name__ == "__main__":
    sys.exit(main())