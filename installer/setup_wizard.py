"""Next/Done installer GUI for AbletonDiscordPresence. Pure UI wiring —
all path/copy logic lives in wizard_logic.py so that logic can be tested
without spinning up tkinter (see wizard_logic.py's __main__).

Dark, Ableton/Discord-adjacent theme: this installer runs next to two
apps its users keep open in dark mode all day, so a stock light Tk
window would look out of place."""
import os
import sys
import tkinter as tk
import webbrowser
from tkinter import filedialog, messagebox, ttk

from wizard_logic import get_remote_scripts_path, install, is_existing_install

TUTORIAL_URL = 'https://github.com/DA0806/Ableton-Discord-Presence/blob/master/docs/tutorial.md'

BG = '#2a2a2a'
SURFACE = '#363636'
TEXT = '#E8E6E3'
MUTED = '#9A9A9A'
ACCENT = '#fcaf57'


def _bundled_source_dir():
    """Path to the AbletonDiscordPresence folder to copy — inside the
    PyInstaller onefile bundle when frozen, next to this script otherwise."""
    base = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, 'AbletonDiscordPresence')


def _assets_dir():
    """Path to the icon/banner assets — inside the PyInstaller onefile
    bundle when frozen, next to this script otherwise (same pattern as
    _bundled_source_dir())."""
    base = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, 'assets')


class Wizard(tk.Tk):
    def __init__(self):
        tk.Tk.__init__(self)
        self.title('Ableton Discord Presence Setup')
        self.geometry('460x372')
        self.resizable(False, False)
        self.configure(bg=BG)

        self._init_style()
        self.iconbitmap(os.path.join(_assets_dir(), 'icon.ico'))

        self.dest_path = tk.StringVar(value=get_remote_scripts_path())
        self.open_tutorial = tk.BooleanVar(value=True)

        self._banner_img = tk.PhotoImage(file=os.path.join(_assets_dir(), 'banner.png'))
        tk.Label(self, image=self._banner_img, bg=BG, bd=0).pack(fill='x')

        self.body = tk.Frame(self, bg=BG)
        self.body.pack(fill='both', expand=True, padx=24, pady=20)

        self._render_setup()

    def _init_style(self):
        style = ttk.Style(self)
        style.theme_use('clam')
        style.configure('Dark.TCheckbutton', background=BG, foreground=TEXT)
        style.map('Dark.TCheckbutton', background=[('active', BG)])
        style.configure('Primary.TButton', background=ACCENT, foreground=BG,
                         borderwidth=0, padding=(16, 8), font=('Segoe UI Semibold', 10))
        style.map('Primary.TButton', background=[('active', '#fcaf57')])
        style.configure('Link.TButton', background=BG, foreground=ACCENT,
                         borderwidth=0, padding=(0, 0), font=('Segoe UI', 9, 'underline'))
        style.map('Link.TButton', background=[('active', BG)], foreground=[('active', '#fcaf57')])

    def _clear_body(self):
        for widget in self.body.winfo_children():
            widget.destroy()

    def _render_setup(self):
        self._clear_body()

        tk.Label(self.body, text='Ableton Discord Presence Setup', bg=BG, fg=TEXT,
                 font=('Segoe UI Semibold', 15)).pack(anchor='w')
        tk.Label(
            self.body, bg=BG, fg=MUTED, wraplength=400, justify='left',
            text=('Installs the Remote Script into your Ableton Live User '
                  'Library, so your Discord status shows your project, '
                  'BPM, and scale.'),
        ).pack(anchor='w', pady=(6, 20))

        tk.Label(self.body, text='INSTALL LOCATION', bg=BG, fg=MUTED,
                 font=('Segoe UI', 8)).pack(anchor='w')

        readout = tk.Frame(self.body, bg=SURFACE)
        readout.pack(fill='x', pady=(4, 4))
        tk.Label(readout, textvariable=self.dest_path, bg=SURFACE, fg=TEXT,
                 font=('Consolas', 9), anchor='w', padx=10, pady=8).pack(side='left', fill='x', expand=True)

        ttk.Button(self.body, text='Change...', style='Link.TButton',
                   command=self._browse, cursor='hand2').pack(anchor='w', pady=(0, 24))

        self.action_btn = ttk.Button(self.body, style='Primary.TButton', command=self._install)
        self._update_action_label()
        self.action_btn.pack(anchor='e')

    def _update_action_label(self):
        label = 'Update' if is_existing_install(self.dest_path.get()) else 'Install'
        self.action_btn.config(text=label)

    def _browse(self):
        chosen = filedialog.askdirectory(initialdir=self.dest_path.get())
        if chosen:
            self.dest_path.set(chosen)
            self._update_action_label()

    def _install(self):
        try:
            install(_bundled_source_dir(), self.dest_path.get())
        except OSError as exc:
            messagebox.showerror('Install failed', str(exc))
            return
        self._render_done()

    def _render_done(self):
        self._clear_body()

        tk.Label(self.body, text='✓', bg=BG, fg=ACCENT,
                 font=('Segoe UI', 28, 'bold')).pack(anchor='w')
        tk.Label(self.body, text='Done', bg=BG, fg=TEXT,
                 font=('Segoe UI Semibold', 15)).pack(anchor='w', pady=(4, 6))
        tk.Label(
            self.body, bg=BG, fg=MUTED, wraplength=400, justify='left',
            text=('Restart Ableton Live, then go to Preferences -> Link, '
                  'Tempo & MIDI and select "AbletonDiscordPresence" in a '
                  'Control Surface dropdown.'),
        ).pack(anchor='w', pady=(0, 16))

        ttk.Checkbutton(self.body, text='Open the setup tutorial', variable=self.open_tutorial,
                        style='Dark.TCheckbutton').pack(anchor='w', pady=(0, 20))

        ttk.Button(self.body, text='Finish', style='Primary.TButton',
                   command=self._finish).pack(anchor='e')

    def _finish(self):
        if self.open_tutorial.get():
            webbrowser.open(TUTORIAL_URL)
        self.destroy()


if __name__ == '__main__':
    Wizard().mainloop()
