# Advanced Calculator - Python Tkinter project
# Calculator + BMI + Currency converter in one window
# Run:  python advanced_calculator.py

import json
import math
import queue
import re
import threading
import tkinter as tk
from tkinter import ttk
from tkinter import font as tkfont
from urllib.request import Request, urlopen


# ------------------------------------------------------------------
# colours (dark = "obsidian", light = "ivory", gold accent in both)
# ------------------------------------------------------------------
DARK = dict(
    bg="#0B0D12", side="#0F1218", card="#141821", card2="#1B202B", line="#272D3B",
    text="#ECE8DF", muted="#8C91A1", gold="#D8B16A", on_gold="#1A1306",
    disp="#10141C", disp_text="#F6F2E9", disp_mut="#7E8497", entry="#0E1118",
    good="#3FCF9B", warn="#F2B84B", bad="#F0707A", info="#6DA8FF",
    num=("#1C2230", "#262E40", "#313B52", "#F3EFE6"),
    fn=("#141924", "#1D2433", "#272F43", "#B9BDCB"),
    op=("#2B2517", "#3A3120", "#4A3F29", "#E5C078"),
    clr=("#2C1B1F", "#3B2328", "#4A2C32", "#F28B95"),
    eq=("#D8B16A", "#E6C589", "#C39B52", "#1A1306"),
    mem=("#0F131B", "#181D29", "#212837", "#7F8598"),
)

LIGHT = dict(
    bg="#F2EFE9", side="#FFFFFF", card="#FFFFFF", card2="#F6F3EC", line="#E3DED2",
    text="#1D1B17", muted="#857F72", gold="#B88A3E", on_gold="#FFFFFF",
    disp="#15171E", disp_text="#F6F2E9", disp_mut="#8B90A2", entry="#FBFAF7",
    good="#119E70", warn="#C98A06", bad="#D8404B", info="#2D74DA",
    num=("#FFFFFF", "#F3EFE6", "#E8E2D4", "#1D1B17"),
    fn=("#EAE6DC", "#E0DACB", "#D4CDBA", "#4A463C"),
    op=("#F6EAD0", "#EFDDB8", "#E7CF9D", "#8A5F12"),
    clr=("#FBE3E5", "#F7D0D4", "#F1BDC3", "#C5303C"),
    eq=("#B88A3E", "#C79A4F", "#A67A31", "#FFFFFF"),
    mem=("#ECE8DE", "#E2DDCF", "#D7D0BE", "#857F72"),
)


# ------------------------------------------------------------------
# maths part (own small parser, no eval)
# ------------------------------------------------------------------
class CalcError(Exception):
    pass


NAMES = ["sin⁻¹", "cos⁻¹", "tan⁻¹", "sin", "cos", "tan", "ln", "log", "√", "abs",
         "mean", "max", "min", "mod", "Ans", "π", "e"]
FUNCS = ["sin⁻¹", "cos⁻¹", "tan⁻¹", "sin", "cos", "tan", "ln", "log", "√", "abs",
         "mean", "max", "min"]
OPS = "+−×÷^!(),"
OP_ALIAS = {"-": "−", "*": "×", "/": "÷"}


def tokenize(text):
    tokens = []
    i = 0
    while i < len(text):
        ch = text[i]
        if ch == " ":
            i += 1
        elif ch.isdigit() or ch == ".":
            j = i
            while j < len(text) and (text[j].isdigit() or text[j] == "."):
                j += 1
            word = text[i:j]
            if word.count(".") > 1 or word == ".":
                raise CalcError("Invalid number")
            tokens.append(("num", float(word) if "." in word else int(word)))
            i = j
        elif ch in OPS or ch in OP_ALIAS:
            tokens.append(("op", OP_ALIAS.get(ch, ch)))
            i += 1
        else:
            for name in NAMES:
                if text.startswith(name, i):
                    break
            else:
                raise CalcError("Invalid expression")
            if name == "mod":
                tokens.append(("op", "mod"))
            elif name in FUNCS:
                tokens.append(("func", name))
            else:
                tokens.append(("const", name))
            i += len(name)
    return tokens


def factorial(x):
    if x != int(x) or x < 0 or x > 170:
        raise ValueError
    return math.factorial(int(x))


def power(a, b):
    if abs(b) > 1000 and abs(a) > 1:
        raise OverflowError
    r = a ** b
    if isinstance(r, complex):
        raise ValueError
    return r


def call_function(name, args, angle):
    if name == "mean":
        return sum(args) / len(args)
    if name == "max":
        return max(args)
    if name == "min":
        return min(args)
    if len(args) != 1:
        raise CalcError("Invalid expression")
    x = args[0]
    if name in ("sin", "cos", "tan"):
        if angle == "DEG":
            if name == "tan" and (x - 90) % 180 == 0:
                raise ValueError
            x = math.radians(x)
        return round(getattr(math, name)(x), 12)
    if name in ("sin⁻¹", "cos⁻¹", "tan⁻¹"):
        f = {"sin⁻¹": math.asin, "cos⁻¹": math.acos, "tan⁻¹": math.atan}[name]
        r = f(x)
        return math.degrees(r) if angle == "DEG" else r
    if name == "ln":
        return math.log(x)
    if name == "log":
        return math.log10(x)
    if name == "√":
        return math.sqrt(x)
    return abs(x)


class Parser:
    def __init__(self, tokens, angle, ans):
        self.tokens = tokens
        self.pos = 0
        self.angle = angle
        self.ans = ans

    def peek(self):
        if self.pos < len(self.tokens):
            return self.tokens[self.pos]
        return None

    def take(self):
        tok = self.peek()
        self.pos += 1
        return tok

    def is_op(self, *ops):
        tok = self.peek()
        return tok is not None and tok[0] == "op" and tok[1] in ops

    def run(self):
        if not self.tokens:
            raise CalcError("")
        value = self.expr()
        if self.peek() is not None:
            raise CalcError("Invalid expression")
        return value

    def expr(self):
        value = self.term()
        while self.is_op("+", "−"):
            op = self.take()[1]
            right = self.term()
            value = value + right if op == "+" else value - right
        return value

    def term(self):
        value = self.unary()
        while True:
            if self.is_op("×", "÷", "mod"):
                op = self.take()[1]
                right = self.unary()
                if op == "×":
                    value = value * right
                elif right == 0:
                    raise CalcError("Cannot divide by 0")
                elif op == "÷":
                    value = value / right
                else:
                    value = value % right
            elif self.starts_value():
                value = value * self.unary()          # 2π, 3(4+1)
            else:
                return value

    def starts_value(self):
        tok = self.peek()
        if tok is None:
            return False
        return tok[0] in ("num", "func", "const") or tok == ("op", "(")

    def unary(self):
        if self.is_op("−"):
            self.take()
            return -self.unary()
        if self.is_op("+"):
            self.take()
            return self.unary()
        base = self.postfix()
        if self.is_op("^"):
            self.take()
            return power(base, self.unary())
        return base

    def postfix(self):
        value = self.primary()
        while self.is_op("!"):
            self.take()
            value = factorial(value)
        return value

    def primary(self):
        tok = self.take()
        if tok is None:
            raise CalcError("Invalid expression")
        kind, val = tok
        if kind == "num":
            return val
        if kind == "const":
            return {"π": math.pi, "e": math.e, "Ans": self.ans}[val]
        if kind == "func":
            if not self.is_op("("):
                raise CalcError("Invalid expression")
            self.take()
            args = [self.expr()]
            while self.is_op(","):
                self.take()
                args.append(self.expr())
            self.close()
            return call_function(val, args, self.angle)
        if tok == ("op", "("):
            value = self.expr()
            self.close()
            return value
        raise CalcError("Invalid expression")

    def close(self):
        if self.is_op(")"):
            self.take()
        elif self.peek() is not None:
            raise CalcError("Invalid expression")
        # bracket band nahi kiya to bhi chalega


