# ===============================================================
#                     tkEditor1.py
# ---------------------------------------------------------------
# Written for users PAGE and Tkinter
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Author: Greg Walters
# Date Created: 2025-10-03 06:38:32
# ---------------------------------------------------------------
# Copyright © 2025 by G.D. Walters and Designated Geek Software
# ---------------------------------------------------------------
# Original idea by Greg Walters
# Original code by ChatGPT 5.0
# Modified by Greg Walters
# Version 0.1.0
# ===============================================================
# Purpose:
#    This file contains code to create a 'Metawidget' for Tkinter
# that provides a Tk Text widget that has line numbers that sync
# when text contents are scrolled.  It also supplies a VERY simple
# and somewhat useless folding utility.  it also includes a VERY
# simple code/syntax highlighting routine.
#
# PLEASE NOTE...
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# This is a work in progress.  ALL functionallity is subject to
# change without notice.  There are many things that I would like
# to see changed from the original ChatGPT version.
# ===============================================================
# Last modified on October 3, 2025
# ---------------------------------------------------------------
# For usage, see the tkEditorDemo1 program.
# ---------------------------------------------------------------


import tkinter as tk
import tkinter.ttk as ttk
from tkinter.constants import *

import re


# _debug = True


# ---------------- Tooltip ----------------
class Tooltip(tk.Toplevel):
    """Simple tooltip window."""

    def __init__(self, widget, text):
        super().__init__(widget)
        self.withdraw()
        self.overrideredirect(True)
        self.wm_attributes("-topmost", True)

        label = tk.Label(
            self,
            text=text,
            background="#ffffe0",
            relief="solid",
            borderwidth=1,
            font=("TkDefaultFont", 9),
        )
        label.pack(ipadx=2, ipady=1)

    def show(self, x, y):
        self.geometry(f"+{x+15}+{y+10}")
        self.deiconify()

    def hide(self):
        self.withdraw()


# ---------------- Line Numbers ----------------
class LineNumbers(tk.Canvas):
    def __init__(self, master, text_widget, folds, **kwargs):
        super().__init__(master, width=70, **kwargs)
        self.text_widget = text_widget
        self.folds = folds
        self.hover_line = None
        self.tooltip = None

        self.bind("<Motion>", self.on_motion)
        self.bind("<Leave>", self.on_leave)
        self.bind("<Button-1>", self.toggle_fold)

    def redraw(self, event=None):
        self.delete("all")
        i = self.text_widget.index("@0,0")
        current_line = int(self.text_widget.index("insert").split(".")[0])

        while True:
            dline = self.text_widget.dlineinfo(i)
            if dline is None:
                break
            y = dline[1]
            h = dline[3]
            linenum = int(str(i).split(".")[0])

            # Highlight active line
            if linenum == current_line:
                self.create_rectangle(0, y, 70, y + h, fill="#ddeeff", outline="")

            # Line number
            self.create_text(
                20,
                y,
                anchor="n",
                text=linenum,
                fill="blue" if linenum == current_line else "gray25",
                font=(
                    "TkDefaultFont",
                    9,
                    "bold" if linenum == current_line else "normal",
                ),
            )

            # Fold marker
            if linenum in self.folds:
                folded = self.folds[linenum]["folded"]
                bg_color = "#f2dede" if folded else "#d9edf7"
                if self.hover_line == linenum:
                    bg_color = "#ffcccc" if folded else "#cce5ff"

                # Background rectangle
                self.create_rectangle(
                    40, y + 2, 65, y + h - 2, fill=bg_color, outline="#666", width=1
                )

                # Triangle
                cx, cy = 52, y + h / 2
                size = 6
                points = (
                    [cx - size, cy - size, cx - size, cy + size, cx + size, cy]
                    if folded
                    else [cx - size, cy - size, cx + size, cy - size, cx, cy + size]
                )
                self.create_polygon(points, fill="darkred" if folded else "darkblue")

            i = self.text_widget.index(f"{i}+1line")

    def on_motion(self, event):
        line = int(self.text_widget.index(f"@0,{event.y}").split(".")[0])
        if line in self.folds:
            if self.hover_line != line:
                self.hover_line = line
                self.redraw()
                folded = self.folds[line]["folded"]
                msg = "Click to unfold block" if folded else "Click to fold block"
                if self.tooltip:
                    self.tooltip.destroy()
                self.tooltip = Tooltip(self, msg)
                self.tooltip.show(
                    self.winfo_rootx() + event.x, self.winfo_rooty() + event.y
                )
        else:
            if self.hover_line is not None:
                self.hover_line = None
                self.redraw()
            if self.tooltip:
                self.tooltip.hide()

    def on_leave(self, event):
        if self.hover_line is not None:
            self.hover_line = None
            self.redraw()
        if self.tooltip:
            self.tooltip.hide()

    def toggle_fold(self, event):
        line_clicked = int(self.text_widget.index(f"@0,{event.y}").split(".")[0])
        self._toggle_fold_line(line_clicked)

    def _toggle_fold_line(self, linenum):
        if linenum in self.folds:
            info = self.folds[linenum]
            start, end = info["range"]
            if info["folded"]:
                self.text_widget.tag_remove("elide", f"{start+1}.0", f"{end}.0 lineend")
                info["folded"] = False
            else:
                self.text_widget.tag_add("elide", f"{start+1}.0", f"{end}.0 lineend")
                info["folded"] = True
            self.redraw()

    def fold_all(self):
        for linenum, info in self.folds.items():
            start, end = info["range"]
            self.text_widget.tag_add("elide", f"{start+1}.0", f"{end}.0 lineend")
            info["folded"] = True
        self.redraw()

    def unfold_all(self):
        for linenum, info in self.folds.items():
            start, end = info["range"]
            self.text_widget.tag_remove("elide", f"{start+1}.0", f"{end}.0 lineend")
            info["folded"] = False
        self.redraw()


