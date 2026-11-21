"""BBK7980 experimental desktop emulator; the screen is rendered by stock firmware."""
import argparse
import json
from pathlib import Path
import sys
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk
from machine import Machine, ROOT, APP_DIR
from keyboard import KEYS, PANEL_ROWS, PANEL_FUNCTIONS, host_key, host_key_source
from audio_output import AudioOutput
from prepare import prepare

PALETTE=[235,241,220,153,169,131,83,105,65,26,45,25]+[0]*756

class Emulator:
    def __init__(self, window, options):
        self.window=window;self.options=options;self.running=True;self.pressed={}
        self.window.title('步步高 7980 模拟器')
        self.window.configure(bg='#e8e8e2');self.window.resizable(False,False)
        self.machine=Machine(options.runtime/'syscode.bin')
        self.data_dir=options.runtime/'data';self.data_dir.mkdir(exist_ok=True)
        self.audio_output=AudioOutput()
        self.save_path=self.data_dir/'nand.bin';self.closed=False
        self.smoke_error = None
        preset=options.runtime/'installed-nand.bin.z'
        source=Path(options.nand) if options.nand else self.save_path if self.save_path.exists() else preset
        self.machine.load_nand(source)
        outer=ttk.Frame(window,padding=(16,12));outer.pack()
        self.display_scale = 2 if window.winfo_screenheight() < 880 else 3
        ttk.Label(outer,text='BBK 7980',font=('Segoe UI',20,'bold')).pack(anchor='w')
        ttk.Label(outer,text='原厂 V1.10 系统 · 240 × 120 · 四级灰度').pack(anchor='w',pady=(0,12))
        self.screen=tk.Label(outer,bg='#35462d',bd=8,relief='sunken');self.screen.pack()
        self.font_notice=tk.StringVar(value='正在检查中文字库…')
        ttk.Label(outer,textvariable=self.font_notice,foreground='#805127').pack(pady=8)
        self.build_keypad(outer)
        row=ttk.Frame(outer);row.pack(pady=8)
        for label,action in [('暂停 / 继续',self.pause),('重启',self.reset),('保存',self.save),('截图',self.screenshot),('载入 NAND',self.open_nand),('按键矩阵',self.matrix)]:
            ttk.Button(row,text=label,command=action).pack(side='left',padx=3)
        self.status=tk.StringVar(value='正在启动…');ttk.Label(outer,textvariable=self.status).pack(anchor='w',pady=(8,0))
        window.bind('<KeyPress>',self.key_down);window.bind('<KeyRelease>',self.key_up)
        window.bind('<FocusOut>',lambda event:self.release_all())
        window.protocol('WM_DELETE_WINDOW',self.close)
        self.machine.run(80_000_000);self.update_font_notice()
        if options.minesweeper:self.launch_minesweeper()
        if hasattr(self.machine.lib,'bbk_audio_clear'):self.machine.lib.bbk_audio_clear()
        self.last_frame=None;self.render()
        window.after(16,self.step)
        if options.smoke_test:window.after(500,self.run_smoke_test)

    def build_keypad(self, parent):
        panel = ttk.Frame(parent, padding=(0, 0, 0, 4))
        panel.pack(fill='x')
        panel.columnconfigure(tuple(range(22)), weight=1, uniform='half_key')

        def place(label, code, row, column, span=2, rows=1):
            button = self.key_button(panel, label, code, width=1)
            button.grid(row=row, column=column, columnspan=span, rowspan=rows,
                        sticky='nsew', padx=2, pady=2)

        for row, keys in enumerate(PANEL_ROWS):
            margin = 11 - len(keys)
            for index, (label, code) in enumerate(keys):
                place(label, code, row, margin + 2 * index)

        column = 1
        for index, (label, code) in enumerate(PANEL_FUNCTIONS):
            span = 2 if index < 7 else 3
            place(label, code, 4, column, span)
            column += span

        place('Esc', KEYS['Escape'], 6, 5, 3)
        place('Enter', KEYS['Return'], 5, 8, 4, 2)
        place('↑', KEYS['Up'], 5, 14)
        place('←', KEYS['Left'], 6, 12)
        place('↓', KEYS['Down'], 6, 14)
        place('→', KEYS['Right'], 6, 16)
        place('上翻页', KEYS['Prior'], 5, 19, 3)
        place('下翻页', KEYS['Next'], 6, 19, 3)

    def key_button(self,parent,label,code,width=None):
        button=ttk.Button(parent,text=label,width=width if width is not None else max(5,len(label)+1),takefocus=False)
        button.bind('<ButtonPress-1>',lambda event:self.press(code,button))
        button.bind('<ButtonRelease-1>',lambda event:self.release(code,button))
        return button

    def press(self, code, source=None):
        source = ('direct', code) if source is None else source
        if source in self.pressed:
            return
        if code not in self.pressed.values():
            self.machine.lib.bbk_key(code//8, code%8, 1)
        self.pressed[source] = code

    def release(self, code, source=None):
        source = ('direct', code) if source is None else source
        released = self.pressed.pop(source, None)
        if released is not None and released not in self.pressed.values():
            self.machine.lib.bbk_key(released//8, released%8, 0)

    def release_all(self):
        for code in set(self.pressed.values()):
            self.machine.lib.bbk_key(code//8, code%8, 0)
        self.pressed.clear()

    def key_down(self,event):
        code = host_key(event, windows=sys.platform == 'win32')
        if code is not None:
            self.press(code, host_key_source(event))

    def key_up(self,event):
        source = host_key_source(event)
        self.release(self.pressed.get(source), source)

    def frame_image(self):
        im=Image.frombytes('P',(240,120),self.display_frame());im.putpalette(PALETTE)
        return im.convert('RGB')

    def display_frame(self):
        # V1.10 sets the LCD control stop bit when the power key puts it to sleep.
        return bytes(240 * 120) if self.machine.lib.bbk_read(0x47) & 0x80 else self.machine.frame()

    def render(self):
        frame=self.display_frame()
        if frame!=self.last_frame:
            self.last_frame=frame;im=Image.frombytes('P',(240,120),frame);im.putpalette(PALETTE)
            size=(240*self.display_scale,120*self.display_scale)
            self.photo=ImageTk.PhotoImage(im.resize(size,Image.Resampling.NEAREST));self.screen.configure(image=self.photo)

    def step(self):
        if self.closed:return
        if self.running:self.machine.run(66_667)
        self.audio_output.write(self.machine.audio())
        self.render();s=self.machine.state()
        self.status.set(f'{"运行中" if self.running else "已暂停"} · PC {s["pc"]:04X} · {s["cycles"]/4_000_000:.1f} 秒 · 方向键 / Enter / Esc / F1–F5')
        self.window.after(16,self.step)

    def pause(self):
        self.running=not self.running;self.release_all()
        if not self.running:self.audio_output.clear()
    def update_font_notice(self):
        text='兼容中文字库已启用。' if self.machine.lib.bbk_read(0x9eca)!=0xff else '当前镜像缺少中文字库，部分汉字显示为方块。'
        self.font_notice.set(text+(' PSG 旋律声音已启用；语音尚未实现。' if self.audio_output.available else ' 当前音频设备不可用。'))

    def reset(self):
        self.release_all();self.machine.lib.bbk_reset();self.machine.run(80_000_000);self.update_font_notice()
        if self.options.minesweeper:self.launch_minesweeper()
        self.audio_output.clear()
        if hasattr(self.machine.lib,'bbk_audio_clear'):self.machine.lib.bbk_audio_clear()

    def launch_minesweeper(self):
        # Drive the real shell and loader, including their normal file checks.
        for code in [43]*8+[6]:
            self.machine.lib.bbk_key(code//8,code%8,1);self.machine.run(300_000)
            self.machine.lib.bbk_key(code//8,code%8,0);self.machine.run(30_000_000 if code==6 else 5_000_000)

    def save(self):
        try:self.machine.save_nand(self.save_path);self.status.set('已保存到 '+str(self.save_path))
        except OSError as exc:messagebox.showerror('保存失败',str(exc))

    def screenshot(self):
        path=filedialog.asksaveasfilename(defaultextension='.png',filetypes=[('PNG 图片','*.png')])
        if path:self.frame_image().resize((960,480),Image.Resampling.NEAREST).save(path)

    def open_nand(self):
        path=filedialog.askopenfilename(filetypes=[('NAND 镜像','*.bin *.z'),('所有文件','*')])
        if not path:return
        try:self.machine.load_nand(path);self.reset()
        except (OSError,ValueError) as exc:messagebox.showerror('载入失败',str(exc))

    def matrix(self):
        panel=tk.Toplevel(self.window);panel.title('7980 原始按键矩阵')
        ttk.Label(panel,text='Y = 16；Esc = 49；Enter = 50；帮助 = 55；Delete = 56。').grid(row=0,column=0,columnspan=8,padx=10,pady=10)
        for code in range(64):self.key_button(panel,f'{code:02d}',code).grid(row=code//8+1,column=code%8,padx=3,pady=3)

    def smoke_test(self):
        before=self.machine.frame()
        code=50 if self.options.minesweeper else 43
        self.press(code);self.machine.run(8_000_000);self.release(code);self.render()
        if before==self.machine.frame():raise RuntimeError('Guest did not respond to its input')
        target=Path(self.options.smoke_test);target.parent.mkdir(parents=True,exist_ok=True)
        self.frame_image().save(target)
        self.window.update()
        from PIL import ImageGrab
        x,y=self.window.winfo_rootx(),self.window.winfo_rooty()
        width,height=self.window.winfo_width(),self.window.winfo_height()
        ImageGrab.grab(bbox=(x,y,x+width,y+height)).save(target.with_name(target.stem+'-window.png'))

    def run_smoke_test(self):
        try:
            self.smoke_test()
        except Exception as error:
            self.smoke_error = error
        finally:
            self.audio_output.close()
            self.closed = True
            self.window.quit()

    def close(self):
        self.release_all()
        try:self.machine.save_nand(self.save_path)
        except OSError as exc:
            messagebox.showerror('保存失败',str(exc));return
        self.audio_output.close();self.closed=True;self.window.destroy()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--version', action='version', version=(ROOT/'VERSION').read_text().strip())
    parser.add_argument('--runtime', type=Path, default=APP_DIR/'runtime')
    parser.add_argument('--prepare', type=Path, metavar='UPDATER')
    parser.add_argument('--nand', type=Path)
    parser.add_argument('--smoke-test', type=Path)
    parser.add_argument('--minesweeper', action='store_true')
    args = parser.parse_args()
    window = tk.Tk()
    window.withdraw()
    try:
        if args.prepare or not (args.runtime/'installed-nand.bin.z').is_file():
            run_setup(window, args)
            if not (args.runtime/'installed-nand.bin.z').is_file():
                window.destroy()
                return
        if args.minesweeper:
            manifest = json.loads((args.runtime/'installed-manifest.json').read_text(encoding='utf8'))
            if not any(record['name'] == '扫雷.exe' for record in manifest['verified']):
                raise ValueError('当前运行镜像未安装扫雷。请用带有扫雷示例的发行包重新初始化。')
        emulator = Emulator(window, args)
        window.deiconify()
        window.mainloop()
        if emulator.smoke_error:
            raise emulator.smoke_error
        if args.smoke_test:
            window.destroy()
    except (OSError, ValueError, RuntimeError) as error:
        if args.smoke_test:
            window.destroy()
            raise
        messagebox.showerror('步步高 7980 模拟器', str(error), parent=window)
        window.destroy()


def run_setup(window, args):
    updater = args.prepare or filedialog.askopenfilename(
        parent=window, title='选择步步高 7980 V1.10 官网升级包',
        filetypes=[('步步高升级包', '*.exe'), ('所有文件', '*')])
    if not updater:
        return
    window.title('初始化步步高 7980')
    window.protocol('WM_DELETE_WINDOW', lambda: None)
    panel = ttk.Frame(window, padding=24)
    panel.pack()
    status = tk.StringVar()
    ttk.Label(panel, width=48, textvariable=status).pack()
    window.deiconify()

    def progress(message):
        status.set(message)
        window.update_idletasks()

    demo_paths = (ROOT/'demo/minesweeper.exe', ROOT/'build/demo/minesweeper.exe')
    demo = next((path for path in demo_paths if path.is_file()), None)
    try:
        prepare(updater, args.runtime, demo, progress)
    finally:
        panel.destroy()


if __name__ == '__main__':
    main()
