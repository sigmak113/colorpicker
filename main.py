# -*- coding: utf-8 -*-
"""
컬러 팔레트 매니저
- 5개 세트, 세트당 5개 색상 슬롯 관리
- 클릭 시 #RRGGBB 클립보드 자동 복사 (프리미어 프로 Lumetri 색상창 등에 Ctrl+V로 붙여넣기)
- 색상 지정: 팔레트에서 선택 / 화면에서 스포이드로 추출
- colors_data.json 파일에 자동 저장 (exe와 같은 폴더)
"""

import sys
import os
import json
import tkinter as tk
from tkinter import colorchooser, simpledialog, messagebox

try:
    import pyperclip
except ImportError:
    pyperclip = None

try:
    from PIL import Image, ImageGrab, ImageTk, ImageDraw
except ImportError:
    Image = ImageGrab = ImageTk = ImageDraw = None

SET_COUNT = 5
SLOT_COUNT = 5
SWATCH_SIZE = 70
MAGNIFIER_ZOOM = 8          # 스포이드 확대 배율
MAGNIFIER_GRID_PX = 11      # 확대해서 보여줄 원본 픽셀 범위 (11x11)


def get_base_path():
    """exe로 빌드됐을 때와 스크립트로 실행할 때 모두 올바른 폴더를 반환"""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


DATA_FILE = os.path.join(get_base_path(), "colors_data.json")


def default_data():
    return {
        "current_set": 0,
        "set_names": [f"세트 {i + 1}" for i in range(SET_COUNT)],
        # 각 세트는 슬롯 5개, 값은 "#RRGGBB" 또는 None(비어있음)
        "sets": [[None] * SLOT_COUNT for _ in range(SET_COUNT)],
    }


def load_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            # 방어적 보정 (파일이 손상/구버전이어도 죽지 않게)
            d = default_data()
            d.update({k: v for k, v in data.items() if k in d})
            if len(d["sets"]) != SET_COUNT:
                d["sets"] = default_data()["sets"]
            if len(d["set_names"]) != SET_COUNT:
                d["set_names"] = default_data()["set_names"]
            return d
        except Exception:
            pass
    return default_data()


def save_data(data):
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print("저장 실패:", e)


def readable_text_color(hex_color):
    """배경색 밝기에 따라 검/흰 텍스트 자동 선택"""
    hex_color = hex_color.lstrip("#")
    r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
    luminance = (0.299 * r + 0.587 * g + 0.114 * b)
    return "#000000" if luminance > 150 else "#ffffff"