# ---------------- Custom Text ----------------
class CustomText(tk.Text):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bind("<<Modified>>", self._on_change)
        self.tag_configure("current_line", background="#eef6ff")
        self.tag_configure("elide", elide=True)
        # Syntax highlighting tags
        self.tag_configure("keyword", foreground="blue")
        self.tag_configure("string", foreground="lightblue")
        self.tag_configure("comment", foreground="green")
        self.tag_configure("number", foreground="purple")

    def _on_change(self, event=None):
        self.event_generate("<<Change>>", when="tail")
        self.edit_modified(False)
        self.highlight_syntax()

    def highlight_syntax(self):
        content = self.get("1.0", "end-1c")
        self.tag_remove("keyword", "1.0", "end")
        self.tag_remove("string", "1.0", "end")
        self.tag_remove("comment", "1.0", "end")
        self.tag_remove("number", "1.0", "end")

        keyword_pattern = r"\b(def|for|if|else|elif|while|return|in|print|class|import|from|as|with|try|except|finally|break|continue|pass|and|or|not|is|lambda)\b"
        string_pattern = r"(\".*?\"|'.*?')"
        comment_pattern = r"#[^\n]*"
        number_pattern = r"\b\d+(\.\d+)?\b"

        for match in re.finditer(keyword_pattern, content):
            start = f"1.0 + {match.start()} chars"
            end = f"1.0 + {match.end()} chars"
            self.tag_add("keyword", start, end)
        for match in re.finditer(string_pattern, content):
            start = f"1.0 + {match.start()} chars"
            end = f"1.0 + {match.end()} chars"
            self.tag_add("string", start, end)
        for match in re.finditer(comment_pattern, content):
            start = f"1.0 + {match.start()} chars"
            end = f"1.0 + {match.end()} chars"
            self.tag_add("comment", start, end)
        for match in re.finditer(number_pattern, content):
            start = f"1.0 + {match.start()} chars"
            end = f"1.0 + {match.end()} chars"
            self.tag_add("number", start, end)


