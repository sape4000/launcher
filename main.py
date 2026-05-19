import os
import sys
import subprocess
import customtkinter as ctk

# Импортируем дочерние модули-страницы
from key_editor import KeyEditorWidget
from account_editor import AccountEditorWidget

# Подключаем WinAPI для проверки прав администратора в системе
import ctypes
shell32 = ctypes.windll.shell32

class AsteriosManagerPro(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        self.title("Asterios Manager Pro: Chaotic Chronicle v15.5")
        self.geometry("1300x820")
        
        # Жесткий запрет на сжатие интерфейса меньше ширины таблицы в редакторе аккаунтов
        self.minsize(1300, 600)
        
        ctk.set_appearance_mode("dark")
        
        self.current_page = None
        self.script_dir = os.path.dirname(os.path.abspath(__file__))
        self.launchsetting_file = os.path.join(self.script_dir, "launchsetting.txt")
        self.keys_file = os.path.join(self.script_dir, "keys.txt")
        self.settings_ini_file = os.path.join(self.script_dir, "settings.ini") # Файл настроек спойлеров
        
        self.game_path = r"G:\Asterios"
        self.accounts_data = {} 
        self.groups_expanded_status = {} # Хранилище состояний спойлеров в ОЗУ
        
        self.is_admin = self.check_if_run_as_admin()
        
        self.load_launcher_settings()
        self.load_spoilers_from_ini() # Загружаем состояние вкладок из settings.ini
        self.load_accounts_from_keys()
        
        self.build_top_menu()
        
        self.content_container = ctk.CTkFrame(self, fg_color="transparent")
        self.content_container.pack(fill="both", expand=True, padx=15, pady=(5, 15))
        
        # Дочерние фреймы в памяти
        self.page_accounts = ctk.CTkFrame(self.content_container, fg_color="transparent")
        self.page_settings = ctk.CTkFrame(self.content_container, fg_color="transparent")
        self.page_hotkeys_editor = KeyEditorWidget(self.content_container)
        self.page_accounts_editor = AccountEditorWidget(self.content_container, self)
        
        self.build_accounts_page()
        self.build_settings_page()
        
        # Горячие клавиши главного окна
        self.bind("<Escape>", lambda event: self.quit())
        self.bind("<Key>", self.global_key_handler)
        
        self.show_page(self.page_accounts)

    def check_if_run_as_admin(self):
        try: return shell32.IsUserAnAdmin() != 0
        except: return False

    def global_key_handler(self, event):
        ctrl_pressed = (event.state & 0x4) != 0
        if ctrl_pressed and event.keycode == 86:
            focused_widget = self.focus_get()
            if focused_widget and hasattr(focused_widget, "insert"):
                try:
                    clipboard_text = self.clipboard_get()
                    if clipboard_text:
                        if focused_widget.has_selection():
                            focused_widget.delete("sel.first", "sel.last")
                        focused_widget.insert("insert", clipboard_text)
                    return "break"
                except: pass

    def load_launcher_settings(self):
        if not os.path.exists(self.launchsetting_file): return
        try:
            with open(self.launchsetting_file, "r", encoding="cp1251") as f:
                for line in f:
                    if line.strip().startswith("# [GAME_PATH ="):
                        self.game_path = line.strip()[14:-1].strip()
        except: pass

    def load_spoilers_from_ini(self):
        """ Считывает сохраненные спойлеры из блока [Spoilers] в settings.ini """
        if not os.path.exists(self.settings_ini_file): return
        try:
            with open(self.settings_ini_file, "r", encoding="cp1251") as f:
                lines = f.readlines()
                
            in_spoilers_section = False
            for line in lines:
                line = line.strip()
                if not line: continue
                
                if line.lower() == "[spoilers]":
                    in_spoilers_section = True
                    continue
                elif line.startswith("["):
                    in_spoilers_section = False
                    
                if in_spoilers_section and "=" in line:
                    g_name, g_state = line.split("=", 1)
                    self.groups_expanded_status[g_name.strip()] = g_state.strip() == "1"
        except: pass

    def save_spoilers_to_ini(self):
        """ Записывает или обновляет блок [Spoilers] в settings.ini без потери других данных """
        existing_sections = {}
        current_section = ""
        
        if os.path.exists(self.settings_ini_file):
            try:
                with open(self.settings_ini_file, "r", encoding="cp1251") as f:
                    for line in f:
                        line_stripped = line.strip()
                        if not line_stripped: continue
                        if line_stripped.startswith("[") and line_stripped.endswith("]"):
                            current_section = line_stripped.lower()
                            existing_sections[current_section] = []
                        elif current_section and current_section != "[spoilers]":
                            existing_sections[current_section].append(line.rstrip())
            except: pass
            
        spoilers_content = ["[Spoilers]"]
        for g_name, is_expanded in self.groups_expanded_status.items():
            state_val = "1" if is_expanded else "0"
            spoilers_content.append(f"{g_name}={state_val}")
            
        final_lines = []
        final_lines.extend(spoilers_content)
        
        for section_name, section_lines in existing_sections.items():
            final_lines.append("")
            final_lines.append(section_name.upper() if section_name == "[spoilers]" else section_name)
            final_lines.extend(section_lines)
            
        try:
            with open(self.settings_ini_file, "w", encoding="cp1251") as f:
                f.write("\n".join(final_lines) + "\n")
        except: pass

    def toggle_group_visibility(self, group_name, content_frame, button_widget):
        is_currently_expanded = self.groups_expanded_status.get(group_name, True)
        new_state = not is_currently_expanded
        self.groups_expanded_status[group_name] = new_state
        
        if new_state:
            content_frame.pack(fill="x", padx=15, pady=(0, 15))
            button_widget.configure(text=f"▲  {group_name}")
        else:
            content_frame.pack_forget()
            button_widget.configure(text=f"▼  {group_name}")
            
        self.save_spoilers_to_ini()

    # =========================================================================
    # 💎 ЖЕЛЕЗНЫЙ ИСПРАВЛЕННЫЙ ПАРСЕР С СИСТЕМНЫМИ ИНДЕКСАМИ НАРЕЗКИ СТРОК
    # =========================================================================
    def load_accounts_from_keys(self):
        self.accounts_data.clear()
        if not os.path.exists(self.keys_file): return
        try:
            with open(self.keys_file, "r", encoding="cp1251") as f:
                lines = f.readlines()
            current_group_name = "Без группы"
            current_group_num = "1"
            for line in lines:
                line = line.strip()
                if not line or line.startswith("# ["): continue
                if line.startswith("#"):
                    potential_group = line[1:].strip()
                    if "DATABASE" not in potential_group.upper(): current_group_name = str(potential_group)
                    continue
                if "=" in line:
                    char_id, val = line.split("=", 1)
                    char_id, val = char_id.strip(), val.strip()
                    if "|" in val:
                        parts = [p.strip() for p in val.split("|")]
                        if len(parts) >= 8:
                            # ИСПРАВЛЕНО НАВСЕГДА: Вытаскиваем только сухой текст элементов списка!
                            self.accounts_data[char_id] = {
                                "group_num": str(parts[0]),
                                "group_name": str(parts[1]),
                                "desc": str(parts[2]),
                                "key": str(parts[3]),
                                "res_x": str(parts[4]),
                                "res_y": str(parts[5]),
                                "pos_x": str(parts[6]),
                                "pos_y": str(parts[7]),
                                "attach": str(parts[8]) if len(parts) > 8 else "0"
                            }
                    else:
                        self.accounts_data[char_id] = {
                            "group_num": str(current_group_num), "group_name": str(current_group_name),
                            "desc": "warex2", "key": val, "res_x": "1280", "res_y": "720", "pos_x": "0", "pos_y": "0", "attach": "0"           
                        }
        except Exception as e: print(f"[ОШИБКА] Чтение базы в мейне: {e}")

    def build_top_menu(self):
        self.menu_frame = ctk.CTkFrame(self, height=45, fg_color="#1A1A1E", corner_radius=0)
        self.menu_frame.pack(fill="x", side="top", pady=(0, 10))
        self.menu_frame.pack_propagate(False)
        ctk.CTkButton(self.menu_frame, text="АККАУНТЫ", font=("Segoe UI", 12, "bold"), fg_color="transparent", text_color="#A8A8B3", hover_color="#2A2A30", command=lambda: self.show_page_accounts_with_check()).pack(side="left", fill="both", expand=True)
        ctk.CTkButton(self.menu_frame, text="НАСТРОЙКИ", font=("Segoe UI", 12, "bold"), fg_color="transparent", text_color="#A8A8B3", hover_color="#2A2A30", command=lambda: self.show_page_settings_with_check()).pack(side="left", fill="both", expand=True)

    def show_page(self, page_to_show):
        if self.current_page: self.current_page.pack_forget()
        page_to_show.pack(fill="both", expand=True)
        self.current_page = page_to_show

    def show_page_accounts_with_check(self):
        if self.current_page == self.page_accounts_editor and hasattr(self.page_accounts_editor, "check_unsaved_changes"):
            self.page_accounts_editor.check_unsaved_changes(lambda: self.show_page(self.page_accounts))
        else: self.show_page(self.page_accounts)

    def show_page_settings_with_check(self):
        if self.current_page == self.page_accounts_editor and hasattr(self.page_accounts_editor, "check_unsaved_changes"):
            self.page_accounts_editor.check_unsaved_changes(lambda: self.show_page(self.page_settings))
        else: self.show_page(self.page_settings)

    # --- ИСПРАВЛЕННАЯ СБОРКА СТРАНИЦЫ С АВТОМАТИЧЕСКИМ МАСШТАБИРОВАНИЕМ КНОПОК ---
    def build_accounts_page(self):
        for widget in self.page_accounts.winfo_children(): widget.destroy()
        scroll = ctk.CTkScrollableFrame(self.page_accounts, fg_color="transparent")
        scroll.pack(fill="both", expand=True)
        
        groups = {}
        for cid, info in self.accounts_data.items():
            g_name = str(info["group_name"])
            if g_name not in groups: groups[g_name] = []
            groups[g_name].append((cid, info))
            
        for g_name, chars in groups.items():
            if g_name not in self.groups_expanded_status:
                self.groups_expanded_status[g_name] = True
                
            is_expanded = self.groups_expanded_status[g_name]
            
            group_frame = ctk.CTkFrame(scroll, fg_color="#141416", border_color="#222226", border_width=1)
            group_frame.pack(fill="x", pady=6, padx=5)
            
            # Контейнер для кнопок персонажей этой группы
            chars_row = ctk.CTkFrame(group_frame, fg_color="transparent")
            
            # Настраиваем автоматическое адаптивное масштабирование всех 6 колонок по ширине
            for i in range(6):
                chars_row.grid_columnconfigure(i, weight=1)
            
            icon_prefix = "▲" if is_expanded else "▼"
            btn_spoiler = ctk.CTkButton(
                group_frame, 
                text=f"{icon_prefix}  {g_name}", 
                font=("Segoe UI", 12, "bold"), 
                text_color="#A8A8B3", 
                fg_color="transparent", 
                hover_color="#1A1A1E",
                anchor="w",
                height=34,
                corner_radius=0
            )
            btn_spoiler.pack(fill="x", padx=5, pady=4)
            btn_spoiler.configure(command=lambda gn=g_name, cr=chars_row, bs=btn_spoiler: self.toggle_group_visibility(gn, cr, bs))
            
            # Заставляем фрейм кнопок растягиваться во всю ширину экрана
            if is_expanded: 
                chars_row.pack(fill="x", padx=15, pady=(0, 15))
            else: 
                chars_row.pack_forget()
                
            # Раскладываем кнопки по ячейкам сетки (максимум 6 штук в один ряд)
            for index, (cid, info) in enumerate(chars):
                row_index = index // 6  
                col_index = index % 6   
                
                btn = ctk.CTkButton(
                    chars_row, 
                    text=cid, 
                    font=("Segoe UI", 12, "bold"), 
                    fg_color="#1A233A", 
                    hover_color="#243256", 
                    height=38, 
                    command=lambda n=cid: self.launch_game_window(n)
                )
                # sticky="ew" заставляет кнопки динамически растягиваться во всю ширину своей колонки!
                btn.grid(row=row_index, column=col_index, padx=5, pady=5, sticky="ew")
                
        self.lbl_game_status = ctk.CTkLabel(scroll, text="", font=("Segoe UI", 12, "bold"), text_color="#22C55E")
        self.lbl_game_status.pack(pady=10)
        ctk.CTkButton(scroll, text="ВЫХОД ИЗ ЛАУНЧЕРА", font=("Segoe UI", 14, "bold"), text_color="#EF4444", fg_color="#1A1A1E", border_color="#EF4444", border_width=1, height=45, command=self.quit).pack(fill="x", pady=10, padx=5)

    def build_settings_page(self):
        lbl_info = ctk.CTkLabel(self.page_settings, text="⚙  Настройки менеджера и утилит хроник", font=("Segoe UI", 16, "bold"), text_color="#44AAFF")
        lbl_info.pack(pady=(20, 5), anchor="w", padx=20)
        
        if self.is_admin:
            lbl_admin_status = ctk.CTkLabel(self.page_settings, text="🟢  Запущено от имени Администратора (Доступ к WinAPI и античиту открыт)", font=("Segoe UI", 12, "bold"), text_color="#22C55E")
        else:
            lbl_admin_status = ctk.CTkLabel(self.page_settings, text="🔴  Запущено БЕЗ прав Администратора! (Прилипала окон будет заблокирован)", font=("Segoe UI", 12, "bold"), text_color="#EF4444")
        lbl_admin_status.pack(pady=(0, 15), anchor="w", padx=20)
        
        path_frame = ctk.CTkFrame(self.page_settings, fg_color="#1A1A1E", height=50)
        path_frame.pack(fill="x", padx=20, pady=10)
        ctk.CTkLabel(path_frame, text="Путь к корневой папке Asterios:", font=("Segoe UI", 12, "bold")).pack(side="left", padx=15)
        
        self.entry_game_path = ctk.CTkEntry(path_frame, font=("Consolas", 12), fg_color="#121214", height=32)
        self.entry_game_path.insert(0, self.game_path)
        self.entry_game_path.pack(side="left", fill="x", expand=True, padx=10)
        ctk.CTkButton(path_frame, text="📁 Обзор", width=100, font=("Segoe UI", 11, "bold"), command=self.browse_folder).pack(side="right", padx=15)
        
        ctk.CTkButton(self.page_settings, text="🔧   Настройка глобальных хоткеев (launchsetting.txt)", font=("Segoe UI", 13, "bold"), fg_color="#1A1A1E", hover_color="#2A2A30", anchor="w", height=45, command=lambda: self.show_page(self.page_hotkeys_editor)).pack(fill="x", padx=20, pady=5)
        ctk.CTkButton(self.page_settings, text="🖥   Редактор аккаунтов, разрешений и прилипалы (keys.txt)", font=("Segoe UI", 13, "bold"), fg_color="#1A1A1E", hover_color="#2A2A30", anchor="w", height=45, command=lambda: [self.page_accounts_editor.reload_and_draw(), self.show_page(self.page_accounts_editor)]).pack(fill="x", padx=20, pady=5)
        
        self.lbl_status = ctk.CTkLabel(self.page_settings, text="", font=("Segoe UI", 11, "bold"), text_color="#22C55E")
        self.lbl_status.pack(pady=5)
        ctk.CTkButton(self.page_settings, text="💾 Сохранить пути игры", font=("Segoe UI", 13, "bold"), fg_color="#44AAFF", height=40, command=self.save_launcher_paths).pack(fill="x", padx=20, pady=5)

    def browse_folder(self):
        from tkinter.filedialog import askdirectory
        folder = askdirectory(title="Выберите корневую папку Asterios")
        if folder:
            clean_folder = folder.replace("/", "\\")
            self.entry_game_path.delete(0, "end")
            self.entry_game_path.insert(0, clean_folder)
            self.game_path = clean_folder

    def save_launcher_paths(self):
        try:
            self.game_path = self.entry_game_path.get().strip()
            content = ""
            if os.path.exists(self.launchsetting_file):
                with open(self.launchsetting_file, "r", encoding="cp1251") as f: content = f.read()
            lines = [l for l in content.split("\n") if not l.strip().startswith("# [GAME_PATH =")]
            new_content = f"# [GAME_PATH = {self.game_path}]\n" + "\n".join(lines)
            with open(self.launchsetting_file, "w", encoding="cp1251") as f: f.write(new_content)
            self.lbl_status.configure(text="✔ Путь к игре успешно сохранен!")
            self.after(3000, lambda: self.lbl_status.configure(text=""))
        except Exception as e: self.lbl_status.configure(text=f"Ошибка: {e}")

    def launch_game_window(self, character_name):
        info = self.accounts_data.get(character_name)
        if not info: return
        
        asterios_game_ini = os.path.join(self.game_path, "asterios", "AsteriosGame.ini")
        option_ini = os.path.join(self.game_path, "asterios", "Option.ini")

        try:
            self.lbl_game_status.configure(text=f"⏳ Записываем Key={info['key']} в AsteriosGame.ini...", text_color="#EAB308")
            self.update_idletasks()

            if os.path.exists(asterios_game_ini):
                with open(asterios_game_ini, "r", encoding="cp1251") as f: lines = f.readlines()
                new_lines = []; in_auth_section = False; key_replaced = False
                for line in lines:
                    clean_line = line.strip().lower()
                    if clean_line.startswith("[auth]"): in_auth_section = True
                    elif clean_line.startswith("[") and in_auth_section:
                        if not key_replaced: new_lines.append(f"Key={info['key']}\n"); key_replaced = True
                        in_auth_section = False
                    if in_auth_section and clean_line.startswith("key="):
                        new_lines.append(f"Key={info['key']}\n"); key_replaced = True
                    else: new_lines.append(line)
                if in_auth_section and not key_replaced: new_lines.append(f"Key={info['key']}\n")
                with open(asterios_game_ini, "w", encoding="cp1251") as f: f.writelines(new_lines)

            if os.path.exists(option_ini):
                with open(option_ini, "r", encoding="cp1251") as f: lines = f.readlines()
                new_lines = []; in_video_section = False
                for line in lines:
                    clean_line = line.strip().lower()
                    if clean_line.startswith("[video]"): in_video_section = True
                    elif clean_line.startswith("[") and in_video_section: in_video_section = False
                    if in_video_section and line.strip().startswith("GamePlayViewportX="):
                        new_lines.append(f"GamePlayViewportX={info['res_x']}\n")
                    elif in_video_section and line.strip().startswith("GamePlayViewportY="):
                        new_lines.append(f"GamePlayViewportY={info['res_y']}\n")
                    else: new_lines.append(line)
                with open(option_ini, "w", encoding="cp1251") as f: f.writelines(new_lines)

            executable = os.path.join(self.game_path, "Asterios.exe")
            if not os.path.exists(executable): executable = os.path.join(self.game_path, "asterios", "l2.exe")
            
            cmd_command = f'start "" "{executable}" /autoplay'
            subprocess.Popen(cmd_command, shell=True, cwd=self.game_path)
            
            self.lbl_game_status.configure(text=f"🚀 Окно {character_name} успешно запущено с /autoplay!", text_color="#22C55E")
            self.after(3000, lambda: self.lbl_game_status.configure(text=""))

            if info["attach"] == "1":
                wm_absolute_path = os.path.join(self.script_dir, "window_manager.exe")
                if os.path.exists(wm_absolute_path):
                    subprocess.Popen([wm_absolute_path], cwd=self.script_dir)
                    print(f"[ПРИЛИПАЛА] Автономный window_manager.exe запущен в фоне.")
        except Exception as e: 
            self.lbl_game_status.configure(text=f"❌ Ошибка старта: {e}", text_color="#EF4444")

if __name__ == "__main__":
    app = AsteriosManagerPro()
    app.mainloop()
