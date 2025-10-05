#!/usr/bin/env python3

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
# Version 0.1.1
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
# Last modified on October 5, 2025
# ---------------------------------------------------------------
# For usage, see the tkEditorDemo1 program.
# ---------------------------------------------------------------
"""
Tkinter code editor with:
- CodeText (auto-indent, configurable)
- Line numbers gutter
- Click + keyboard code folding (uses 'elide' tags)
- Basic Python syntax highlighting
"""

import tkinter as tk
from tkinter import ttk
from tkinter.scrolledtext import ScrolledText
import tkinter.font as tkfont
from tkinter.constants import *

import keyword
import re


# ---------------------------
# CodeText: Text subclass
# ---------------------------
class CodeText(tk.Text):
    def __init__(self, master=None, indent_width=4, use_tabs=False, **kwargs):
        super().__init__(master, **kwargs)
        self.indent_width = indent_width
        self.use_tabs = use_tabs
        self.bind("<Return>", self._auto_indent)
        # call highlight when text changes
        self._highlight_after_id = None

    def set_indent_width(self, spaces: int):
        if isinstance(spaces, int) and spaces >= 0:
            self.indent_width = spaces

    def _get_line_indent(self, line_text: str) -> int:
        """Return the number of leading spaces (treat tabs as indent_width)."""
        if not line_text:
            return 0
        count = 0
        for ch in line_text:
            if ch == " ":
                count += 1
            elif ch == "\t":
                count += self.indent_width
            else:
                break
        return count

    def _auto_indent(self, event):
        """
        Insert newline with indentation matching current line.
        If the current (previous) line ends with ':', add additional indent.
        """
        insert_index = self.index("insert")
        line_num = int(insert_index.split(".")[0])
        line_text = self.get(f"{line_num}.0", f"{line_num}.end")

        base_indent = self._get_line_indent(line_text)
        new_indent = base_indent

        if line_text.rstrip().endswith(":"):
            new_indent += self.indent_width

        # Decide whether to use tabs or spaces
        if self.use_tabs and (self.indent_width % 1 == 0):
            # convert indentation into tabs where appropriate (simple approach)
            tabs = new_indent // self.indent_width
            spaces = new_indent % self.indent_width
            indent_str = "\t" * tabs + " " * spaces
        else:
            indent_str = " " * new_indent

        self.insert("insert", "\n" + indent_str)
        return "break"


# ---------------------------
# LineNumbers gutter (with fold marker)
# ---------------------------
class LineNumbers(tk.Canvas):
    def __init__(self, master, text_widget: CodeText, width=44, **kwargs):
        super().__init__(master, width=width, **kwargs)
        self.text_widget = text_widget
        self.width = width
        self.bg = kwargs.get("bg", "#f7f7f7")
        # Bindings to react to text changes/scroll
        self.text_widget.bind("<<Change>>", self.redraw)
        self.text_widget.bind("<Configure>", self.redraw)
        self.text_widget.bind("<KeyRelease>", self.redraw)
        self.text_widget.bind("<ButtonRelease-1>", self.redraw)
        # capture clicks in gutter for folding toggles
        self.bind("<Button-1>", self._on_click)

        # Keep a mapping of fold markers -> start_line
        self.fold_markers = {}  # (y_range) -> start_line

    def redraw(self, *args):
        """Redraw line numbers and fold markers."""
        self.delete("all")
        self.fold_markers.clear()

        i = self.text_widget.index("@0,0")
        font = ("Courier", 12)
        while True:
            dline = self.text_widget.dlineinfo(i)
            if dline is None:
                break
            y = dline[1]
            lineno = str(i).split(".")[0]
            # line number text
            self.create_text(
                4, y, anchor="nw", text=lineno, font=font, tags=("lineno",)
            )
            # fold marker: small triangle if a foldable block starts here
            if self.master.editor.is_foldable_line(int(lineno)):
                # draw small triangle marker
                size = 6
                x0, x1 = self.width - 12, self.width - 4
                y0 = y + 4
                # check if folded
                if self.master.editor.is_line_folded(int(lineno)):
                    # right-pointing triangle (collapsed)
                    pts = (x0, y0, x1, y0 + size / 2, x0, y0 + size)
                else:
                    # down-pointing triangle (expanded)
                    pts = (x0, y0, x0 + size / 2, y0 + size, x0 + size, y0)
                marker = self.create_polygon(
                    pts, outline="black", fill="black", tags=("foldmarker",)
                )
                # store mapping from marker id -> line
                self.fold_markers[marker] = int(lineno)
            i = self.text_widget.index(f"{i}+1line")

    def _on_click(self, event):
        # find the nearest marker clicked
        item = self.find_closest(event.x, event.y)
        if not item:
            return
        item = item[0]
        if "foldmarker" in self.gettags(item):
            start_line = self.fold_markers.get(item, None)
            if start_line is None:
                return
            # toggle fold
            self.master.editor.toggle_fold(start_line)
            # redraw after fold change
            self.redraw()


