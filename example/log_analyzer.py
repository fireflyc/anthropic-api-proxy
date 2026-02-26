#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Log Analyzer GUI Tool
Analyzes request/response log files with a tkinter-based interface.
"""

import json
import re
import tkinter as tk
from copy import deepcopy
from tkinter import ttk, filedialog, messagebox, scrolledtext
from datetime import datetime
from pathlib import Path


class LogEntry:
    """Represents a single log entry (request or response)."""

    def __init__(self, timestamp: str, direction: str, request_id: str, data: dict):
        self.timestamp = timestamp
        self.direction = direction  # '>' for request, '<' for response
        self.request_id = request_id
        self.data = data

    def is_request(self) -> bool:
        return self.direction == '>'

    def is_response(self) -> bool:
        return self.direction == '<'


class LogAnalyzer:
    """Parses and analyzes log files."""

    LOG_PATTERN = re.compile(
        r'^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3})\s*-\s*([<>])\s*(req-[a-f0-9-]+)\s*(.*)$'
    )

    @classmethod
    def parse_line(cls, line: str) -> LogEntry | None:
        """Parse a single log line."""
        line = line.strip()
        if not line:
            return None

        match = cls.LOG_PATTERN.match(line)
        if not match:
            return None

        timestamp, direction, request_id, json_str = match.groups()
        try:
            data = json.loads(json_str)
        except json.decoder.JSONDecodeError:
            print(f"skip {json_str}")
            return None

        return LogEntry(timestamp, direction, request_id, data)

    @classmethod
    def parse_file(cls, filepath: str) -> list[LogEntry]:
        """Parse entire log file."""
        entries = []
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                entry = cls.parse_line(line)
                if entry:
                    entries.append(entry)
        return entries

    @classmethod
    def pair_entries(cls, entries: list[LogEntry]) -> dict[str, tuple]:
        """Pair requests with their responses."""
        pairs = {}
        for entry in entries:
            if entry.request_id not in pairs:
                pairs[entry.request_id] = {'request': None, 'response': None}

            if entry.is_request():
                pairs[entry.request_id]['request'] = entry
            else:
                pairs[entry.request_id]['response'] = entry

        return pairs


class LogAnalyzerGUI:
    """Main GUI application for log analysis."""

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Log Analyzer - Request/Response Viewer")
        self.root.geometry("1200x800")

        self.entries: list[LogEntry] = []
        self.pairs: dict[str, tuple] = {}
        self.current_file: str = ""

        self._setup_ui()

    def _setup_ui(self):
        """Set up the user interface."""
        # Menu bar
        self._create_menu()

        # Main container
        main_frame = ttk.Frame(self.root, padding="5")
        main_frame.grid(row=0, column=0, sticky="nsew")

        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(1, weight=1)

        # Top toolbar
        toolbar = ttk.Frame(main_frame)
        toolbar.grid(row=0, column=0, sticky="ew", pady=(0, 5))
        toolbar.columnconfigure(1, weight=1)

        ttk.Label(toolbar, text="Log File:").grid(row=0, column=0, padx=(0, 5))

        self.file_var = tk.StringVar(value="No file loaded")
        file_label = ttk.Label(toolbar, textvariable=self.file_var, width=50)
        file_label.grid(row=0, column=1, sticky="w")

        ttk.Button(toolbar, text="Open...", command=self.open_file).grid(
            row=0, column=2, padx=(10, 0)
        )

        self.refresh_btn = ttk.Button(toolbar, text="Refresh", command=self.refresh_file)
        self.refresh_btn.grid(row=0, column=3, padx=(5, 0))
        self.refresh_btn.state(['disabled'])

        self.copy_btn = ttk.Button(toolbar, text="Copy JSON", command=self.copy_to_clipboard)
        self.copy_btn.grid(row=0, column=4, padx=(10, 0))
        self.copy_btn.state(['disabled'])

        # Stats label
        self.stats_var = tk.StringVar(value="")
        stats_label = ttk.Label(toolbar, textvariable=self.stats_var)
        stats_label.grid(row=0, column=5, padx=(20, 0))

        # Paned window for resizable panels
        self.paned = ttk.PanedWindow(main_frame, orient=tk.HORIZONTAL)
        self.paned.grid(row=1, column=0, sticky="nsew")
        main_frame.rowconfigure(1, weight=1)

        # Left panel - Request list (20% width)
        left_frame = ttk.LabelFrame(self.paned, text="Requests", padding="5")
        self.paned.add(left_frame, weight=1)

        # Create treeview for request list
        columns = ('time', 'content')
        self.tree = ttk.Treeview(left_frame, columns=columns, show='headings', height=20)

        self.tree.heading('time', text='Time')
        self.tree.heading('content', text='Content')

        self.tree.column('time', width=150, minwidth=150)
        self.tree.column('content', width=200)

        # Scrollbar for tree
        tree_scroll = ttk.Scrollbar(left_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=tree_scroll.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        tree_scroll.grid(row=0, column=1, sticky="ns")
        left_frame.columnconfigure(0, weight=1)
        left_frame.rowconfigure(0, weight=1)

        self.tree.bind('<<TreeviewSelect>>', self.on_select)

        # Right panel - Details (80% width)
        right_frame = ttk.LabelFrame(self.paned, text="Details", padding="5")
        self.paned.add(right_frame, weight=4)

        right_frame.columnconfigure(0, weight=1)
        right_frame.rowconfigure(0, weight=1)

        # Notebook for tabs
        self.notebook = ttk.Notebook(right_frame)
        self.notebook.grid(row=0, column=0, sticky="nsew")
        right_frame.rowconfigure(0, weight=1)

        # Request tab
        req_frame = ttk.Frame(self.notebook, padding="5")
        self.notebook.add(req_frame, text="Request")

        self.request_text = scrolledtext.ScrolledText(
            req_frame, wrap=tk.WORD, width=60, height=20, font=('Consolas', 9)
        )
        self.request_text.grid(row=0, column=0, sticky="nsew")
        req_frame.columnconfigure(0, weight=1)
        req_frame.rowconfigure(0, weight=1)

        # Response tab
        resp_frame = ttk.Frame(self.notebook, padding="5")
        self.notebook.add(resp_frame, text="Response")

        self.response_text = scrolledtext.ScrolledText(
            resp_frame, wrap=tk.WORD, width=60, height=20, font=('Consolas', 9)
        )
        self.response_text.grid(row=0, column=0, sticky="nsew")
        resp_frame.columnconfigure(0, weight=1)
        resp_frame.rowconfigure(0, weight=1)

        # Search frame (in Request tab)
        search_frame = ttk.Frame(req_frame, padding="5")
        search_frame.grid(row=1, column=0, sticky="ew", pady=(5, 0))
        req_frame.columnconfigure(0, weight=1)

        ttk.Label(search_frame, text="Search:").grid(row=0, column=0, padx=(0, 5))

        self.search_var = tk.StringVar()
        self.search_entry = ttk.Entry(search_frame, textvariable=self.search_var, width=40)
        self.search_entry.grid(row=0, column=1, padx=(0, 5), sticky="ew")
        search_frame.columnconfigure(1, weight=1)

        self.search_btn = ttk.Button(search_frame, text="Find", command=self.search_in_request)
        self.search_btn.grid(row=0, column=2, padx=(0, 5))

        self.search_prev_btn = ttk.Button(search_frame, text="Previous", command=self.search_previous)
        self.search_prev_btn.grid(row=0, column=3, padx=(0, 5))

        self.search_next_btn = ttk.Button(search_frame, text="Next", command=self.search_next)
        self.search_next_btn.grid(row=0, column=4)

        self.search_matches_var = tk.StringVar(value="")
        self.search_matches_label = ttk.Label(search_frame, textvariable=self.search_matches_var)
        self.search_matches_label.grid(row=0, column=5, padx=(10, 0))

        # Search frame (in Response tab)
        resp_search_frame = ttk.Frame(resp_frame, padding="5")
        resp_search_frame.grid(row=1, column=0, sticky="ew", pady=(5, 0))
        resp_frame.columnconfigure(0, weight=1)

        ttk.Label(resp_search_frame, text="Search:").grid(row=0, column=0, padx=(0, 5))

        self.resp_search_var = tk.StringVar()
        self.resp_search_entry = ttk.Entry(resp_search_frame, textvariable=self.resp_search_var, width=40)
        self.resp_search_entry.grid(row=0, column=1, padx=(0, 5), sticky="ew")
        resp_search_frame.columnconfigure(1, weight=1)

        self.resp_search_btn = ttk.Button(resp_search_frame, text="Find", command=self.search_in_response)
        self.resp_search_btn.grid(row=0, column=2, padx=(0, 5))

        self.resp_search_prev_btn = ttk.Button(resp_search_frame, text="Previous", command=self.resp_search_previous)
        self.resp_search_prev_btn.grid(row=0, column=3, padx=(0, 5))

        self.resp_search_next_btn = ttk.Button(resp_search_frame, text="Next", command=self.resp_search_next)
        self.resp_search_next_btn.grid(row=0, column=4)

        self.resp_search_matches_var = tk.StringVar(value="")
        self.resp_search_matches_label = ttk.Label(resp_search_frame, textvariable=self.resp_search_matches_var)
        self.resp_search_matches_label.grid(row=0, column=5, padx=(10, 0))

        # Configure text tags for highlighting
        self.request_text.tag_configure("search", background="yellow")
        self.response_text.tag_configure("search", background="yellow")

        # Store search results
        self.request_search_results = []
        self.request_search_index = 0
        self.response_search_results = []
        self.response_search_index = 0

        # Bind Enter key for search
        self.search_entry.bind('<Return>', lambda e: self.search_in_request())
        self.resp_search_entry.bind('<Return>', lambda e: self.search_in_response())

    def _create_menu(self):
        """Create menu bar."""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)

        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Open...", command=self.open_file, accelerator="Ctrl+O")
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.quit, accelerator="Ctrl+Q")

        # Help menu
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="About", command=self.show_about)

        # Keyboard shortcuts
        self.root.bind('<Control-o>', lambda e: self.open_file())
        self.root.bind('<Control-q>', lambda e: self.root.quit())

    def open_file(self):
        """Open a log file."""
        filepath = filedialog.askopenfilename(
            title="Open Log File",
            filetypes=[
                ("Log files", "*.log"),
                ("Text files", "*.txt"),
                ("All files", "*.*")
            ]
        )

        if filepath:
            self.load_file(filepath)

    def load_file(self, filepath: str):
        """Load and parse a log file."""
        try:
            self.current_file = filepath
            self.file_var.set(filepath)

            # Parse the file
            self.entries = LogAnalyzer.parse_file(filepath)
            self.pairs = LogAnalyzer.pair_entries(self.entries)

            # Populate the tree
            self.populate_tree()

            # Update stats
            requests = sum(1 for e in self.entries if e.is_request())
            responses = sum(1 for e in self.entries if e.is_response())
            self.stats_var.set(f"Requests: {requests} | Responses: {responses}")

            # Enable buttons
            self.refresh_btn.state(['!disabled'])
            self.copy_btn.state(['!disabled'])

        except Exception as e:
            print(e)
            messagebox.showerror("Error", f"Failed to load file: {e}")

    def refresh_file(self):
        """Reload the current file."""
        if self.current_file:
            self.load_file(self.current_file)

    def populate_tree(self):
        """Populate the tree view with requests."""
        # Clear existing items
        for item in self.tree.get_children():
            self.tree.delete(item)

        # Add requests (sorted by timestamp)
        requests = [e for e in self.entries if e.is_request()]

        for entry in requests:
            item_id = entry.request_id

            # Extract content from messages
            content = self._extract_content(entry.data)

            self.tree.insert('', 'end', iid=item_id,
                             values=(entry.timestamp, content))

    def _extract_content(self, data: dict) -> str:
        """Extract content from request data."""
        messages = data.get('messages', [])
        if messages:
            last_msg = messages[-1]
            content = last_msg.get('content', '')
            if isinstance(content, str):
                # Truncate long content for display
                if len(content) > 100:
                    return content[:100] + "..."
                return content
            elif isinstance(content, list):
                # Handle array content
                text_parts = []
                for item in content:
                    if isinstance(item, dict) and item.get('type') == 'text':
                        text_parts.append(item.get('text', ''))
                text = ' '.join(text_parts)
                if len(text) > 100:
                    return text[:100] + "..."
                return text if text else str(content)
        return ''

    def copy_to_clipboard(self):
        """Copy current JSON to clipboard."""
        # Get the currently selected request_id
        selection = self.tree.selection()
        if not selection:
            messagebox.showwarning("Nothing to copy", "No request selected.")
            return

        request_id = selection[0]
        pair = self.pairs.get(request_id, {})

        # Get the currently selected tab
        current_tab = self.notebook.index(self.notebook.select())

        if current_tab == 0:  # Request tab
            entry = pair.get('request')
            data = entry.data if entry else None
        else:  # Response tab
            entry = pair.get('response')
            data = entry.data if entry else None

        if data:
            formatted = json.dumps(data, indent=2, ensure_ascii=False)
            self.root.clipboard_clear()
            self.root.clipboard_append(formatted)
        else:
            messagebox.showwarning("Nothing to copy", "No content to copy.")

    def on_select(self, event):
        """Handle selection in tree view."""
        selection = self.tree.selection()
        if not selection:
            return

        request_id = selection[0]
        pair = self.pairs.get(request_id, {})

        # Clear search highlights and reset index
        self.request_text.tag_remove("search", 1.0, tk.END)
        self.response_text.tag_remove("search", 1.0, tk.END)
        self.request_search_results.clear()
        self.response_search_results.clear()
        self.request_search_index = 0
        self.response_search_index = 0
        self.search_matches_var.set("")
        self.resp_search_matches_var.set("")

        # Display request
        self.request_text.delete(1.0, tk.END)
        request = deepcopy(pair.get('request'))
        if request:
            formatted = self._format_json(request.data)
            self.request_text.insert(tk.END, formatted)

        # Display response
        self.response_text.delete(1.0, tk.END)
        response = deepcopy(pair.get('response'))
        if response:
            formatted = self._format_json(response.data)
            self.response_text.insert(tk.END, formatted)
        else:
            self.response_text.insert(tk.END, "No response recorded")

    def _format_json(self, data: dict) -> str:
        """Format JSON data for display, truncating long fields."""
        # Create a copy to avoid modifying original
        display_data = self._prepare_display_data(data)

        try:
            return json.dumps(display_data, indent=2, ensure_ascii=False)
        except Exception:
            return str(data)

    def _prepare_display_data(self, data: dict, depth: int = 0) -> dict:
        """Prepare data for display, truncating long fields."""
        if not isinstance(data, dict):
            return data

        result = {}
        max_depth = 5

        for key, value in data.items():
            # Handle tools field specially - show only function names
            if key == 'tools' and isinstance(value, list):
                tool_names = []
                for tool in value:
                    if isinstance(tool, dict):
                        func = tool.get('function', {})
                        name = func.get('name', 'unknown')
                        tool_names.append(f"[Function: {name}]")
                result[key] = tool_names
            # Handle nested dicts
            elif isinstance(value, dict):
                if depth < max_depth:
                    result[key] = self._prepare_display_data(value, depth + 1)
                else:
                    result[key] = "{...}"
            elif key == "messages":
                processed_list = []
                for item in value:
                    content = item.get('content', '')
                    if content is not None:
                        content = content if len(
                            content) <= 1000 else f"{content[:1000]}... ({len(content)} chars total)"
                        item["content"] = content
                    processed_list.append(item)
                result[key] = processed_list
            else:
                result[key] = value

        return result

    def search_in_request(self):
        """Search in request JSON."""
        search_term = self.search_var.get()
        if not search_term:
            return

        text = self.request_text.get(1.0, tk.END)
        self._perform_search(text, search_term, self.request_text,
                             self.request_search_results, self.search_matches_var)
        self.request_search_index = 0

    def search_in_response(self):
        """Search in response JSON."""
        search_term = self.resp_search_var.get()
        if not search_term:
            return

        text = self.response_text.get(1.0, tk.END)
        self._perform_search(text, search_term, self.response_text,
                             self.response_search_results, self.resp_search_matches_var)
        self.response_search_index = 0

    def _perform_search(self, text: str, search_term: str, text_widget,
                        results_list: list, matches_var: tk.StringVar):
        """Perform search and highlight results."""
        # Remove existing highlights
        text_widget.tag_remove("search", 1.0, tk.END)

        if not search_term:
            return

        # Find all occurrences
        results_list.clear()
        start_pos = 1.0
        while True:
            pos = text_widget.search(search_term, start_pos, tk.END)
            if not pos:
                break
            end_pos = f"{pos}+{len(search_term)}c"
            results_list.append((pos, end_pos))
            start_pos = end_pos

        # Highlight all results
        for start, end in results_list:
            text_widget.tag_add("search", start, end)

        # Update matches count
        if results_list:
            matches_var.set(f"{len(results_list)} matches")
            # Jump to first match
            text_widget.mark_set(tk.INSERT, results_list[0][0])
            text_widget.see(results_list[0][0])
        else:
            matches_var.set("No matches")

    def search_next(self):
        """Go to next search result in request."""
        if self.request_search_results:
            self.request_search_index = (self.request_search_index + 1) % len(self.request_search_results)
            pos, _ = self.request_search_results[self.request_search_index]
            self.request_text.mark_set(tk.INSERT, pos)
            self.request_text.see(pos)

    def search_previous(self):
        """Go to previous search result in request."""
        if self.request_search_results:
            self.request_search_index = (self.request_search_index - 1) % len(self.request_search_results)
            pos, _ = self.request_search_results[self.request_search_index]
            self.request_text.mark_set(tk.INSERT, pos)
            self.request_text.see(pos)

    def resp_search_next(self):
        """Go to next search result in response."""
        if self.response_search_results:
            self.response_search_index = (self.response_search_index + 1) % len(self.response_search_results)
            pos, _ = self.response_search_results[self.response_search_index]
            self.response_text.mark_set(tk.INSERT, pos)
            self.response_text.see(pos)

    def resp_search_previous(self):
        """Go to previous search result in response."""
        if self.response_search_results:
            self.response_search_index = (self.response_search_index - 1) % len(self.response_search_results)
            pos, _ = self.response_search_results[self.response_search_index]
            self.response_text.mark_set(tk.INSERT, pos)
            self.response_text.see(pos)

    def show_about(self):
        """Show about dialog."""
        messagebox.showinfo(
            "About Log Analyzer",
            "Log Analyzer v1.0\n\n"
            "A tool for viewing request/response logs.\n\n"
            "Features:\n"
            "- View paired requests and responses\n"
            "- Truncated display of long fields\n"
            "- Tools shown as function names only\n"
            "- Refresh to reload updated files\n"
            "- Search within JSON content"
        )


def main():
    """Main entry point."""
    root = tk.Tk()

    # Set theme
    style = ttk.Style()
    if 'clam' in style.theme_names():
        style.theme_use('clam')

    app = LogAnalyzerGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
