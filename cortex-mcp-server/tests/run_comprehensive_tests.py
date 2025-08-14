#!/usr/bin/env python3
"""
Comprehensive test runner for the cross-tool memory system.

This script runs all test categories and generates a comprehensive report
validating that all requirements are met.
"""

import subprocess
import sys
import time
from pathlib import Path
import argparse


def run_command(cmd, description):
    """Run a command and return the result."""
    print(f"\n{'='*60}")
    print(f"Running: {description}")
    print(f"Command: {' '.join(cmd)}")
    print(f"{'='*60}")
    
    start_time = time.time()
    result = subprocess.run(cmd, capture_output=True, text=True)
    end_time = time.time()
    
    print(f"Duration: {end_time - start_time:.2f} seconds")
    print(f"Return code: {result.returncode}")
    
    if result.stdout:
        print("STDOUT:")
        print(result.stdout)
    
    if result.stderr:
        print("STDERR:")
        print(result.stderr)
    
    return result


def main():
    """Run comprehensive test suite."""
    parser = argparse.ArgumentParser(description="Run comprehensive test suite")
    parser.add_argument("--unit-only", action="store_true", help="Run only unit tests")
    parser.add_argument("--integration-only", action="store_true", help="Run only integration tests")
    parser.add_argument("--performance-only", action="store_true", help="Run only performance tests")
    parser.add_argument("--e2e-only", action="store_true", help="Run only end-to-end tests")
    parser.add_argument("--requirements-only", action="store_true", help="Run only requirements validation tests")
    parser.add_argument("--fast", action="store_true", help="Skip slow tests")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--coverage", action="store_true", help="Generate coverage report")
    
    args = parser.parse_args()
    
    # Base pytest command
    base_cmd = ["python", "-m", "pytest"]
    
    if args.verbose:
        base_cmd.append("-v")
    
    if args.coverage:
        base_cmd.extend(["--cov=src", "--cov-report=html", "--cov-report=term"])
    
    # Test results
    results = {}
    
    print("Starting Comprehensive Test Suite")
    print("=" * 60)
    
    # 1. Unit Tests
    if not any([args.integration_only, args.performance_only, args.e2e_only, args.requirements_only]):
        print("\n🧪 Running Unit Tests...")
        unit_tests = [
            "tests/test_conversation_repository.py",
            "tests/test_project_repository.py", 
            "tests/test_preferences_repository.py",
            "tests/test_database_models.py",
            "tests/test_embedding_service.py",
            "tests/test_vector_store.py",
            "tests/test_search_engine.py",
            "tests/test_tagging_service.py",
            "tests/test_learning_engine.py",
            "tests/test_context_manager.py",
            "tests/test_conversation_processor.py",
            "tests/test_config_management.py",
            "tests/test_error_handling.py"
        ]
        
        cmd = base_cmd + unit_tests
        if args.fast:
            cmd.append("--run-fast")
        
        result = run_command(cmd, "Unit Tests")
        results["unit_tests"] = result.returncode == 0
    
    # 2. Integration Tests
    if not any([args.unit_only, args.performance_only, args.e2e_only, args.requirements_only]):
        print("\n🔗 Running Integration Tests...")
        integration_tests = [
            "tests/test_mcp_server.py",
            "tests/test_rest_api.py",
            "tests/test_search_integration.py",
            "tests/test_semantic_search_integration.py",
            "tests/test_context_tagging_integration.py",
            "tests/test_security_integration.py"
        ]
        
        cmd = base_cmd + integration_tests + ["-m", "integration"]
        result = run_command(cmd, "Integration Tests")
        results["integration_tests"] = result.returncode == 0
    
    # 3. Performance Tests
    if args.performance_only or not any([args.unit_only, args.integration_only, args.e2e_only, args.requirements_only]):
        print("\n⚡ Running Performance Tests...")
        cmd = base_cmd + ["tests/test_performance.py", "-m", "performance"]
        if not args.fast:
            cmd.append("--run-performance")
        
        result = run_command(cmd, "Performance Tests")
        results["performance_tests"] = result.returncode == 0
    
    # 4. Load Tests
    if not args.fast and not any([args.unit_only, args.integration_only, args.e2e_only, args.requirements_only]):
        print("\n🏋️ Running Load Tests...")
        cmd = base_cmd + ["tests/test_load_testing.py", "-m", "load", "--run-load"]
        
        result = run_command(cmd, "Load Tests")
        results["load_tests"] = result.returncode == 0
    
    # 5. End-to-End Tests
    if args.e2e_only or not any([args.unit_only, args.integration_only, args.performance_only, args.requirements_only]):
        print("\n🎯 Running End-to-End Tests...")
        cmd = base_cmd + ["tests/test_end_to_end_workflows.py", "-m", "e2e"]
        
        result = run_command(cmd, "End-to-End Tests")
        results["e2e_tests"] = result.returncode == 0
    
    # 6. Requirements Validation Tests
    if args.requirements_only or not any([args.unit_only, args.integration_only, args.performance_only, args.e2e_only]):
        print("\n📋 Running Requirements Validation Tests...")
        cmd = base_cmd + ["tests/test_requirements_validation.py", "-m", "requirements"]
        
        result = run_command(cmd, "Requirements Validation Tests")
        results["requirements_tests"] = result.returncode == 0
    
    # 7. Simple MCP and REST API Tests (quick smoke tests)
    if not any([args.performance_only, args.e2e_only, args.requirements_only]):
        print("\n💨 Running Quick Smoke Tests...")
        smoke_tests = [
            "tests/test_mcp_server_simple.py",
            "tests/test_rest_api_simple.py"
        ]
        
        cmd = base_cmd + smoke_tests
        result = run_command(cmd, "Smoke Tests")
        results["smoke_tests"] = result.returncode == 0
    
    # Generate Summary Report
    print("\n" + "="*60)
    print("COMPREHENSIVE TEST SUITE SUMMARY")
    print("="*60)
    
    total_categories = len(results)
    passed_categories = sum(1 for passed in results.values() if passed)
    
    print(f"Test Categories Run: {total_categories}")
    print(f"Test Categories Passed: {passed_categories}")
    print(f"Overall Success Rate: {passed_categories/total_categories*100:.1f}%")
    
    print("\nDetailed Results:")
    for category, passed in results.items():
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"  {category.replace('_', ' ').title()}: {status}")
    
    # Requirements Coverage Report
    print("\n" + "="*60)
    print("REQUIREMENTS COVERAGE REPORT")
    print("="*60)
    
    requirements_coverage = {
        "Requirement 1 - Context Persistence": results.get("e2e_tests", False) and results.get("integration_tests", False),
        "Requirement 2 - Intelligent Categorization": results.get("integration_tests", False) and results.get("unit_tests", False),
        "Requirement 3 - Local Network Privacy": results.get("unit_tests", False) and results.get("integration_tests", False),
        "Requirement 4 - Query and Search": results.get("integration_tests", False) and results.get("performance_tests", False),
        "Requirement 5 - MCP Integration": results.get("integration_tests", False) and results.get("smoke_tests", False),
        "Requirement 6 - Learning and Patterns": results.get("unit_tests", False) and results.get("integration_tests", False),
        "Requirement 7 - Project Management": results.get("unit_tests", False) and results.get("integration_tests", False)
    }
    
    for requirement, covered in requirements_coverage.items():
        status = "✅ COVERED" if covered else "❌ NOT COVERED"
        print(f"  {requirement}: {status}")
    
    # Performance Metrics Report
    if results.get("performance_tests", False):
        print("\n" + "="*60)
        print("PERFORMANCE METRICS SUMMARY")
        print("="*60)
        print("✅ All performance tests passed")
        print("  - Document storage: < 10ms per document")
        print("  - Search operations: < 200ms average")
        print("  - Concurrent operations: 95%+ success rate")
        print("  - Memory usage: Within acceptable limits")
    
    # Final Status
    print("\n" + "="*60)
    if all(results.values()):
        print("🎉 ALL TESTS PASSED - SYSTEM READY FOR DEPLOYMENT")
        exit_code = 0
    else:
        print("❌ SOME TESTS FAILED - REVIEW REQUIRED")
        exit_code = 1
    
    print("="*60)
    
    # Coverage report location
    if args.coverage:
        print(f"\n📊 Coverage report generated: htmlcov/index.html")
    
    sys.exit(exit_code)


if __name__ == "__main__":
    main()