# ---------------------------
# Main Editor Frame
# ---------------------------
class CodeEditor(tk.Frame):
    __version__ = "0.1.1"
    __license__ = "MIT"
    _debug = True

    def __init__(self, master=None, indent_width=4, **kwargs):
        super().__init__(master, **kwargs)
        self.pack(fill="both", expand=True)
        # Left: gutter, middle: text, right: vscroll
        self.gutter_frame = tk.Frame(self)
        self.gutter_frame.pack(side="left", fill="y")

        self.text_frame = tk.Frame(self)
        self.text_frame.pack(side="left", fill="both", expand=True)

        self._set_editor_colours()

        # Use CodeText
        self.text = CodeText(
            self.text_frame,
            indent_width=indent_width,
            wrap="none",
            font=("Courier", 12),
            undo=True,
        )

        # link to editor so gutter can access fold info
        self.gutter_frame.editor = self
        self.text_frame.editor = self

        # Scrollbar
        self.vsb = ttk.Scrollbar(
            self.text_frame, orient="vertical", command=self._on_vscroll
        )
        self.text.configure(yscrollcommand=self.vsb.set)

        # Horizontal scrollbar
        self.hsb = ttk.Scrollbar(
            self.text_frame, orient="horizontal", command=self.text.xview
        )
        self.text.configure(xscrollcommand=self.hsb.set)

        # Line numbers gutter
        self.linenumbers = LineNumbers(self.gutter_frame, self.text, bg="#f7f7f7")
        self.linenumbers.pack(side="left", fill="y")

        self.vsb.pack(side="right", fill="y")
        self.hsb.pack(side="bottom", fill="x")

        self.text.pack(side="left", fill="both", expand=True)

        # Folding state: mapping start_line -> dict with 'end' and 'tag'
        self.folds = {}

        # Syntax highlighting tags
        self._setup_tags()

        # Event wiring for change notifications & highlight scheduling
        self._install_change_event()

        # Keybindings for folding
        self.text.bind("<Control-f>", self._toggle_fold_current)
        self.text.bind("<Alt-Left>", self._fold_current)
        self.text.bind("<Alt-Right>", self._unfold_current)

        # keep line numbers in sync with scroll
        self.text.bind("<MouseWheel>", self._on_mousewheel)
        self.text.bind("<Button-4>", self._on_mousewheel)  # linux
        self.text.bind("<Button-5>", self._on_mousewheel)

    # ---------- view/scroll helpers ----------
    def _on_vscroll(self, *args):
        self.text.yview(*args)
        self.linenumbers.redraw()

    def _on_mousewheel(self, event):
        # allow normal scroll and then update gutter
        self.text.after(1, self.linenumbers.redraw)

    # ---------- change event ----------
    def _install_change_event(self):
        # Whenever text is modified by user or program, generate <<Change>>
        def _on_modify(event=None):
            # generate virtual event for gutter and other listeners
            try:
                self.text.event_generate("<<Change>>", when="tail")
            except tk.TclError:
                pass
            # schedule syntax highlight
            self._schedule_highlight()
            # schedule fold updates (if necessary)
            self.text.after(100, self._refresh_folds_on_edit)

        self.text.bind("<<Modified>>", _on_modify)

        # Ensure modified flag is reset after handling
        def _reset_modified(event=None):
            try:
                self.text.tk.call(self.text._w, "edit", "modified", 0)
            except tk.TclError:
                pass

        self.text.bind("<<Change>>", _reset_modified)

    # ---------- folding logic ----------
    def is_foldable_line(self, line: int) -> bool:
        """
        Decide whether a line starts a foldable block.
        For Python: line that ends with ':' and the next line is more indented.
        """
        try:
            s = self.text.get(f"{line}.0", f"{line}.end")
        except tk.TclError:
            return False
        if not s.rstrip().endswith(":"):
            return False
        # check next line indentation
        try:
            next_line_text = self.text.get(f"{line+1}.0", f"{line+1}.end")
        except tk.TclError:
            return False
        return self.text._get_line_indent(next_line_text) > self.text._get_line_indent(
            s
        )

    def is_line_folded(self, line: int) -> bool:
        """Return True if a fold starting at `line` exists and is currently elided."""
        fold = self.folds.get(line)
        if not fold:
            return False
        # check whether elide tag exists (any text with the tag)
        ranges = self.text.tag_ranges(fold["tag"])
        return bool(ranges)

    def _find_block_range(self, start_line: int):
        """
        Given a line that begins a block (like ends with ':'), return (start_index, end_index, end_line)
        where end_index is the index of the last character in the block to be hidden (inclusive).
        Basic approach: a block includes all subsequent lines with indentation > start indent.
        """
        start_line_text = self.text.get(f"{start_line}.0", f"{start_line}.end")
        start_indent = self.text._get_line_indent(start_line_text)

        # start scanning from next line
        cur = start_line + 1
        last_in_block = start_line
        total_lines = int(self.text.index("end-1c").split(".")[0])
        while cur <= total_lines:
            line_txt = self.text.get(f"{cur}.0", f"{cur}.end")
            # blank lines: treat their indent as large negative so they can be part of block if they are empty
            if line_txt.strip() == "":
                # keep them in block only if next non-empty line remains in block
                last_in_block = cur
                cur += 1
                continue
            indent = self.text._get_line_indent(line_txt)
            if indent > start_indent:
                last_in_block = cur
                cur += 1
            else:
                break
        if last_in_block == start_line:
            return None  # no block
        start_index = f"{start_line+1}.0"  # hide from the next line start
        end_index = f"{last_in_block}.end"
        return start_index, end_index, last_in_block

    def toggle_fold(self, start_line: int):
        if start_line in self.folds:
            self.unfold(start_line)
        else:
            self.fold(start_line)

    def fold(self, start_line: int):
        rng = self._find_block_range(start_line)
        if not rng:
            return False
        start_index, end_index, end_line = rng
        tagname = f"fold_{start_line}"
        # create tag with elide true to hide the text
        self.text.tag_add(tagname, start_index, end_index)
        self.text.tag_config(tagname, elide=True)
        # store fold metadata
        self.folds[start_line] = {"start": start_line, "end": end_line, "tag": tagname}
        # redraw gutter
        self.linenumbers.redraw()
        return True

    def unfold(self, start_line: int):
        fold = self.folds.get(start_line)
        if not fold:
            return False
        tagname = fold["tag"]
        self.text.tag_delete(tagname)
        self.folds.pop(start_line, None)
        self.linenumbers.redraw()
        return True

    # ---------- keyboard actions ----------
    def _toggle_fold_current(self, event=None):
        idx = self.text.index("insert")
        cur_line = int(idx.split(".")[0])
        # If current line not foldable, search up to find nearest foldable ancestor
        if not self.is_foldable_line(cur_line):
            # search up
            for L in range(cur_line - 1, 0, -1):
                if self.is_foldable_line(L):
                    cur_line = L
                    break
        self.toggle_fold(cur_line)
        return "break"

    def _fold_current(self, event=None):
        idx = self.text.index("insert")
        cur_line = int(idx.split(".")[0])
        # find nearest foldable ancestor up the tree
        for L in range(cur_line, 0, -1):
            if self.is_foldable_line(L):
                self.fold(L)
                break
        return "break"

    def _unfold_current(self, event=None):
        idx = self.text.index("insert")
        cur_line = int(idx.split(".")[0])
        # try current line and parents
        for L in range(cur_line, 0, -1):
            if L in self.folds:
                self.unfold(L)
                break
        return "break"

    def _refresh_folds_on_edit(self):
        """
        Called after edits to ensure existing folds are still valid.
        If structure changed so a fold no longer valid, unfold it.
        Also if new foldable lines appeared, leave them closed (do not auto-fold).
        """
        to_unfold = []
        for start, meta in list(self.folds.items()):
            # Ensure start line still exists and still begins a block
            total_lines = int(self.text.index("end-1c").split(".")[0])
            if start > total_lines:
                to_unfold.append(start)
                continue
            if not self.is_foldable_line(start):
                to_unfold.append(start)
        for s in to_unfold:
            self.unfold(s)

    def _set_editor_colours(self):
        # global keyword_fg_color, string_color, comment_color, current_line_bg_color

        self.keyword_fg_color = "#0000ff"
        self.string_fg_color = "#a31515"
        self.comment_fg_color = "#008000"
        self.currentLine_bg_color = "#f0f8ff"

    # ---------- syntax highlighting ----------
    def _setup_tags(self):
        # create and keep font objects so they are not garbage-collected
        base_font = tkfont.Font(font=self.text["font"])
        base_font.configure(size=12)
        self._base_font = base_font
        comment_font = base_font.copy()
        comment_font.configure(slant="italic", size=12)
        self._comment_font = comment_font

        # minimal styling — users can customize these tags
        #
        # self.keyword_fg_color = "#0000ff"
        # self.string_fg_color = "#a31515"
        # self.comment_fg_color = "#008000"
        # self.currentLine_bg_color = "#f0f8ff"

        self.text.tag_configure(
            "keyword", foreground=self.keyword_fg_color, font=self._base_font
        )
        self.text.tag_configure(
            "string", foreground=self.string_fg_color, font=self._base_font
        )
        # use the italic font for comments
        self.text.tag_configure(
            "comment", foreground=self.comment_fg_color, font=self._comment_font
        )
        # optional: background for current line
        self.text.tag_configure("current_line_bg", background=self.currentLine_bg_color)

        # self.text.tag_configure("keyword", foreground="#0000ff", font=self._base_font)
        # self.text.tag_configure("string", foreground="#a31515", font=self._base_font)
        # # use the italic font for comments
        # self.text.tag_configure(
        #     "comment", foreground="#008000", font=self._comment_font
        # )
        # # optional: background for current line
        # self.text.tag_configure("current_line_bg", background="#f0f8ff")

        # precompile regexes for speed
        kwlist = keyword.kwlist
        self._kw_regex = re.compile(r"\b(" + r"|".join(map(re.escape, kwlist)) + r")\b")
        self._string_regex = re.compile(r"(\".*?\"|\'.*?\')", re.S)
        self._comment_regex = re.compile(r"#[^\n]*")

        # schedule initial highlight
        self._schedule_highlight(initial=True)

    def _schedule_highlight(self, initial=False):
        """Debounce highlight calls."""
        if self.text._highlight_after_id:
            try:
                self.text.after_cancel(self.text._highlight_after_id)
            except Exception:
                pass
        delay = 50 if not initial else 0
        self.text._highlight_after_id = self.text.after(delay, self._do_highlight)

    def _do_highlight(self):
        txt = self.text.get("1.0", "end-1c")
        # clear tags
        for tag in ("keyword", "string", "comment"):
            self.text.tag_remove(tag, "1.0", "end")

        # comments first (so strings inside commented text not highlighted)
        for m in self._comment_regex.finditer(txt):
            start = "1.0 + %dc" % m.start()
            end = "1.0 + %dc" % m.end()
            self.text.tag_add("comment", start, end)

        # strings
        for m in self._string_regex.finditer(txt):
            # skip if inside comment
            if self._comment_regex.search(txt[m.start() : m.end()]):
                continue
            start = "1.0 + %dc" % m.start()
            end = "1.0 + %dc" % m.end()
            self.text.tag_add("string", start, end)

        # keywords (skip those within strings/comments)
        for m in self._kw_regex.finditer(txt):
            s_idx = m.start()
            e_idx = m.end()
            # check it's not inside comment or string by checking tags at that index
            pos = "1.0 + %dc" % s_idx
            tags = self.text.tag_names(pos)
            if "string" in tags or "comment" in tags:
                continue
            start = "1.0 + %dc" % s_idx
            end = "1.0 + %dc" % e_idx
            self.text.tag_add("keyword", start, end)

        # reset scheduled id
        self.text._highlight_after_id = None

    # ---------- load/show helpers ----------
    def load_file(self, path):
        """Load a file into editor, clear folds & recalc."""
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = f.read()
        except Exception as e:
            print("Error loading file:", e)
            return False
        self.text.delete("1.0", "end")
        self.text.insert("1.0", data)
        # reset folds and tags
        for k in list(self.folds.keys()):
            self.unfold(k)
        self.folds.clear()
        # schedule gutter redraw and highlighting
        self.linenumbers.redraw()
        self._schedule_highlight(initial=True)
        return True

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


