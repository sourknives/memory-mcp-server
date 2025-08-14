#!/usr/bin/env python3
"""
Test runner for intelligent storage functionality.

This script runs the comprehensive test suite for intelligent storage
with proper configuration and reporting.
"""

import subprocess
import sys
from pathlib import Path


def run_tests():
    """Run the intelligent storage test suite."""
    test_file = Path(__file__).parent / "test_intelligent_storage.py"
    
    # Test command with appropriate flags
    cmd = [
        sys.executable, "-m", "pytest",
        str(test_file),
        "-v",                    # Verbose output
        "--tb=short",           # Short traceback format
        "--strict-markers",     # Strict marker checking
        "--disable-warnings",   # Disable deprecation warnings for cleaner output
        "-x",                   # Stop on first failure (optional)
    ]
    
    print("🧪 Running Intelligent Storage Test Suite")
    print("=" * 50)
    print(f"Test file: {test_file}")
    print(f"Command: {' '.join(cmd)}")
    print("=" * 50)
    
    try:
        result = subprocess.run(cmd, check=False)
        
        if result.returncode == 0:
            print("\n✅ All tests passed!")
            print("\n📊 Test Coverage Summary:")
            print("- StorageAnalyzer pattern recognition and confidence scoring")
            print("- MCP tool integration with mock conversations")
            print("- Auto-storage and suggestion workflows")
            print("- Integration with existing storage and search functionality")
            print("- Requirements validation for all specified features")
            
        else:
            print(f"\n❌ Tests failed with exit code: {result.returncode}")
            
        return result.returncode
        
    except KeyboardInterrupt:
        print("\n⚠️  Test execution interrupted by user")
        return 1
    except Exception as e:
        print(f"\n💥 Error running tests: {e}")
        return 1


def run_specific_test_class(class_name: str):
    """Run tests for a specific test class."""
    test_file = Path(__file__).parent / "test_intelligent_storage.py"
    
    cmd = [
        sys.executable, "-m", "pytest",
        f"{test_file}::{class_name}",
        "-v",
        "--tb=short",
        "--disable-warnings"
    ]
    
    print(f"🧪 Running {class_name} tests")
    print("=" * 50)
    
    result = subprocess.run(cmd, check=False)
    return result.returncode


def run_requirements_validation():
    """Run only the requirements validation tests."""
    return run_specific_test_class("TestRequirementsValidation")


def run_storage_analyzer_tests():
    """Run only the StorageAnalyzer tests."""
    return run_specific_test_class("TestStorageAnalyzer")


def run_mcp_integration_tests():
    """Run only the MCP integration tests."""
    return run_specific_test_class("TestMCPToolIntegration")


def run_workflow_tests():
    """Run only the workflow tests."""
    return run_specific_test_class("TestAutoStorageWorkflows")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        test_type = sys.argv[1].lower()
        
        if test_type == "analyzer":
            exit_code = run_storage_analyzer_tests()
        elif test_type == "mcp":
            exit_code = run_mcp_integration_tests()
        elif test_type == "workflows":
            exit_code = run_workflow_tests()
        elif test_type == "requirements":
            exit_code = run_requirements_validation()
        else:
            print(f"Unknown test type: {test_type}")
            print("Available options: analyzer, mcp, workflows, requirements")
            exit_code = 1
    else:
        exit_code = run_tests()
    
    sys.exit(exit_code)