class EyedropperOverlay(tk.Toplevel):
    """화면 전체를 캡처해서 보여주고, 클릭한 픽셀의 색상을 골라주는 오버레이 창"""

    def __init__(self, master, on_pick):
        super().__init__(master)
        self.on_pick = on_pick
        self.result_color = None

        if Image is None:
            messagebox.showerror("오류", "Pillow 라이브러리가 설치되어 있지 않습니다.\npip install pillow")
            self.destroy()
            return

        # 화면 캡처 (주 모니터 기준)
        self.screenshot = ImageGrab.grab()
        self.img_w, self.img_h = self.screenshot.size

        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.geometry(f"{self.img_w}x{self.img_h}+0+0")
        self.config(cursor="crosshair")

        self.tk_bg_image = ImageTk.PhotoImage(self.screenshot)
        self.canvas = tk.Canvas(self, width=self.img_w, height=self.img_h,
                                 highlightthickness=0, cursor="crosshair")
        self.canvas.pack(fill="both", expand=True)
        self.canvas.create_image(0, 0, image=self.tk_bg_image, anchor="nw")

        # 안내 문구
        self.canvas.create_rectangle(0, 0, 480, 34, fill="#111111", outline="")
        self.canvas.create_text(
            10, 17, anchor="w", fill="white",
            text="화면을 클릭해서 색상을 추출하세요.  (ESC: 취소)",
            font=("맑은 고딕", 11)
        )

        self.magnifier_id = None
        self.hex_text_id = None

        self.canvas.bind("<Motion>", self._on_motion)
        self.canvas.bind("<Button-1>", self._on_click)
        self.bind("<Escape>", lambda e: self._cancel())
        self.focus_force()

    def _get_pixel(self, x, y):
        x = max(0, min(self.img_w - 1, x))
        y = max(0, min(self.img_h - 1, y))
        return self.screenshot.getpixel((x, y))[:3]

    def _on_motion(self, event):
        x, y = event.x, event.y
        r, g, b = self._get_pixel(x, y)
        hex_color = "#%02x%02x%02x" % (r, g, b)

        # 확대경 이미지 생성
        half = MAGNIFIER_GRID_PX // 2
        left = max(0, x - half)
        top = max(0, y - half)
        right = min(self.img_w, x + half + 1)
        bottom = min(self.img_h, y + half + 1)
        crop = self.screenshot.crop((left, top, right, bottom))
        crop = crop.resize(
            (MAGNIFIER_GRID_PX * MAGNIFIER_ZOOM, MAGNIFIER_GRID_PX * MAGNIFIER_ZOOM),
            Image.NEAREST
        )
        draw = ImageDraw.Draw(crop)
        cx = cy = (MAGNIFIER_GRID_PX * MAGNIFIER_ZOOM) // 2
        s = MAGNIFIER_ZOOM // 2
        draw.rectangle(
            [cx - s, cy - s, cx + s, cy + s],
            outline="red", width=2
        )
        self.tk_magnifier_image = ImageTk.PhotoImage(crop)

        # 화면 밖으로 안 나가게 위치 보정
        mx = x + 25
        my = y + 25
        mag_size = MAGNIFIER_GRID_PX * MAGNIFIER_ZOOM
        if mx + mag_size > self.img_w:
            mx = x - mag_size - 25
        if my + mag_size + 30 > self.img_h:
            my = y - mag_size - 30

        if self.magnifier_id:
            self.canvas.delete(self.magnifier_id)
        if self.hex_text_id:
            self.canvas.delete(self.hex_text_id)
        if getattr(self, "hex_bg_id", None):
            self.canvas.delete(self.hex_bg_id)

        self.magnifier_id = self.canvas.create_image(mx, my, image=self.tk_magnifier_image, anchor="nw")
        self.hex_bg_id = self.canvas.create_rectangle(
            mx, my + mag_size, mx + mag_size, my + mag_size + 26,
            fill=hex_color, outline="#222222"
        )
        self.hex_text_id = self.canvas.create_text(
            mx + mag_size / 2, my + mag_size + 13,
            text=hex_color, fill=readable_text_color(hex_color),
            font=("Consolas", 11, "bold")
        )

    def _on_click(self, event):
        r, g, b = self._get_pixel(event.x, event.y)
        hex_color = "#%02x%02x%02x" % (r, g, b)
        self.destroy()
        self.on_pick(hex_color)

    def _cancel(self):
        self.destroy()


class ColorPaletteApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("컬러 팔레트 매니저")
        self.resizable(False, False)
        self.configure(bg="#1e1e1e")

        self.data = load_data()
        self.set_buttons = []
        self.swatch_widgets = []  # [(frame, canvas, label)] * SLOT_COUNT

        self._build_ui()
        self._refresh_all()

    # ---------- UI 구성 ----------

    def _build_ui(self):
        top = tk.Frame(self, bg="#1e1e1e")
        top.pack(padx=16, pady=(14, 6))

        for i in range(SET_COUNT):
            btn = tk.Button(
                top, text=self.data["set_names"][i], width=8,
                command=lambda idx=i: self._switch_set(idx),
            )
            btn.grid(row=0, column=i, padx=3)
            btn.bind("<Double-Button-1>", lambda e, idx=i: self._rename_set(idx))
            self.set_buttons.append(btn)

        hint = tk.Label(
            self, text="더블클릭: 세트 이름 변경 · 좌클릭: 색상 복사 · 우클릭: 색상 지정",
            bg="#1e1e1e", fg="#9a9a9a", font=("맑은 고딕", 9)
        )
        hint.pack(pady=(0, 10))

        mid = tk.Frame(self, bg="#1e1e1e")
        mid.pack(padx=16, pady=4)

        for slot in range(SLOT_COUNT):
            frame = tk.Frame(mid, bg="#1e1e1e")
            frame.grid(row=0, column=slot, padx=8)

            canvas = tk.Canvas(
                frame, width=SWATCH_SIZE, height=SWATCH_SIZE,
                highlightthickness=1, highlightbackground="#555555", cursor="hand2"
            )
            canvas.pack()
            canvas.bind("<Button-1>", lambda e, s=slot: self._on_swatch_click(s))
            canvas.bind("<Button-3>", lambda e, s=slot: self._show_context_menu(e, s))

            label = tk.Label(frame, text="비어있음", bg="#1e1e1e", fg="#cccccc", font=("Consolas", 9))
            label.pack(pady=(4, 0))

            self.swatch_widgets.append((frame, canvas, label))

        self.status_label = tk.Label(
            self, text="색상을 클릭하면 클립보드에 복사됩니다.",
            bg="#1e1e1e", fg="#4caf50", font=("맑은 고딕", 10, "bold")
        )
        self.status_label.pack(pady=(12, 14))

    # ---------- 상태 갱신 ----------

    def _refresh_all(self):
        self._refresh_set_buttons()
        self._refresh_swatches()

    def _refresh_set_buttons(self):
        current = self.data["current_set"]
        for i, btn in enumerate(self.set_buttons):
            btn.config(text=self.data["set_names"][i])
            if i == current:
                btn.config(relief="sunken", bg="#3a7bd5", fg="white", activebackground="#3a7bd5")
            else:
                btn.config(relief="raised", bg="#f0f0f0", fg="black")

    def _refresh_swatches(self):
        current_set = self.data["sets"][self.data["current_set"]]
        for slot, (frame, canvas, label) in enumerate(self.swatch_widgets):
            color = current_set[slot]
            canvas.delete("all")
            if color:
                canvas.config(bg=color)
                label.config(text=color.upper())
            else:
                canvas.config(bg="#2b2b2b")
                canvas.create_text(
                    SWATCH_SIZE / 2, SWATCH_SIZE / 2, text="+",
                    fill="#777777", font=("맑은 고딕", 20)
                )
                label.config(text="비어있음")

    # ---------- 이벤트 핸들러 ----------

    def _switch_set(self, idx):
        self.data["current_set"] = idx
        save_data(self.data)
        self._refresh_all()

    def _rename_set(self, idx):
        new_name = simpledialog.askstring(
            "세트 이름 변경", "새 이름을 입력하세요:",
            initialvalue=self.data["set_names"][idx], parent=self
        )
        if new_name:
            self.data["set_names"][idx] = new_name.strip()[:12]
            save_data(self.data)
            self._refresh_all()

    def _on_swatch_click(self, slot):
        current_set = self.data["sets"][self.data["current_set"]]
        color = current_set[slot]
        if not color:
            # 비어있으면 바로 색상 지정 다이얼로그
            self._pick_from_palette(slot)
            return
        self._copy_to_clipboard(color)

    def _copy_to_clipboard(self, hex_color):
        ok = False
        if pyperclip:
            try:
                pyperclip.copy(hex_color)
                ok = True
            except Exception:
                ok = False
        if not ok:
            # pyperclip 실패 시 tkinter 기본 클립보드로 대체
            self.clipboard_clear()
            self.clipboard_append(hex_color)
            self.update()
        self.status_label.config(text=f"복사됨: {hex_color.upper()}  (Ctrl+V로 붙여넣기 하세요)")

    def _show_context_menu(self, event, slot):
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(label="🎨 팔레트에서 색상 선택", command=lambda: self._pick_from_palette(slot))
        menu.add_command(label="💧 화면에서 스포이드로 추출", command=lambda: self._pick_from_screen(slot))
        current_set = self.data["sets"][self.data["current_set"]]
        if current_set[slot]:
            menu.add_separator()
            menu.add_command(label="📋 색상 코드 복사", command=lambda: self._copy_to_clipboard(current_set[slot]))
            menu.add_command(label="🗑 비우기", command=lambda: self._clear_slot(slot))
        menu.tk_popup(event.x_root, event.y_root)

    def _pick_from_palette(self, slot):
        current_set = self.data["sets"][self.data["current_set"]]
        initial = current_set[slot] or "#ffffff"
        rgb, hex_color = colorchooser.askcolor(color=initial, title="색상 선택")
        if hex_color:
            self._set_slot_color(slot, hex_color)

    def _pick_from_screen(self, slot):
        self.withdraw()  # 메인 창 숨기고 스포이드 오버레이 표시
        self.after(150, lambda: self._launch_overlay(slot))

    def _launch_overlay(self, slot):
        def on_pick(hex_color):
            self.deiconify()
            self._set_slot_color(slot, hex_color)

        overlay = EyedropperOverlay(self, on_pick)
        overlay.protocol("WM_DELETE_WINDOW", lambda: (overlay.destroy(), self.deiconify()))
        # ESC로 취소했을 때도 메인 창 복원
        overlay.bind("<Destroy>", lambda e: self.deiconify() if self.state() == "withdrawn" else None)

    def _set_slot_color(self, slot, hex_color):
        hex_color = hex_color.lower()
        self.data["sets"][self.data["current_set"]][slot] = hex_color
        save_data(self.data)
        self._refresh_swatches()
        self._copy_to_clipboard(hex_color)

    def _clear_slot(self, slot):
        self.data["sets"][self.data["current_set"]][slot] = None
        save_data(self.data)
        self._refresh_swatches()
        self.status_label.config(text="슬롯을 비웠습니다.")


if __name__ == "__main__":
    app = ColorPaletteApp()
    app.mainloop()