def show(v):
    # number ko screen ke liye string banata hai
    if isinstance(v, int) and abs(v) < 10 ** 15:
        return str(v)
    v = float(v)
    if math.isnan(v) or math.isinf(v):
        raise OverflowError
    if v == int(v) and abs(v) < 1e15:
        return str(int(v))
    s = "%.12g" % v
    if "e" in s:
        a, b = s.split("e")
        s = "%s×10^%d" % (a, int(b))
    return "0" if s == "-0" else s


def calculate(text, angle="DEG", ans=0):
    try:
        value = Parser(tokenize(text), angle, ans).run()
        return value, show(value)
    except ZeroDivisionError:
        raise CalcError("Cannot divide by 0")
    except OverflowError:
        raise CalcError("Result too large")
    except (ValueError, RecursionError):
        raise CalcError("Invalid input")


# ------------------------------------------------------------------
# currency data
# ------------------------------------------------------------------
CURRENCIES = {
    "USD": "US Dollar", "EUR": "Euro", "GBP": "British Pound", "INR": "Indian Rupee",
    "JPY": "Japanese Yen", "AUD": "Australian Dollar", "CAD": "Canadian Dollar",
    "CHF": "Swiss Franc", "CNY": "Chinese Yuan", "SGD": "Singapore Dollar",
    "AED": "UAE Dirham", "SAR": "Saudi Riyal", "NZD": "New Zealand Dollar",
    "HKD": "Hong Kong Dollar", "KRW": "South Korean Won", "MXN": "Mexican Peso",
    "BRL": "Brazilian Real", "ZAR": "South African Rand", "SEK": "Swedish Krona",
    "NOK": "Norwegian Krone", "DKK": "Danish Krone", "PLN": "Polish Zloty",
    "TRY": "Turkish Lira", "THB": "Thai Baht", "IDR": "Indonesian Rupiah",
    "MYR": "Malaysian Ringgit", "PHP": "Philippine Peso", "VND": "Vietnamese Dong",
    "PKR": "Pakistani Rupee", "BDT": "Bangladeshi Taka", "LKR": "Sri Lankan Rupee",
    "NPR": "Nepalese Rupee", "EGP": "Egyptian Pound", "NGN": "Nigerian Naira",
    "KES": "Kenyan Shilling", "QAR": "Qatari Riyal", "KWD": "Kuwaiti Dinar",
    "ILS": "Israeli Shekel", "CZK": "Czech Koruna", "HUF": "Hungarian Forint",
}

# rough rates (per 1 USD). Sirf tab use hote hain jab internet nahi hota.
OFFLINE_RATES = {
    "USD": 1, "EUR": 0.86, "GBP": 0.76, "INR": 88.5, "JPY": 153, "AUD": 1.53,
    "CAD": 1.40, "CHF": 0.80, "CNY": 7.12, "SGD": 1.30, "AED": 3.673, "SAR": 3.75,
    "NZD": 1.75, "HKD": 7.78, "KRW": 1440, "MXN": 18.5, "BRL": 5.4, "ZAR": 17.3,
    "SEK": 9.5, "NOK": 10.1, "DKK": 6.45, "PLN": 3.65, "TRY": 42, "THB": 32.5,
    "IDR": 16600, "MYR": 4.2, "PHP": 59, "VND": 26300, "PKR": 281, "BDT": 122,
    "LKR": 302, "NPR": 141, "EGP": 47.5, "NGN": 1450, "KES": 129, "QAR": 3.64,
    "KWD": 0.307, "ILS": 3.25, "CZK": 21, "HUF": 335,
}


def read_er_api(data):
    if data.get("result") != "success":
        return None, ""
    return data["rates"], (data.get("time_last_update_utc") or "")[:16]


def read_frankfurter(data):
    rates = dict(data["rates"])
    rates["USD"] = 1.0
    return rates, data.get("date", "")


RATE_URLS = [
    ("https://open.er-api.com/v6/latest/USD", read_er_api),
    ("https://api.frankfurter.dev/v1/latest?base=USD", read_frankfurter),
]


# ------------------------------------------------------------------
# small custom widgets
# ------------------------------------------------------------------
def round_rect(c, x1, y1, x2, y2, r, **kw):
    pts = [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2,
           x2 - r, y2, x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]
    return c.create_polygon(pts, smooth=True, **kw)


