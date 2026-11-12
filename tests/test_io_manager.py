from __future__ import annotations
from pathlib import Path
from campus_safety.io_manager.io_manager import IOManager

def test_io_manager_menu_valid_choice():
    # Mock user input to return "1" immediately
    inputs = iter(["1"])
    outputs = []
    
    io = IOManager(
        read=lambda prompt: next(inputs),
        write=lambda msg: outputs.append(msg)
    )
    
    choice = io.menu()
    assert choice == "1"

def test_io_manager_confirm_yes():
    inputs = iter(["yes"])
    outputs = []
    
    io = IOManager(
        read=lambda prompt: next(inputs),
        write=lambda msg: outputs.append(msg)
    )
    
    result = io.confirm("Proceed? (y/n): ")
    assert result is True

def test_io_manager_confirm_invalid_then_no():
    # Test input validation loop: invalid text first, then "n"
    inputs = iter(["maybe", "n"])
    outputs = []
    
    io = IOManager(
        read=lambda prompt: next(inputs),
        write=lambda msg: outputs.append(msg)
    )
    
    result = io.confirm("Proceed? (y/n): ")
    assert result is False
    assert any("[Error]" in msg for msg in outputs)