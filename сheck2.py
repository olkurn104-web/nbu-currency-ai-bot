import re
import tkinter as tk
from tkinter import ttk, scrolledtext
import requests

API_KEY = "YOUR_OPENROUTER_API_KEY"
OPENROUTER_URL = "https://openrouter.ai"
MODEL_NAME = "openrouter/free"
class NBUCurrencyService:
    def __init__(self):
        self.url = "https://bank.gov.ua"
        self.rates = {}
    def fetch_rates(self):
        headers = {"User-Agent": "Mozilla/5.0"}
        try:
            response = requests.get(self.url, headers=headers, timeout=10)
            response.raise_for_status()
            data = response.json()
            self.rates = {item["cc"]: item for item in data}
            return True, f"Завантажено {len(self.rates)} валют НБУ"
        except Exception:
            self.rates = {
                "USD": {"cc": "USD", "txt": "Долар США", "rate": 45.272},
                "EUR": {"cc": "EUR", "txt": "Євро", "rate": 49.5346},
                "PLN": {"cc": "PLN", "txt": "Злотий", "rate": 11.0566},
                "GBP": {"cc": "GBP", "txt": "Фунт стерлінгів", "rate": 59.1673},
                "CHF": {"cc": "CHF", "txt": "Швейцарський франк", "rate": 54.3619},
            }
            return False, "Офлайн-режим (НБУ недоступний): завантажено базові курси"
    def get_all_currency_labels(self):
        items = [f"{cc} — {info['txt']}" for cc, info in self.rates.items()]
        return sorted(items)
    def convert_to_uah(self, user_input, fallback_code=None):
        text = user_input.strip().replace(",", ".")
        if not text:
            return False, "Введіть суму та валюту (напр. 100EUR або 100 USD)"
        match = re.match(r"^(\d+(?:\.\d+)?)\s*([a-zA-Z]{3})$", text)
        if match:
            amount = float(match.group(1))
            code = match.group(2).upper()
        else:
            try:
                amount = float(text)
                if not fallback_code:
                    return False, "Вкажіть код валюти (напр. 100 EUR)"
                code = fallback_code
            except ValueError:
                return False, "Невірний формат! Приклад: 100EUR або 100 USD"
        if code not in self.rates:
            return False, f"Валюту '{code}' не знайдено"
        info = self.rates[code]
        rate = float(info["rate"])
        total_uah = round(amount * rate)
        return True, f"{amount:g} {code} ({info['txt']}) = {total_uah} грн\n(Курс: {rate} грн)"
    def get_all_rates_for_ai(self):
        if not self.rates:
            return "курси тимчасово недоступні"
        return "; ".join([f"{cc} ({info['txt']}): {info['rate']} грн" for cc, info in self.rates.items()])
class OpenRouterBot:
    def __init__(self, api_key, url, model, currency_context):
        self.api_key = api_key
        self.url = url
        self.model = model
        self.history = [
            {
                "role": "system",
                "content": (
                    f"Ти — фінансовий помічник у додатку конвертера валют. "
                    f"Актуальні курси НБУ: {currency_context}. "
                    f"Відповідай українською мовою, коротко та по суті."
                )
            }
        ]
    def ask(self, user_message):
        if not self.api_key or self.api_key == "YOUR_OPENROUTER_API_KEY":
            return "⚠️ Вставте свій API-ключ OpenRouter у змінну API_KEY!"
        self.history.append({"role": "user", "content": user_message})
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {"model": self.model, "messages": self.history}
        try:
            response = requests.post(self.url, headers=headers, json=payload, timeout=20)
            if response.status_code == 429:
                return "⏳ Перевищено ліміт запитів OpenRouter. Спробуйте через хвилину."
            if response.status_code == 401:
                return "❌ Невірний або заблокований API-ключ OpenRouter."
            response.raise_for_status()
            data = response.json()
            if "choices" not in data or not data["choices"]:
                return "⚠️ Порожня відповідь від моделі. Спробуйте ще раз."
            reply = data["choices"][0]["message"]["content"]
            self.history.append({"role": "assistant", "content": reply})
            return reply
        except requests.exceptions.RequestException:
            return "❌ Немає з'єднання з OpenRouter або сервер не відповідає."
class FinanceApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Калькулятор будь-яких валют + AI Фінансист")
        self.root.geometry("540x630")
        self.root.configure(bg="#f4f6f9")
        self.nbu = NBUCurrencyService()
        success, status_msg = self.nbu.fetch_rates()
        self.bot = OpenRouterBot(API_KEY, OPENROUTER_URL, MODEL_NAME, self.nbu.get_all_rates_for_ai())
        self._build_ui(status_msg, success)
    def _build_ui(self, status_msg, success):
        status_color = "#28a745" if success else "#e67e22"
        tk.Label(self.root, text=status_msg, fg=status_color, bg="#f4f6f9", font=("Arial", 9)).pack(pady=(5, 0))
        tk.Label(
            self.root, text="Введіть суму і валюту (напр. 100EUR або 100 PLN):",
            font=("Arial", 11, "bold"), bg="#f4f6f9"
        ).pack(pady=(10, 5))
        all_labels = self.nbu.get_all_currency_labels()
        self.currency_combo = ttk.Combobox(self.root, values=all_labels, width=32, state="readonly", font=("Arial", 10))
        if all_labels:
            default_idx = next((i for i, v in enumerate(all_labels) if v.startswith("USD")), 0)
            self.currency_combo.current(default_idx)
        self.currency_combo.pack(pady=(0, 8))
        conv_frame = tk.Frame(self.root, bg="#f4f6f9")
        conv_frame.pack()
        self.conv_entry = tk.Entry(conv_frame, font=("Arial", 13), width=20, justify="center")
        self.conv_entry.pack(side=tk.LEFT, padx=5)
        self.conv_entry.focus()
        self.conv_entry.bind("<Return>", lambda e: self.handle_convert())
        tk.Button(
            conv_frame, text="Перевести в грн", font=("Arial", 11, "bold"),
            bg="#007bff", fg="white", command=self.handle_convert
        ).pack(side=tk.LEFT)
        self.conv_result = tk.Label(self.root, text="", font=("Arial", 12, "bold"), bg="#f4f6f9")
        self.conv_result.pack(pady=8)
        tk.Label(self.root, text="AI Фінансовий помічник (OpenRouter):", font=("Arial", 11, "bold"), bg="#f4f6f9").pack(pady=(8, 5))
        self.chat_box = scrolledtext.ScrolledText(self.root, width=60, height=15, font=("Arial", 10), state="disabled", wrap=tk.WORD)
        self.chat_box.pack(padx=15, pady=5)
        chat_input_frame = tk.Frame(self.root, bg="#f4f6f9")
        chat_input_frame.pack(pady=10)
        self.chat_entry = tk.Entry(chat_input_frame, font=("Arial", 11), width=38)
        self.chat_entry.pack(side=tk.LEFT, padx=5)
        self.chat_entry.bind("<Return>", lambda e: self.handle_chat())
        tk.Button(
            chat_input_frame, text="Запитати AI", font=("Arial", 10, "bold"),
            bg="#28a745", fg="white", command=self.handle_chat
        ).pack(side=tk.LEFT)
        self._append_chat("Бот", "Привіт! Введи будь-яку суму і валюту зверху (напр. 100EUR або 500 JPY) або запитай мене про обмін валют.")
    def handle_convert(self):
        selected_combo = self.currency_combo.get()
        fallback_code = selected_combo.split(" — ")[0] if selected_combo else None
        ok, res = self.nbu.convert_to_uah(self.conv_entry.get(), fallback_code)
        self.conv_result.config(text=res, fg="#28a745" if ok else "#d9534f")
    def handle_chat(self):
        msg = self.chat_entry.get().strip()
        if not msg:
            return
        self.chat_entry.delete(0, tk.END)
        self._append_chat("Ви", msg)
        self.root.update()
        reply = self.bot.ask(msg)
        self._append_chat("Бот", reply)
    def _append_chat(self, sender, text):
        self.chat_box.config(state="normal")
        self.chat_box.insert(tk.END, f"{sender}: {text}\n\n")
        self.chat_box.see(tk.END)
        self.chat_box.config(state="disabled")
if __name__ == "__main__":
    root = tk.Tk()
    app = FinanceApp(root)
    root.mainloop()
