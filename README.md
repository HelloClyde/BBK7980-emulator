# 步步高 7980 模拟器

在 Windows 上运行朗文 7980 的 V1.10 系统。模拟器包含 65C02 指令、存储分页、定时器、中断、240 × 120 四级灰度 LCD、按键矩阵、UART 和虚拟 NAND。面板按 7980 真机照片排布，四方向键已在原厂工具菜单中逐一核对。

![Windows 模拟器运行 SDK 扫雷，屏幕下方为真机布局键盘](assets/minesweeper-window.png)

## 下载与运行

1. 下载并完整解压 [Windows x64 便携版](https://github.com/HelloClyde/BBK7980-emulator/releases/tag/v0.6.1)。
2. 保存[步步高官网 7980 V1.10 升级包](https://down.eebbk.net/xzzx/7980/1/7980sj.exe)。这是模拟器首次启动时要选的文件。
3. 打开 `BBK7980.exe`，选择刚下载的 `7980sj.exe`。模拟器读取其资源，格式化虚拟 NAND、安装字库和应用，并逐一读回检查。导入可能需要一分钟左右。
4. 打开「娱乐」中的《扫雷》，用方向键移动，Enter 翻开格子，空格插旗，Esc 退出。

升级包 SHA-256 为 `b9c4aa62cd9517859930620cdce5f7c6027120777926bb49e56989bb4e8d145c`。ZIP 的 SHA-256 随 Release 提供。便携版包含开源字库及扫雷，原厂固件和应用由导入步骤在本地生成。

## 键盘和存档

| 电脑按键 | 模拟器按键 |
| --- | --- |
| 方向键、Enter、Esc | 四方向、确认、退出 |
| Page Up / Page Down | 上翻页 / 下翻页 |
| Home | 目录 |
| Backspace / Delete | 删除 |
| F1–F5 / F6 | F1–F5 / 帮助 |
| Caps Lock / Shift | 大小写 / Shift |

数字、字母、空格可直接输入，电源、字体、帮助、输入法和中英符也可以在面板上点选。菜单中的「载入 NAND」可打开同一模拟器格式的 NAND 文件。

初次导入生成的 `runtime/` 包含基准镜像、导入清单和字库。点「保存」或正常退出会把用户镜像写入 `runtime/data/nand.bin`。迁移便携版时可一并复制整个 `runtime/`，或者把旧版的 `data/nand.bin` 备份后复制到该位置。

## 单个文件的导入和导出

- 点「导入文件」并选择普通数据文件或 7980 SDK 生成的 `BJBBK.110` 应用传输包。普通数据文件沿用文件名，应用沿用包内的文件名和分类。导入会逐字节读回校验，通过后保存到当前 NAND。确认导入时，同名机内文件会被替换。
- 点「导出文件」，输入机内完整文件名（含扩展名，区分大小写），再选择电脑上的保存位置。导出的是机内文件原始内容，应用的 PC 传输包头需要使用 SDK 另行生成。
- 两项操作都通过原厂「电脑联机」，会重启模拟器。请先在当前应用里保存进度。

## 从源码运行

需要 Windows x64、Python 3.11 和 MSYS2 UCRT64 GCC。将 UCRT64 的 `bin` 加入 PATH，然后在项目根目录运行：

```powershell
python -m pip install -r requirements.txt
python build.py
python tools/build_demo.py
python app.py
```

`tools/build_demo.py` 从固定的 SDK v1.1.1 发行资产构建扫雷，核对资产的 SHA-256，在临时副本里修正 SDK 的四个方向键编号，并让扫雷使用这些键值。也可用 `--sdk-archive PATH` 指定同一个已下载的 SDK ZIP。省略这一步时，首次导入只安装官网包和兼容字库。

```powershell
python prepare.py C:\path\to\7980sj.exe
python -m unittest discover -s tests -v
python -m pip install -r requirements-build.txt
python package.py
python tools/verify_release.py dist
```

未导入官网包时，测试使用合成 ROM 检查 CPU、中断及 NAND，原厂系统的集成测试会跳过。安装后的测试覆盖格式化、串口往返、菜单、按键、字库读取。GitHub Actions 从公开源码构建并检查便携包。

## 已知限制和许可

兼容字库基于 GNU Unifont，字形与原厂字库有差别。PSG 方波旋律可输出，原机语音尚未实现，中文输入法仍有兼容问题。RAM 和部分外设的参数是模拟模型，真机容量和完整电气时序仍待确认。更多实现细节见 [硬件研究](hardware.md)。

模拟器采用 [GPL-3.0](COPYING)。感谢 9288 / GAM4980 和 Unifont 的贡献者，见 [第三方组件与致谢](THIRD_PARTY.md)。