# ---------------------------
# Demo app
# ---------------------------
# def demo():
#     root = tk.Tk()
#     root.title("Tkinter Code Editor — Auto-indent, Folding, Highlighting")
#     root.geometry("900x600")

#     editor = CodeEditor(root, indent_width=4)
#     # expose as attribute for easier access in examples
#     root.editor = editor

#     # sample code to show functionality
#     sample = """\
# class Example:
#     def __init__(self, x):
#         self.x = x

#     def method(self):
#         if self.x > 0:
#             for i in range(self.x):
#                 print(i)
#         else:
#             print("no items")

# def top_level():
#     print("done")
# """
#     editor.text.insert("1.0", sample)
#     editor.linenumbers.redraw()
#     editor._schedule_highlight(initial=True)

#     # simple menu to load files and change indent width
#     menubar = tk.Menu(root)
#     filem = tk.Menu(menubar, tearoff=False)
#     def _open():
#         from tkinter.filedialog import askopenfilename
#         p = askopenfilename()
#         if p:
#             editor.load_file(p)
#     filem.add_command(label="Open...", command=_open)
#     filem.add_command(label="Quit", command=root.destroy)
#     menubar.add_cascade(label="File", menu=filem)

#     settings = tk.Menu(menubar, tearoff=False)
#     def set_indent():
#         # simple popup to set indent width
#         w = tk.Toplevel(root)
#         w.title("Set indent width")
#         tk.Label(w, text="Indent width (spaces):").pack(side="left", padx=4, pady=6)
#         var = tk.IntVar(value=editor.text.indent_width)
#         ent = tk.Entry(w, textvariable=var, width=6)
#         ent.pack(side="left", padx=4)
#         def ok():
#             editor.text.set_indent_width(var.get())
#             w.destroy()
#         tk.Button(w, text="OK", command=ok).pack(side="left", padx=6)
#     settings.add_command(label="Indent width...", command=set_indent)
#     menubar.add_cascade(label="Settings", menu=settings)

#     root.config(menu=menubar)
#     root.mainloop()

# if __name__ == "__main__":
#    demo()
