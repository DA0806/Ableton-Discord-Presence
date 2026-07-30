"""Next/Back/Finish installer GUI for AbletonDiscordPresence. Pure UI
wiring — all path/copy logic lives in wizard_logic.py so that logic can
be tested without spinning up tkinter (see wizard_logic.py's __main__)."""
import os
import sys
import tkinter as tk
import webbrowser
from tkinter import filedialog, messagebox, ttk

from wizard_logic import get_remote_scripts_path, install, is_existing_install

TUTORIAL_URL = 'https://github.com/DA0806/Ableton-Discord-Presence/blob/master/docs/tutorial.md'


def _bundled_source_dir():
    """Path to the AbletonDiscordPresence folder to copy — inside the
    PyInstaller onefile bundle when frozen, next to this script otherwise."""
    base = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, 'AbletonDiscordPresence')


class Wizard(tk.Tk):
    PAGES = ('welcome', 'location', 'install', 'finish')

    def __init__(self):
        tk.Tk.__init__(self)
        self.title('AbletonDiscordPresence Setup')
        self.geometry('480x320')
        self.resizable(False, False)

        self.dest_path = tk.StringVar(value=get_remote_scripts_path())
        self.open_tutorial = tk.BooleanVar(value=True)
        self.page_index = 0

        self.body = tk.Frame(self)
        self.body.pack(fill='both', expand=True, padx=16, pady=16)

        nav = tk.Frame(self)
        nav.pack(fill='x', padx=16, pady=(0, 16))
        self.back_btn = ttk.Button(nav, text='< Back', command=self._go_back)
        self.back_btn.pack(side='left')
        self.next_btn = ttk.Button(nav, text='Next >', command=self._go_next)
        self.next_btn.pack(side='right')

        self._render_page()

    def _clear_body(self):
        for widget in self.body.winfo_children():
            widget.destroy()

    def _render_page(self):
        self._clear_body()
        page = self.PAGES[self.page_index]
        getattr(self, '_render_' + page)()
        self.back_btn.config(state='normal' if self.page_index > 0 else 'disabled')
        self.next_btn.config(text='Finish' if page == 'finish' else 'Next >')

    def _render_welcome(self):
        tk.Label(self.body, text='AbletonDiscordPresence Setup', font=('Segoe UI', 14, 'bold')).pack(anchor='w')
        tk.Label(
            self.body, wraplength=440, justify='left',
            text=('This installs the AbletonDiscordPresence Remote Script '
                  'into your Ableton Live User Library, so your Discord '
                  'status shows your project name, BPM, and scale.'),
        ).pack(anchor='w', pady=(12, 0))

    def _render_location(self):
        tk.Label(self.body, text='Install location', font=('Segoe UI', 14, 'bold')).pack(anchor='w')
        tk.Label(
            self.body, wraplength=440, justify='left',
            text='Detected Ableton Remote Scripts folder:',
        ).pack(anchor='w', pady=(12, 4))
        row = tk.Frame(self.body)
        row.pack(fill='x')
        tk.Entry(row, textvariable=self.dest_path).pack(side='left', fill='x', expand=True)
        ttk.Button(row, text='Browse...', command=self._browse).pack(side='left', padx=(8, 0))

    def _render_install(self):
        tk.Label(self.body, text='Install', font=('Segoe UI', 14, 'bold')).pack(anchor='w')
        if is_existing_install(self.dest_path.get()):
            msg = 'Previous installation detected — it will be updated.'
        else:
            msg = 'AbletonDiscordPresence will be installed to the folder above.'
        tk.Label(self.body, wraplength=440, justify='left', text=msg).pack(anchor='w', pady=(12, 0))

    def _render_finish(self):
        tk.Label(self.body, text='Done', font=('Segoe UI', 14, 'bold')).pack(anchor='w')
        tk.Label(
            self.body, wraplength=440, justify='left',
            text=('Restart Ableton Live, then go to Preferences -> Link, '
                  'Tempo & MIDI and select "AbletonDiscordPresence" in a '
                  'Control Surface dropdown.'),
        ).pack(anchor='w', pady=(12, 12))
        tk.Checkbutton(self.body, text='Open the setup tutorial', variable=self.open_tutorial).pack(anchor='w')

    def _browse(self):
        chosen = filedialog.askdirectory(initialdir=self.dest_path.get())
        if chosen:
            self.dest_path.set(chosen)

    def _go_back(self):
        self.page_index -= 1
        self._render_page()

    def _go_next(self):
        page = self.PAGES[self.page_index]
        if page == 'install':
            try:
                install(_bundled_source_dir(), self.dest_path.get())
            except OSError as exc:
                messagebox.showerror('Install failed', str(exc))
                return
        if page == 'finish':
            if self.open_tutorial.get():
                webbrowser.open(TUTORIAL_URL)
            self.destroy()
            return
        self.page_index += 1
        self._render_page()


if __name__ == '__main__':
    Wizard().mainloop()
