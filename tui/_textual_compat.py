"""
Textual Compatibility Layer.

This module provides compatibility for Textual imports.
When Textual is not installed, it provides dummy classes to prevent import errors.
"""

HAS_TEXTUAL = False

try:
    # Import all the Textual components we need
    from textual.app import App, ComposeResult
    from textual.binding import Binding
    from textual.containers import Container, ScrollableContainer
    from textual.message import Message
    from textual.reactive import reactive
    from textual.screen import Screen
    from textual.widget import Widget
    from textual.widgets import Label, Input, Button, OptionList, Header, Footer, TabbedContent, TabPane
    from textual import events, on
    HAS_TEXTUAL = True
except ImportError:
    # Create dummy classes for when Textual is not installed
    class App: pass
    class ComposeResult: pass
    class Binding: pass
    class Container: pass
    class ScrollableContainer: pass
    class Message: pass
    class reactive:
        def __init__(self, default=None, init=True):
            self.default = default
            self.init = init
        def __call__(self, func):
            return func
    class Screen: pass
    class Widget: pass
    class Label: pass
    class Input: pass
    class Button: pass
    class OptionList: pass
    class Header: pass
    class Footer: pass
    class TabbedContent: pass
    class TabPane: pass
    
    class events: pass
    
    def on(event_type):
        def decorator(func):
            return func
        return decorator


# Re-export everything
if HAS_TEXTUAL:
    __all__ = [
        'App', 'ComposeResult', 'Binding', 'Container', 'ScrollableContainer',
        'Message', 'reactive', 'Screen', 'Widget', 'Label', 'Input',
        'Button', 'OptionList', 'Header', 'Footer', 'TabbedContent', 'TabPane',
        'events', 'on', 'HAS_TEXTUAL'
    ]
else:
    __all__ = ['HAS_TEXTUAL'] + [name for name in dir() if not name.startswith('_')]