# ---------------- App ----------------
# class App(tk.Tk):
class PyEditor(ttk.Frame):
    __version__ = "0.1.0"
    __license__ = "MIT"
    _debug = True

    def __init__(self, parent=None):
        super().__init__()
        # self.title("Tkinter Editor with Auto Folding")
        # self.geometry("800x600")

        # frame = tk.Frame(self)
        frame = parent

        # frame.pack(fill=tk.BOTH, expand=True)

        # Scrollbars
        vscroll = tk.Scrollbar(frame, orient="vertical")
        vscroll.pack(side=tk.RIGHT, fill=tk.Y)
        hscroll = tk.Scrollbar(frame, orient="horizontal")
        hscroll.pack(side=tk.BOTTOM, fill=tk.X)

        # Text widget
        self.text = CustomText(frame, wrap=tk.NONE, undo=True)
        self.text.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        # Folding info and line numbers
        self.folds = {}
        self.linenumbers = LineNumbers(frame, self.text, self.folds, bg="#f7f7f7")
        self.linenumbers.pack(side=tk.LEFT, fill=tk.Y)

        # Scroll sync
        def on_scroll(*args):
            vscroll.set(*args)
            self.linenumbers.redraw()

        self.text.config(yscrollcommand=on_scroll)
        vscroll.config(command=self._on_vscroll)
        hscroll.config(command=self.text.xview)

        # Bind events
        self.text.bind("<KeyRelease>", self._update_highlight)
        self.text.bind("<ButtonRelease-1>", self._update_highlight)
        self.text.bind("<<Change>>", self._update_highlight)
        self.text.bind("<Configure>", self._update_highlight)

        # Keyboard shortcuts
        # self.bind_all("<Control-slash>", self.toggle_fold_shortcut)
        # self.bind_all("<Control-Shift-slash>", self.toggle_fold_all)
        self.bind_all("<Control-KeyPress><Key-slash>", self.toggle_fold_shortcut)
        self.bind_all("<Shift-Control-KeyPress><Key-slash>", self.toggle_fold_all)

        # Sample Python code

    #         sample_code = """# Sample Python code
    # def hello_world():
    #     print("Hello, world!")
    #     for i in range(5):
    #         print(i)  # print numbers
    #     print("Done")

    # x = 42
    # if x > 10:
    #     print("x is big")
    # """
    #         self.text.insert("1.0", sample_code)
    #         self._update_highlight()  # initial highlight + folds

    # ---------------- Folding ----------------
    def _detect_folds(self):
        old_folds = {k: v["folded"] for k, v in self.folds.items()}
        lines = self.text.get("1.0", "end-1c").split("\n")
        self.folds.clear()
        stack = []
        for idx, line in enumerate(lines, start=1):
            stripped = line.strip()
            indent = len(line) - len(line.lstrip(" "))
            if stripped.endswith(":"):
                stack.append((idx, indent))
            else:
                while stack and indent <= stack[-1][1]:
                    start, _ = stack.pop()
                    end = idx - 1
                    if end > start:
                        self.folds[start] = {
                            "range": (start, end),
                            "folded": old_folds.get(start, False),
                        }
        while stack:
            start, _ = stack.pop()
            end = len(lines)
            if end > start:
                self.folds[start] = {
                    "range": (start, end),
                    "folded": old_folds.get(start, False),
                }

    def _on_vscroll(self, *args):
        self.text.yview(*args)
        self.linenumbers.redraw()

    def _update_highlight(self, event=None):
        self._detect_folds()  # recompute folds dynamically
        self.text.tag_remove("current_line", "1.0", "end")
        cursor_index = self.text.index("insert")
        line_start = f"{cursor_index.split('.')[0]}.0"
        line_end = f"{cursor_index.split('.')[0]}.end+1c"
        self.text.tag_add("current_line", line_start, line_end)
        self.linenumbers.redraw()

    def toggle_fold_shortcut(self, event=None):
        if self._debug:
            print("into toggle_fold_shortcut")
        line = int(self.text.index("insert").split(".")[0])
        if line in self.folds:
            self.linenumbers._toggle_fold_line(line)

    def toggle_fold_all(self, event=None):
        if self._debug:
            print("into toggle_fold_all")
        if any(info["folded"] for info in self.folds.values()):
            self.linenumbers.unfold_all()
        else:
            self.linenumbers.fold_all()

    def load_file(self, filename=None):

        data = self.read_file(filename)
        self.text.insert(1.0, data)
        self._update_highlight()

    def clear_editor(self):
        self.text.delete(1.0, END)

    def read_file(self, filename=None):
        # ======================================================
        # function read_file()
        # ======================================================
        # Read file, leaving end of lines
        # ======================================================
        with open(filename) as f:
            lines = f.read()
        return lines

    def get_version(self):
        return self.__version__

    def get_licence(self):
        return self.__license__