class RoundButton(tk.Canvas):
    # colors = (normal, hover, pressed, text colour)
    def __init__(self, parent, text, command, colors, surface, font,
                 radius=12, width=60, height=40, border=None):
        tk.Canvas.__init__(self, parent, width=width, height=height, bg=surface,
                           highlightthickness=0, bd=0, cursor="hand2")
        self.text = text
        self.command = command
        self.colors = colors
        self.font = font
        self.radius = radius
        self.border = border
        self.state = 0
        self.bind("<Configure>", lambda e: self.draw())
        self.bind("<Enter>", lambda e: self.set_state(1))
        self.bind("<Leave>", lambda e: self.set_state(0))
        self.bind("<ButtonPress-1>", lambda e: self.set_state(2))
        self.bind("<ButtonRelease-1>", self.released)

    def set_state(self, s):
        self.state = s
        self.draw()

    def released(self, e):
        inside = 0 <= e.x <= self.winfo_width() and 0 <= e.y <= self.winfo_height()
        self.set_state(1 if inside else 0)
        if inside and self.command:
            self.command()

    def restyle(self, text=None, colors=None):
        if text is not None:
            self.text = text
        if colors is not None:
            self.colors = colors
        self.draw()

    def draw(self):
        try:
            self.delete("all")
            w = max(self.winfo_width(), 4)
            h = max(self.winfo_height(), 4)
            fill = self.colors[self.state]
            round_rect(self, 1, 1, w - 1, h - 1, min(self.radius, h // 2),
                       fill=fill, outline=self.border or fill)
            self.create_text(w / 2, h / 2, text=self.text, fill=self.colors[3], font=self.font)
        except tk.TclError:
            pass            # widget already destroyed


class Card(tk.Canvas):
    # rounded panel, widgets go inside card.inner
    def __init__(self, parent, color, surface, radius=18, border=None, **kw):
        tk.Canvas.__init__(self, parent, bg=surface, highlightthickness=0, bd=0, **kw)
        self.color = color
        self.radius = radius
        self.border = border
        self.pad = max(6, radius // 2)
        self.inner = tk.Frame(self, bg=color)
        self.win = self.create_window(self.pad, self.pad, window=self.inner, anchor="nw")
        self.bind("<Configure>", self.resize)

    def resize(self, e):
        self.delete("bg")
        round_rect(self, 1, 1, e.width - 1, e.height - 1, self.radius, fill=self.color,
                   outline=self.border or self.color, tags="bg")
        self.tag_lower("bg")
        self.itemconfigure(self.win, width=max(e.width - 2 * self.pad, 1),
                           height=max(e.height - 2 * self.pad, 1))


class NavItem(tk.Canvas):
    # sidebar button: icon + small label
    def __init__(self, parent, label, icon, command, C, scale, active=False):
        tk.Canvas.__init__(self, parent, width=int(96 * scale), height=int(80 * scale),
                           bg=C["side"], highlightthickness=0, cursor="hand2")
        self.label, self.icon, self.command, self.C = label, icon, command, C
        self.scale = scale
        self.active = active
        self.hover = False
        self.bind("<Configure>", lambda e: self.draw())
        self.bind("<Enter>", lambda e: self.set_hover(True))
        self.bind("<Leave>", lambda e: self.set_hover(False))
        self.bind("<ButtonRelease-1>", lambda e: command())

    def set_hover(self, value):
        self.hover = value
        self.draw()

    def set_active(self, value):
        self.active = value
        self.draw()

    def draw(self):
        try:
            self.delete("all")
        except tk.TclError:
            return
        C, s = self.C, self.scale
        w, h = self.winfo_width(), self.winfo_height()
        if self.active:
            col = C["gold"]
        else:
            col = C["text"] if self.hover else C["muted"]
        if self.active:
            round_rect(self, 12 * s, 6 * s, w - 12 * s, h - 6 * s, 14 * s, fill=C["card2"], outline=C["card2"])
            self.create_rectangle(0, 20 * s, 4 * s, h - 20 * s, fill=C["gold"], outline=C["gold"])
        cx, cy = w / 2, h / 2 - 9 * s
        if self.icon == "calc":
            round_rect(self, cx - 13 * s, cy - 15 * s, cx + 13 * s, cy + 15 * s, 5 * s, fill="", outline=col, width=2)
            self.create_rectangle(cx - 8 * s, cy - 10 * s, cx + 8 * s, cy - 5 * s, fill=col, outline=col)
            for dx in (-7, 0, 7):
                for dy in (2, 9):
                    self.create_oval(cx + (dx - 2) * s, cy + (dy - 2) * s, cx + (dx + 2) * s,
                                     cy + (dy + 2) * s, fill=col, outline=col)
        elif self.icon == "bmi":
            self.create_arc(cx - 15 * s, cy - 13 * s, cx + 15 * s, cy + 17 * s, start=15, extent=150,
                            style="arc", outline=col, width=3)
            self.create_line(cx, cy + 4 * s, cx + 7 * s, cy - 7 * s, fill=col, width=2)
            self.create_oval(cx - 3 * s, cy + 1 * s, cx + 3 * s, cy + 7 * s, fill=col, outline=col)
        elif self.icon == "money":
            self.create_line(cx - 14 * s, cy - 6 * s, cx + 14 * s, cy - 6 * s, fill=col, width=2, arrow="last")
            self.create_line(cx + 14 * s, cy + 7 * s, cx - 14 * s, cy + 7 * s, fill=col, width=2, arrow="last")
        else:
            self.create_text(cx, cy, text=self.icon, fill=col, font=("Segoe UI Symbol", int(17 * s * 0.75)))
        self.create_text(cx, h - 20 * s, text=self.label, fill=col, font=("Segoe UI", 9, "bold"))


# ------------------------------------------------------------------
# the app
# ------------------------------------------------------------------
BACKSPACE_TOKENS = ["sin⁻¹(", "cos⁻¹(", "tan⁻¹(", "sin(", "cos(", "tan(", "ln(", "log(",
                    "√(", "abs(", "mean(", "max(", "min(", " mod ", "Ans"]
BIN_OPS = ["+", "−", "×", "÷", "^", "mod"]

SCI_KEYS = [
    [("sin", "sin("), ("cos", "cos("), ("tan", "tan("), ("Ans", "Ans")],
    [("sin⁻¹", "sin⁻¹("), ("cos⁻¹", "cos⁻¹("), ("tan⁻¹", "tan⁻¹("), ("π", "π")],
    [("ln", "ln("), ("log", "log("), ("e", "e"), ("mod", " mod ")],
    [("x²", "^2"), ("xʸ", "^"), ("√x", "√("), ("n!", "!")],
    [("(", "("), (")", ")"), ("|x|", "abs("), ("1/x", "1÷(")],
    [("mean", "mean("), ("max", "max("), ("min", "min("), (",", ",")],
]

MAIN_KEYS = [
    [("MC", "mc", "mem"), ("MR", "mr", "mem"), ("M+", "m+", "mem"), ("M−", "m-", "mem")],
    [("C", "clear", "clr"), ("⌫", "back", "clr"), ("±", "neg", "op"), ("÷", "÷", "op")],
    [("7", "7", "num"), ("8", "8", "num"), ("9", "9", "num"), ("×", "×", "op")],
    [("4", "4", "num"), ("5", "5", "num"), ("6", "6", "num"), ("−", "−", "op")],
    [("1", "1", "num"), ("2", "2", "num"), ("3", "3", "num"), ("+", "+", "op")],
    [("0", "0", "num"), (".", ".", "num"), ("=", "eval", "eq")],
]


class App:
    def __init__(self, root):
        self.root = root
        root.title("Advanced Calculator")
        self.scale = max(root.winfo_fpixels("1i") / 96.0, 1.0)
        sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
        w = min(self.px(1260), sw - self.px(60))
        h = min(self.px(820), sh - self.px(110))
        root.geometry("%dx%d+%d+%d" % (w, h, (sw - w) // 2, max((sh - h) // 3, 0)))
        root.minsize(min(self.px(1060), w), min(self.px(700), h))

        families = set(tkfont.families(root))
        self.family = "TkDefaultFont"
        for name in ("Segoe UI", "SF Pro Display", "Helvetica Neue", "Inter", "Ubuntu", "DejaVu Sans", "Arial"):
            if name in families:
                self.family = name
                break
        self.mono = "TkFixedFont"
        for name in ("Cascadia Mono", "Consolas", "Menlo", "DejaVu Sans Mono", "Courier New"):
            if name in families:
                self.mono = name
                break

        self.theme = "dark"
        self.C = DARK
        self.tab = "calc"

        # calculator state
        self.expr = ""
        self.sub = ""
        self.error = ""
        self.just_done = False
        self.angle = "DEG"
        self.memory = 0
        self.ans = 0
        self.history = []
        self.show_sci = True
        self.show_hist = True

        # bmi state
        self.unit = tk.StringVar(value="metric")
        self.kg, self.cm = tk.StringVar(), tk.StringVar()
        self.lb, self.ft, self.inch = tk.StringVar(), tk.StringVar(), tk.StringVar()
        self.bmi_data = None

        # currency state
        self.amount = tk.StringVar(value="100")
        self.from_cur = tk.StringVar(value=self.cur_name("USD"))
        self.to_cur = tk.StringVar(value=self.cur_name("INR"))
        self.rates = dict(OFFLINE_RATES)
        self.rate_note = ("Offline rates (approximate). Press “Update live rates”.", "warn")
        self.rate_live = False
        self.fetching = False
        self.rate_queue = queue.Queue()

        # live update when the user types
        for var in (self.unit, self.kg, self.cm, self.lb, self.ft, self.inch):
            var.trace_add("write", lambda *a: self.bmi_live())
        for var in (self.amount, self.from_cur, self.to_cur):
            var.trace_add("write", lambda *a: self.convert())

        root.bind_all("<Key>", self.on_key)
        self.build()
        self.fetch_rates()

    # ---------- small helpers ----------
    def px(self, n):
        return int(n * self.scale)

    def f(self, size, bold=False, mono=False):
        return (self.mono if mono else self.family, size, "bold" if bold else "normal")

    def cur_name(self, code):
        return "%s – %s" % (code, CURRENCIES[code])

    # ---------- whole window ----------
    def build(self):
        for w in self.root.winfo_children():
            w.destroy()
        C = self.C
        self.root.configure(bg=C["bg"])
        self.set_styles()

        side = tk.Frame(self.root, bg=C["side"], width=self.px(96))
        side.pack(side="left", fill="y")
        side.pack_propagate(False)
        tk.Frame(self.root, bg=C["line"], width=1).pack(side="left", fill="y")
        self.make_sidebar(side)

        self.content = tk.Frame(self.root, bg=C["bg"])
        self.content.pack(side="left", fill="both", expand=True, padx=self.px(28), pady=(self.px(22), self.px(26)))
        self.content.grid_rowconfigure(0, weight=1)
        self.content.grid_columnconfigure(0, weight=1)

        self.pages = {
            "calc": self.build_calc(self.content),
            "bmi": self.build_bmi(self.content),
            "cur": self.build_currency(self.content),
        }
        for page in self.pages.values():
            page.grid(row=0, column=0, sticky="nsew")
        self.go(self.tab)
        self.refresh()
        self.refresh_history()
        self.layout_calc()
        self.bmi_live()
        self.convert()
        self.show_rate_note()

    def set_styles(self):
        C = self.C
        st = ttk.Style()
        st.theme_use("clam")
        st.configure("Gold.TCombobox", fieldbackground=C["entry"], background=C["card2"],
                     foreground=C["text"], arrowcolor=C["gold"], bordercolor=C["line"],
                     lightcolor=C["entry"], darkcolor=C["entry"], padding=self.px(9))
        st.map("Gold.TCombobox",
               fieldbackground=[("readonly", C["entry"])],
               foreground=[("readonly", C["text"])],
               selectbackground=[("readonly", C["entry"])],
               selectforeground=[("readonly", C["text"])],
               bordercolor=[("focus", C["gold"])])
        r = self.root
        r.option_add("*TCombobox*Listbox.background", C["card"])
        r.option_add("*TCombobox*Listbox.foreground", C["text"])
        r.option_add("*TCombobox*Listbox.selectBackground", C["gold"])
        r.option_add("*TCombobox*Listbox.selectForeground", C["on_gold"])
        r.option_add("*TCombobox*Listbox.font", self.f(11))

    def make_sidebar(self, side):
        C = self.C
        logo = tk.Canvas(side, width=self.px(46), height=self.px(46), bg=C["side"], highlightthickness=0)
        logo.pack(pady=(self.px(24), self.px(26)))
        round_rect(logo, 1, 1, self.px(45), self.px(45), self.px(14), fill=C["gold"], outline=C["gold"])
        logo.create_text(self.px(23), self.px(23), text="∑", fill=C["on_gold"], font=self.f(18, True))

        self.nav = {}
        for key, label, icon in (("calc", "Calculator", "calc"), ("bmi", "BMI", "bmi"), ("cur", "Currency", "money")):
            item = NavItem(side, label, icon, lambda k=key: self.go(k), C, self.scale)
            item.pack(pady=self.px(3))
            self.nav[key] = item

        icon = "☀" if self.theme == "dark" else "☾"
        label = "Light" if self.theme == "dark" else "Dark"
        theme = NavItem(side, label, icon, self.switch_theme, C, self.scale)
        theme.pack(side="bottom", pady=(0, self.px(18)))

    def go(self, key):
        self.tab = key
        for k, item in self.nav.items():
            item.set_active(k == key)
        self.pages[key].tkraise()

    def switch_theme(self):
        if self.theme == "dark":
            self.theme, self.C = "light", LIGHT
        else:
            self.theme, self.C = "dark", DARK
        self.root.after(10, self.build)

    def page_title(self, parent, title, subtitle):
        C = self.C
        box = tk.Frame(parent, bg=C["bg"])
        tk.Label(box, text=title, bg=C["bg"], fg=C["text"], font=self.f(21, True), anchor="w").pack(anchor="w")
        tk.Label(box, text=subtitle, bg=C["bg"], fg=C["muted"], font=self.f(10), anchor="w").pack(anchor="w")
        return box

    def make_entry(self, parent, var, size=13):
        C = self.C
        box = tk.Frame(parent, bg=C["entry"], highlightbackground=C["line"], highlightthickness=1)
        entry = tk.Entry(box, textvariable=var, bd=0, relief="flat", bg=C["entry"], fg=C["text"],
                         insertbackground=C["gold"], font=self.f(size), highlightthickness=0)
        entry.pack(fill="x", padx=self.px(12), pady=self.px(9))
        entry.bind("<FocusIn>", lambda e: box.config(highlightbackground=C["gold"], highlightthickness=2))
        entry.bind("<FocusOut>", lambda e: box.config(highlightbackground=C["line"], highlightthickness=1))
        return box, entry

    def segmented(self, parent, items, current, command, width, surface):
        # small switch with 2-3 options, returns frame and dict of buttons
        C = self.C
        frame = tk.Frame(parent, bg=C["card2"])
        buttons = {}
        for key, text in items:
            on = key == current
            colors = C["eq"] if on else (C["card2"], C["line"], C["line"], C["muted"])
            b = RoundButton(frame, text, lambda k=key: command(k), colors, C["card2"],
                            self.f(10, True), radius=self.px(10), width=self.px(width), height=self.px(34))
            b.pack(side="left", padx=self.px(3), pady=self.px(3))
            buttons[key] = b
        return frame, buttons

    # ---------- calculator page ----------
    def build_calc(self, parent):
        C = self.C
        px = self.px
        page = tk.Frame(parent, bg=C["bg"])
        page.grid_columnconfigure(0, weight=1)
        page.grid_rowconfigure(1, weight=1)
        self.calc_page = page

        # top bar: title on left, switches on right
        top = tk.Frame(page, bg=C["bg"])
        top.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, px(16)))
        self.page_title(top, "Calculator", "Scientific functions, memory and history").pack(side="left")

        right = tk.Frame(top, bg=C["bg"])
        right.pack(side="right")
        self.btn_hist = RoundButton(right, "History", self.toggle_hist, C["op"], C["bg"], self.f(10, True),
                                    radius=px(12), width=px(96), height=px(38))
        self.btn_hist.pack(side="right", padx=(px(8), 0))
        self.btn_sci = RoundButton(right, "Scientific", self.toggle_sci, C["op"], C["bg"], self.f(10, True),
                                   radius=px(12), width=px(106), height=px(38))
        self.btn_sci.pack(side="right", padx=(px(8), 0))
        seg, self.angle_btns = self.segmented(right, [("DEG", "DEG"), ("RAD", "RAD")], self.angle,
                                              self.set_angle, 56, C["bg"])
        seg.pack(side="right")

        # left side: display + keys
        main = tk.Frame(page, bg=C["bg"])
        main.grid(row=1, column=0, sticky="nsew")
        main.grid_columnconfigure(0, weight=1)
        main.grid_rowconfigure(1, weight=1)
        self.main_area = main

        disp = Card(main, C["disp"], C["bg"], radius=px(22), height=px(196), border=C["line"])
        disp.grid(row=0, column=0, sticky="ew", pady=(0, px(16)))
        d = disp.inner
        row = tk.Frame(d, bg=C["disp"])
        row.pack(fill="x", padx=px(20), pady=(px(12), 0))
        self.lbl_mem = tk.Label(row, text="", bg=C["disp"], fg=C["gold"], font=self.f(9, True))
        self.lbl_mem.pack(side="left")
        self.btn_copy = RoundButton(row, "Copy", self.copy_result, (C["card2"], C["line"], C["line"], C["muted"]),
                                    C["disp"], self.f(9, True), radius=px(10), width=px(68), height=px(28))
        self.btn_copy.pack(side="right")
        self.lbl_sub = tk.Label(row, text="", bg=C["disp"], fg=C["disp_mut"], font=self.f(11), anchor="e")
        self.lbl_sub.pack(side="right", fill="x", expand=True, padx=px(10))
        self.lbl_main = tk.Label(d, text="0", bg=C["disp"], fg=C["disp_text"], font=self.f(36, True), anchor="e")
        self.lbl_main.pack(fill="x", padx=px(20), pady=(px(4), 0))
        self.lbl_prev = tk.Label(d, text="", bg=C["disp"], fg=C["gold"], font=self.f(13), anchor="e")
        self.lbl_prev.pack(fill="x", padx=px(20))

        pads = tk.Frame(main, bg=C["bg"])
        pads.grid(row=1, column=0, sticky="nsew")
        self.pads = pads
        pads.grid_rowconfigure(0, weight=1)
        pads.grid_columnconfigure(1, minsize=px(16))
        pads.grid_columnconfigure(2, weight=1)

        self.sci_frame = tk.Frame(pads, bg=C["bg"])
        self.sci_frame.grid(row=0, column=0, sticky="nsew")
        self.make_keys(self.sci_frame, [[(a, b, "fn") for a, b in row] for row in SCI_KEYS])
        std = tk.Frame(pads, bg=C["bg"])
        std.grid(row=0, column=2, sticky="nsew")
        self.make_keys(std, MAIN_KEYS)

        # history on the right
        hist = Card(page, C["card"], C["bg"], radius=px(22), border=C["line"])
        self.hist_card = hist
        h = hist.inner
        head = tk.Frame(h, bg=C["card"])
        head.pack(fill="x", padx=px(18), pady=(px(16), px(4)))
        tk.Label(head, text="History", bg=C["card"], fg=C["text"], font=self.f(14, True)).pack(side="left")
        RoundButton(head, "Clear", self.clear_history, (C["card2"], C["line"], C["line"], C["muted"]),
                    C["card"], self.f(9, True), radius=px(10), width=px(62), height=px(28)).pack(side="right")
        self.txt_hist = tk.Text(h, bg=C["card"], fg=C["text"], bd=0, highlightthickness=0, wrap="word",
                                cursor="arrow", state="disabled", width=20, padx=px(10), pady=px(4),
                                selectbackground=C["card"], inactiveselectbackground=C["card"])
        self.txt_hist.pack(fill="both", expand=True, padx=px(8), pady=(px(4), 0))
        self.txt_hist.tag_configure("expr", justify="right", foreground=C["muted"], font=self.f(10), spacing1=px(12))
        self.txt_hist.tag_configure("res", justify="right", foreground=C["text"], font=self.f(16, True), spacing3=px(6))
        self.txt_hist.tag_configure("empty", justify="center", foreground=C["muted"], font=self.f(10), spacing1=px(60))
        self.txt_hist.bind("<Button-1>", self.history_click)
        tk.Label(h, text="Click an entry to use it again", bg=C["card"], fg=C["muted"],
                 font=self.f(9)).pack(pady=(px(4), px(14)))
        return page

    def make_keys(self, frame, rows):
        C = self.C
        for c in range(4):
            frame.grid_columnconfigure(c, weight=1, uniform="col")
        for r, row in enumerate(rows):
            frame.grid_rowconfigure(r, weight=1, uniform="row")
            col = 0
            for label, action, kind in row:
                size = 16 if kind in ("num", "op", "eq") else 11 if kind == "mem" else 12
                b = RoundButton(frame, label, lambda a=action: self.press(a), C[kind], C["bg"],
                                self.f(size, kind in ("num", "op", "eq", "clr")), radius=self.px(15),
                                width=self.px(50), height=self.px(44))
                span = 2 if label == "=" else 1
                b.grid(row=r, column=col, columnspan=span, sticky="nsew", padx=self.px(4), pady=self.px(4))
                col += span

    def layout_calc(self):
        C = self.C
        px = self.px
        # scientific panel
        if self.show_sci:
            self.sci_frame.grid()
            self.pads.grid_columnconfigure(0, weight=1)
            self.pads.grid_columnconfigure(1, minsize=px(16))
        else:
            self.sci_frame.grid_remove()
            self.pads.grid_columnconfigure(0, weight=0)
            self.pads.grid_columnconfigure(1, minsize=0)
        # history panel
        if self.show_hist:
            self.hist_card.grid(row=1, column=1, sticky="nsew", padx=(px(20), 0))
            self.calc_page.grid_columnconfigure(1, minsize=px(300))
        else:
            self.hist_card.grid_remove()
            self.calc_page.grid_columnconfigure(1, minsize=0)
        self.btn_sci.restyle(colors=C["op"] if self.show_sci else C["fn"])
        self.btn_hist.restyle(colors=C["op"] if self.show_hist else C["fn"])
        for k, b in self.angle_btns.items():
            b.restyle(colors=C["eq"] if k == self.angle else (C["card2"], C["line"], C["line"], C["muted"]))

    def toggle_sci(self):
        self.show_sci = not self.show_sci
        self.layout_calc()

    def toggle_hist(self):
        self.show_hist = not self.show_hist
        self.layout_calc()

    def set_angle(self, mode):
        self.angle = mode
        self.layout_calc()
        self.refresh()

    # ---------- calculator logic ----------
    def pretty(self, expr):
        return re.sub(r"(?<=[\d)πeAs!])\s*([+−×÷])\s*", r" \1 ", expr)

    def refresh(self):
        C = self.C
        text = self.pretty(self.expr) or "0"
        n = len(text)
        size = 36 if n <= 13 else 30 if n <= 18 else 23 if n <= 26 else 18
        preview = ""
        if self.expr and not self.just_done and not self.error:
            try:
                value, txt = calculate(self.expr, self.angle, self.ans)
                if txt != self.expr.strip():
                    preview = "= " + txt
            except CalcError:
                pass
        try:
            self.lbl_main.config(text=text, font=self.f(size, True))
            self.lbl_mem.config(text="M  " + show(self.memory) if self.memory else "")
            if self.error:
                self.lbl_sub.config(text=self.error, fg=C["bad"])
            else:
                self.lbl_sub.config(text=self.sub, fg=C["disp_mut"])
            self.lbl_prev.config(text=preview)
        except tk.TclError:
            pass

    def refresh_history(self):
        t = self.txt_hist
        t.config(state="normal")
        t.delete("1.0", "end")
        if not self.history:
            t.insert("end", "Nothing here yet", "empty")
        for i in range(len(self.history) - 1, -1, -1):
            expr, res = self.history[i]
            tag = "h_%d" % i
            t.insert("end", self.pretty(expr) + " =\n", ("expr", tag))
            t.insert("end", res + "\n", ("res", tag))
        t.config(state="disabled")

    def history_click(self, e):
        index = self.txt_hist.index("@%d,%d" % (e.x, e.y))
        for tag in self.txt_hist.tag_names(index):
            if tag.startswith("h_"):
                self.expr = self.history[int(tag[2:])][0]
                self.just_done = False
                self.error = ""
                self.sub = ""
                self.refresh()
        return "break"

    def clear_history(self):
        self.history = []
        self.refresh_history()

    def copy_result(self):
        text = ""
        if self.just_done:
            text = self.expr
        elif self.expr:
            try:
                text = calculate(self.expr, self.angle, self.ans)[1]
            except CalcError:
                text = self.expr
        if not text:
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self.btn_copy.restyle(text="Copied")
        self.root.after(1200, lambda: self.btn_copy.restyle(text="Copy"))

    def press(self, key):
        try:
            self.handle(key)
        except CalcError as e:
            self.error = str(e) or "Invalid expression"
        self.refresh()

    def handle(self, key):
        if key == "clear":
            self.expr, self.sub, self.error, self.just_done = "", "", "", False
        elif key == "back":
            self.backspace()
        elif key == "eval":
            self.equals()
        elif key == "neg":
            self.negate()
        elif key in ("mc", "mr", "m+", "m-"):
            self.memory_key(key)
        else:
            self.add(key)

    def backspace(self):
        if self.just_done:
            self.expr, self.sub, self.just_done = "", "", False
            return
        self.error = ""
        for t in BACKSPACE_TOKENS:
            if self.expr.endswith(t):
                self.expr = self.expr[:-len(t)]
                return
        self.expr = self.expr[:-1]

    def equals(self):
        if not self.expr.strip():
            return
        value, text = calculate(self.expr, self.angle, self.ans)
        self.history.append((self.expr, text))
        self.history = self.history[-100:]
        self.sub = self.pretty(self.expr) + " ="
        self.expr = text
        self.ans = value
        self.just_done = True
        self.error = ""
        self.refresh_history()

    def negate(self):
        self.error = ""
        e = self.expr
        if not e:
            self.expr = "−"
        elif re.fullmatch(r"−?[\d.]+", e):
            self.expr = e[1:] if e[0] == "−" else "−" + e
        elif e.startswith("−(") and e.endswith(")"):
            self.expr = e[2:-1]
        else:
            self.expr = "−(" + e + ")"
        self.just_done = False

    def memory_key(self, key):
        if key == "mc":
            self.memory = 0
        elif key == "mr":
            self.add(show(self.memory))
        else:
            value = calculate(self.expr, self.angle, self.ans)[0] if self.expr.strip() else self.ans
            self.memory = self.memory + value if key == "m+" else self.memory - value

    def add(self, tok):
        self.error = ""
        name = tok.strip()
        is_op = name in BIN_OPS
        is_after = tok in ("!", "^2", ")", ",")
        if self.just_done:
            self.just_done = False
            if not (is_op or is_after):
                self.expr, self.sub = "", ""
        if tok == ".":
            if "." in re.search(r"[\d.]*$", self.expr).group():
                return
            if not re.search(r"\d$", self.expr):
                tok = "0."
        if is_op:
            cur = self.expr.rstrip()
            if not cur or cur.endswith("("):
                if name != "−":
                    return
            else:
                last = None
                for o in ("mod", "+", "−", "×", "÷", "^"):
                    if cur.endswith(o):
                        last = o
                        break
                if last and not (name == "−" and last in ("×", "÷", "^", "mod")):
                    self.expr = cur[:-len(last)].rstrip()      # replace the old operator
                    if not self.expr and name != "−":
                        return
        if is_after and tok != ")" and (not self.expr or self.expr.rstrip().endswith("(")):
            return
        self.expr += tok

    def on_key(self, e):
        if self.tab != "calc":
            return
        if isinstance(self.root.focus_get(), (tk.Entry, ttk.Combobox)):
            return
        keymap = {"*": "×", "/": "÷", "-": "−", "+": "+", "^": "^", "(": "(", ")": ")",
                  ",": ",", "!": "!", ".": ".", "%": " mod "}
        if e.keysym in ("Return", "KP_Enter") or e.char == "=":
            self.press("eval")
        elif e.keysym == "BackSpace":
            self.press("back")
        elif e.keysym in ("Escape", "Delete"):
            self.press("clear")
        elif e.char and e.char.isdigit():
            self.press(e.char)
        elif e.char in keymap:
            self.press(keymap[e.char])

    # ---------- BMI page ----------
    def build_bmi(self, parent):
        C = self.C
        px = self.px
        page = tk.Frame(parent, bg=C["bg"])
        page.grid_columnconfigure(0, weight=5, uniform="b")
        page.grid_columnconfigure(1, weight=6, uniform="b")
        page.grid_rowconfigure(1, weight=1)
        self.page_title(page, "BMI", "Body Mass Index with a healthy weight range").grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, px(16)))

        # left card: inputs
        left = Card(page, C["card"], C["bg"], radius=px(22), border=C["line"])
        left.grid(row=1, column=0, sticky="nsew", padx=(0, px(10)))
        a = left.inner
        pad = px(28)
        tk.Label(a, text="Your details", bg=C["card"], fg=C["text"], font=self.f(15, True),
                 anchor="w").pack(fill="x", padx=pad, pady=(px(24), px(14)))
        seg, self.unit_btns = self.segmented(a, [("metric", "Metric"), ("imperial", "Imperial")],
                                             self.unit.get(), self.unit.set, 120, C["card"])
        seg.pack(anchor="w", padx=pad)

        form = tk.Frame(a, bg=C["card"])
        form.pack(fill="x", padx=pad, pady=(px(18), 0))
        self.metric_form = tk.Frame(form, bg=C["card"])
        self.imperial_form = tk.Frame(form, bg=C["card"])
        for frame in (self.metric_form, self.imperial_form):
            frame.grid(row=0, column=0, sticky="ew")
        form.grid_columnconfigure(0, weight=1)

        self.field(self.metric_form, "Weight (kg)", [self.kg], 0)
        self.field(self.metric_form, "Height (cm)", [self.cm], 1)
        self.field(self.imperial_form, "Weight (lb)", [self.lb], 0)
        self.field(self.imperial_form, "Height (ft / in)", [self.ft, self.inch], 1)

        RoundButton(a, "Calculate BMI", self.calc_bmi, C["eq"], C["card"], self.f(12, True),
                    radius=px(15), width=px(100), height=px(50)).pack(fill="x", padx=pad, pady=(px(22), px(8)))
        RoundButton(a, "Reset", self.reset_bmi, (C["card2"], C["line"], C["line"], C["muted"]), C["card"],
                    self.f(11, True), radius=px(15), width=px(100), height=px(42)).pack(fill="x", padx=pad)
        tk.Label(a, text="Result updates while you type.", bg=C["card"], fg=C["muted"],
                 font=self.f(9)).pack(pady=(px(12), 0))

        # right card: result
        right = Card(page, C["card"], C["bg"], radius=px(22), border=C["line"])
        right.grid(row=1, column=1, sticky="nsew", padx=(px(10), 0))
        r = right.inner
        tk.Label(r, text="Your BMI", bg=C["card"], fg=C["muted"], font=self.f(11, True)).pack(pady=(px(26), 0))
        self.lbl_bmi = tk.Label(r, text="––", bg=C["card"], fg=C["text"], font=self.f(58, True))
        self.lbl_bmi.pack()
        self.lbl_cat = tk.Label(r, text="Enter weight and height", bg=C["card"], fg=C["muted"],
                                font=self.f(12, True), padx=px(16), pady=px(5))
        self.lbl_cat.pack(pady=(0, px(14)))
        self.gauge = tk.Canvas(r, bg=C["card"], highlightthickness=0, height=px(84))
        self.gauge.pack(fill="x", padx=px(34))
        self.gauge.bind("<Configure>", lambda e: self.draw_gauge())
        self.lbl_range = tk.Label(r, text="", bg=C["card"], fg=C["text"], font=self.f(11))
        self.lbl_range.pack(pady=(px(4), px(14)))

        self.legend = []
        legend = tk.Frame(r, bg=C["card"])
        legend.pack(fill="x", padx=px(34), pady=(0, px(20)))
        for key, name, rng in (("info", "Underweight", "below 18.5"), ("good", "Normal weight", "18.5 – 24.9"),
                               ("warn", "Overweight", "25 – 29.9"), ("bad", "Obese", "30 and above")):
            row = tk.Frame(legend, bg=C["card"])
            row.pack(fill="x", pady=px(2))
            dot = tk.Canvas(row, width=px(14), height=px(14), bg=C["card"], highlightthickness=0)
            dot.create_oval(2, 2, px(12), px(12), fill=C[key], outline=C[key])
            dot.pack(side="left", padx=(px(10), px(10)), pady=px(8))
            n = tk.Label(row, text=name, bg=C["card"], fg=C["text"], font=self.f(11), anchor="w")
            n.pack(side="left")
            g = tk.Label(row, text=rng, bg=C["card"], fg=C["muted"], font=self.f(10))
            g.pack(side="right", padx=px(10))
            self.legend.append((row, dot, n, g))
        return page

    def field(self, parent, label, variables, row):
        C = self.C
        parent.grid_columnconfigure(0, weight=1)
        tk.Label(parent, text=label, bg=C["card"], fg=C["muted"], font=self.f(10, True),
                 anchor="w").grid(row=row * 2, column=0, sticky="w", pady=(self.px(8), self.px(4)))
        cell = tk.Frame(parent, bg=C["card"])
        cell.grid(row=row * 2 + 1, column=0, sticky="ew")
        for i, var in enumerate(variables):
            box, entry = self.make_entry(cell, var)
            box.pack(side="left", fill="x", expand=True, padx=(0, self.px(10)) if i == 0 and len(variables) > 1 else 0)
            entry.bind("<Return>", lambda e: self.calc_bmi())

    def read_bmi(self):
        # returns (bmi, low, high, unit) or None if inputs are not valid
        try:
            if self.unit.get() == "metric":
                kg, cm = float(self.kg.get()), float(self.cm.get())
                if not (2 <= kg <= 500 and 50 <= cm <= 272):
                    return None
                m2 = (cm / 100) ** 2
                return kg / m2, 18.5 * m2, 24.9 * m2, "kg"
            lb = float(self.lb.get())
            inches = float(self.ft.get() or 0) * 12 + float(self.inch.get() or 0)
            if not (4 <= lb <= 1100 and 20 <= inches <= 107):
                return None
            return 703 * lb / inches ** 2, 18.5 * inches ** 2 / 703, 24.9 * inches ** 2 / 703, "lb"
        except ValueError:
            return None

    def bmi_live(self):
        # runs every time a field changes
        C = self.C
        try:
            unit = self.unit.get()
            for k, b in self.unit_btns.items():
                b.restyle(colors=C["eq"] if k == unit else (C["card2"], C["line"], C["line"], C["muted"]))
            (self.metric_form if unit == "metric" else self.imperial_form).tkraise()
        except (tk.TclError, AttributeError):
            return
        self.bmi_data = self.read_bmi()
        self.show_bmi()

    def calc_bmi(self):
        self.bmi_live()
        if self.bmi_data is None:
            self.lbl_cat.config(text="Please enter valid weight and height", fg=self.C["bad"], bg=self.C["card"])

    def reset_bmi(self):
        for v in (self.kg, self.cm, self.lb, self.ft, self.inch):
            v.set("")

    def bmi_category(self, b):
        if b < 18.5:
            return "Underweight", "info", 0
        if b < 25:
            return "Normal weight", "good", 1
        if b < 30:
            return "Overweight", "warn", 2
        return "Obese", "bad", 3

    def show_bmi(self):
        C = self.C
        try:
            if self.bmi_data is None:
                self.lbl_bmi.config(text="––", fg=C["text"])
                self.lbl_cat.config(text="Enter weight and height", fg=C["muted"], bg=C["card"])
                self.lbl_range.config(text="")
                active = -1
            else:
                bmi, low, high, unit = self.bmi_data
                name, key, active = self.bmi_category(bmi)
                self.lbl_bmi.config(text="%.1f" % bmi, fg=C[key])
                self.lbl_cat.config(text=name, fg=C["on_gold"] if self.theme == "dark" else "#FFFFFF", bg=C[key])
                self.lbl_range.config(text="Healthy weight for your height:  %.1f – %.1f %s" % (low, high, unit))
            for i, (row, dot, n, g) in enumerate(self.legend):
                bg = C["card2"] if i == active else C["card"]
                for w in (row, dot, n, g):
                    w.config(bg=bg)
                n.config(font=self.f(11, i == active))
            self.draw_gauge()
        except tk.TclError:
            pass

    def draw_gauge(self):
        g = self.gauge
        C = self.C
        px = self.px
        try:
            g.delete("all")
        except tk.TclError:
            return
        w = g.winfo_width()
        if w < 60:
            return
        x0, x1, y0, y1 = px(6), w - px(6), px(36), px(52)
        low, high = 12.0, 40.0

        def pos(v):
            return x0 + (min(max(v, low), high) - low) / (high - low) * (x1 - x0)

        parts = [(low, 18.5, C["info"]), (18.5, 25, C["good"]), (25, 30, C["warn"]), (30, high, C["bad"])]
        for i, (a, b, color) in enumerate(parts):
            xa = pos(a) + (px(2) if i else 0)
            xb = pos(b) - (px(2) if i < 3 else 0)
            g.create_rectangle(xa, y0, xb, y1, fill=color, outline=color)
        for v in (18.5, 25, 30):
            g.create_text(pos(v), y1 + px(15), text="%g" % v, fill=C["muted"], font=self.f(9))
        if self.bmi_data is not None:
            x = pos(self.bmi_data[0])
            g.create_polygon(x - px(8), px(8), x + px(8), px(8), x, px(26), fill=C["gold"], outline=C["gold"])
            g.create_line(x, px(26), x, y1 + px(4), fill=C["gold"], width=2)

    # ---------- currency page ----------
    def build_currency(self, parent):
        C = self.C
        px = self.px
        page = tk.Frame(parent, bg=C["bg"])
        page.grid_columnconfigure(0, weight=1)
        page.grid_rowconfigure(2, weight=1)
        self.page_title(page, "Currency", "Live exchange rates, convert one or many amounts").grid(
            row=0, column=0, sticky="w", pady=(0, px(16)))

        form = Card(page, C["card"], C["bg"], radius=px(22), border=C["line"], height=px(196))
        form.grid(row=1, column=0, sticky="ew", pady=(0, px(16)))
        f = form.inner
        for c, wt in enumerate((3, 5, 0, 5)):
            f.grid_columnconfigure(c, weight=wt)
        pad = px(26)
        names = [self.cur_name(k) for k in sorted(CURRENCIES)]

        def label(text, col):
            tk.Label(f, text=text, bg=C["card"], fg=C["muted"], font=self.f(10, True), anchor="w").grid(
                row=0, column=col, sticky="w", padx=(pad if col == 0 else px(8), 0), pady=(px(20), px(6)))

        label("AMOUNT(S)", 0)
        label("FROM", 1)
        label("TO", 3)
        box, entry = self.make_entry(f, self.amount, 16)
        box.grid(row=1, column=0, sticky="ew", padx=(pad, px(8)))
        for col, var in ((1, self.from_cur), (3, self.to_cur)):
            cb = ttk.Combobox(f, textvariable=var, values=names, state="readonly",
                              style="Gold.TCombobox", font=self.f(12))
            cb.grid(row=1, column=col, sticky="ew", padx=(px(8), px(8) if col == 1 else pad))
            cb.bind("<<ComboboxSelected>>", lambda e, w=cb: w.selection_clear())
        RoundButton(f, "⇄", self.swap, C["op"], C["card"], self.f(16, True), radius=px(14),
                    width=px(48), height=px(44)).grid(row=1, column=2)

        bottom = tk.Frame(f, bg=C["card"])
        bottom.grid(row=2, column=0, columnspan=4, sticky="ew", padx=pad, pady=(px(16), 0))
        RoundButton(bottom, "Update live rates", self.fetch_rates, C["op"], C["card"], self.f(11, True),
                    radius=px(13), width=px(170), height=px(40)).pack(side="left")
        self.lbl_note = tk.Label(bottom, text="", bg=C["card"], fg=C["muted"], font=self.f(10))
        self.lbl_note.pack(side="left", padx=px(14))

        result = Card(page, C["card"], C["bg"], radius=px(22), border=C["line"])
        result.grid(row=2, column=0, sticky="nsew")
        r = result.inner
        self.lbl_from = tk.Label(r, text="", bg=C["card"], fg=C["muted"], font=self.f(13), anchor="w")
        self.lbl_from.pack(fill="x", padx=px(30), pady=(px(26), 0))
        self.lbl_big = tk.Label(r, text="", bg=C["card"], fg=C["gold"], font=self.f(40, True), anchor="w")
        self.lbl_big.pack(fill="x", padx=px(30))
        self.lbl_rate = tk.Label(r, text="", bg=C["card"], fg=C["text"], font=self.f(12), anchor="w")
        self.lbl_rate.pack(fill="x", padx=px(30), pady=(px(2), px(10)))
        tk.Frame(r, bg=C["line"], height=1).pack(fill="x", padx=px(30))
        self.txt_cur = tk.Text(r, bg=C["card"], fg=C["text"], bd=0, highlightthickness=0, height=5,
                               state="disabled", cursor="arrow", padx=px(30), pady=px(8),
                               font=self.f(13, mono=True), selectbackground=C["card"],
                               inactiveselectbackground=C["card"])
        self.txt_cur.pack(fill="both", expand=True)
        self.txt_cur.tag_configure("amt", foreground=C["text"], spacing1=px(4), spacing3=px(4))
        self.txt_cur.tag_configure("arrow", foreground=C["muted"])
        self.txt_cur.tag_configure("out", foreground=C["gold"], font=self.f(13, True, True))
        self.txt_cur.tag_configure("note", foreground=C["muted"], font=self.f(10))
        return page

    def code(self, label):
        return label.split(" ")[0]

    def swap(self):
        a, b = self.from_cur.get(), self.to_cur.get()
        self.from_cur.set(b)
        self.to_cur.set(a)

    def get_amounts(self):
        text = self.amount.get().strip().replace(";", ",")
        if re.fullmatch(r"\d{1,3}(,\d{3})+(\.\d+)?", text):         # 1,100 means one amount
            return [float(text.replace(",", ""))]
        parts = [p.strip() for p in text.split(",") if p.strip()]
        if not parts or len(parts) > 12:
            raise ValueError
        return [float(p) for p in parts]

    def money(self, v):
        return "{:,.2f}".format(v) if abs(v) >= 0.01 or v == 0 else "{:,.6f}".format(v)

    def convert(self):
        C = self.C
        try:
            t = self.txt_cur
            t.config(state="normal")
            t.delete("1.0", "end")
        except (tk.TclError, AttributeError):
            return
        try:
            amounts = self.get_amounts()
        except ValueError:
            self.lbl_from.config(text="")
            self.lbl_big.config(text="Check the amount", fg=C["bad"])
            self.lbl_rate.config(text="Use numbers only, for example  10, 50, 250")
            t.config(state="disabled")
            return
        fc, tc = self.code(self.from_cur.get()), self.code(self.to_cur.get())
        rate = self.rates[tc] / self.rates[fc]
        first = amounts[0] * rate
        self.lbl_from.config(text="%s %s  =" % (self.money(amounts[0]), fc))
        self.lbl_big.config(text="%s %s" % (self.money(first), tc), fg=C["gold"])
        digits = "%.4f" if rate >= 0.0001 else "%.8f"
        self.lbl_rate.config(text=("1 %s = " + digits + " %s") % (fc, rate, tc))
        if len(amounts) > 1:
            for a in amounts:
                t.insert("end", "{:>16} {}".format(self.money(a), fc), "amt")
                t.insert("end", "   →   ", "arrow")
                t.insert("end", "{:>16} {}\n".format(self.money(a * rate), tc), "out")
        else:
            t.insert("end", "Tip: type several amounts like  10, 50, 250  to convert them together.", "note")
        t.config(state="disabled")

    # ----- live rates (runs in a thread so the window never freezes)
    def set_note(self, text, color):
        self.rate_note = (text, color)
        self.show_rate_note()

    def show_rate_note(self):
        text, color = self.rate_note
        try:
            self.lbl_note.config(text=text, fg=self.C.get(color, self.C["muted"]))
        except (tk.TclError, AttributeError):
            pass

    def fetch_rates(self):
        if self.fetching:
            return
        self.fetching = True
        self.set_note("Fetching live rates…", "muted")
        threading.Thread(target=self.download_rates, daemon=True).start()
        self.root.after(200, self.check_rates)

    def download_rates(self):
        error = "no connection"
        for url, reader in RATE_URLS:
            try:
                req = Request(url, headers={"User-Agent": "AdvancedCalculator/1.0"})
                with urlopen(req, timeout=8) as r:
                    data = json.loads(r.read().decode("utf-8"))
                rates, when = reader(data)
                if rates:
                    self.rate_queue.put(("ok", rates, when))
                    return
            except Exception as ex:
                error = str(ex)
        self.rate_queue.put(("fail", error))

    def check_rates(self):
        try:
            item = self.rate_queue.get_nowait()
        except queue.Empty:
            self.root.after(200, self.check_rates)
            return
        self.fetching = False
        if item[0] == "ok":
            for code, value in item[1].items():
                if code in CURRENCIES:
                    self.rates[code] = float(value)
            self.rate_live = True
            self.set_note("Live rates · %s UTC" % item[2].strip().rstrip(","), "good")
        else:
            self.set_note("No internet. Using approximate offline rates.", "warn")
        self.convert()


def main():
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)      # sharp text on Windows
    except Exception:
        pass
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()