# Codeforces 提交记录与源码批量导出工具

本工具可以批量导出本人 Codeforces 提交记录和完整源码，不需要逐个打开提交页面。

当前包提供两种使用方式：

1. **双击使用**：填写一次 `cf_config.ini`，以后双击 `开始导出.bat`，再输入场次 ID 和扫描提交数。
2. **命令行使用**：继续使用 `cf_export_fast.py` 或 `cf_export_pause.py`。

---

# 一、最简单的双击用法

## 第 1 步：安装 Python

需要 Python 3.10 或更高版本。

Windows 安装 Python 时务必勾选：

```text
Add Python to PATH
```

安装后打开 PowerShell，输入：

```powershell
python --version
```

或：

```powershell
py --version
```

能够显示 Python 版本即可。

本工具只使用 Python 标准库，不需要安装第三方包。

---

## 第 2 步：创建 Codeforces API Key

1. 登录 Codeforces。
2. 点击右上角头像。
3. 进入 `Settings`。
4. 打开 `API` 页面。
5. 点击 `Add API key`。
6. 保存生成的：
   - API Key
   - API Secret

API Secret 相当于密码，不要公开，也不要把整个工具目录上传到公开仓库。

---

## 第 3 步：填写配置文件

用记事本打开同目录下的：

```text
cf_config.ini
```

初始内容：

```ini
[account]
handle=Whalica
api_key=请填写你的_API_Key
api_secret=请填写你的_API_Secret
```

修改为自己的信息，例如：

```ini
[account]
handle=Whalica
api_key=xxxxxxxxxxxxxxxx
api_secret=yyyyyyyyyyyyyyyyyyyy
```

注意：

- 不要删除 `[account]`；
- 等号两边可以不留空格；
- API Key 和 Secret 不要加引号；
- `handle` 必须是创建这组 API Key 的 Codeforces 账号；
- 配置文件使用明文保存 Secret，请勿公开分享。

---

## 第 4 步：双击启动

双击：

```text
开始导出.bat
```

程序会显示当前配置的用户名，然后询问：

```text
请输入场次 ID:
请输入要扫描的最近提交数 [300]:
```

例如导出比赛 `2248`：

```text
请输入场次 ID: 2248
请输入要扫描的最近提交数 [300]: 300
```

第二项直接按 Enter，默认扫描最近 300 次提交。

如果目标比赛较早，最近 300 次提交中找不到，可输入：

```text
1000
```

或：

```text
5000
```

---

## 第 5 步：查看结果

运行成功后，会在工具目录生成：

```text
cf_export_Whalica_2248/
cf_export_Whalica_2248.zip
```

目录结构类似：

```text
cf_export_Whalica_2248/
├─ 2248/
│  ├─ A/
│  │  └─ 01_提交ID_AC_at-00-09-20.cpp
│  ├─ B/
│  │  └─ 01_提交ID_AC_at-00-44-19.cpp
│  └─ D/
│     ├─ 01_提交ID_WA_pretest-2_at-01-22-xx.cpp
│     └─ 02_提交ID_AC_at-01-35-20.cpp
├─ manifest.csv
├─ submissions.json
└─ README.md
```

程序默认：

- 只导出该场比赛的 `CONTESTANT` 正式参赛提交；
- 包含 AC、WA、CE、TLE 等全部 verdict；
- 自动生成 ZIP；
- 再次导出同一场时覆盖旧结果；
- 成功或报错后都会暂停，不会闪退。

---

# 二、各文件作用

```text
cf_submission_exporter_click/
├─ 开始导出.bat             推荐：直接双击
├─ cf_config.ini            保存用户名、API Key、API Secret
├─ cf_export_click.py       双击模式入口
├─ cf_export_core.py        共用导出核心
├─ cf_export_fast.py        命令行快速版
├─ cf_export_pause.py       命令行暂停版
├─ run_fast.bat             命令行快速版包装
├─ run_pause.bat            命令行暂停版包装
└─ README.md                使用教程
```

---

# 三、双击版的输入规则

## 用户名、Key 和 Secret

从同目录下的 `cf_config.ini` 读取。

## 场次 ID

每次运行时键盘输入。

场次链接例如：

```text
https://codeforces.com/contest/2248
```

其中场次 ID 是：

```text
2248
```

## 扫描提交数

每次运行时键盘输入。

它表示：

> 先读取该用户最近多少次提交，再从中筛选目标场次。

它不是“该场导出多少份”。

例如：

- 输入 `300`：从最近 300 次提交中查找；
- 输入 `1000`：从最近 1000 次提交中查找；
- 输入 `5000`：适合更早的比赛。

数字越大，网络请求和处理时间可能越长。

---

# 四、常见错误

## 1. 双击后提示未找到 Python

重新安装 Python，并勾选：

```text
Add Python to PATH
```

也可以测试：

```powershell
py --version
```

## 2. 提示找不到 `cf_config.ini`

确认这些文件位于同一个目录：

```text
开始导出.bat
cf_export_click.py
cf_config.ini
cf_export_core.py
```

不要只把 `.bat` 单独移动到桌面。

需要桌面入口时，应创建 `.bat` 的快捷方式，而不是移动原文件。

## 3. 提示填写 `api_key` 或 `api_secret`

打开 `cf_config.ini`，将占位文字替换为真实值。

## 4. API 签名错误

检查：

- Key 和 Secret 是否复制完整；
- 是否混用了两组不同的 Key 和 Secret；
- 本机时间是否准确；
- Secret 前后是否有多余空格。

Windows 可执行：

```text
设置 → 时间和语言 → 日期和时间 → 立即同步
```

## 5. 找不到该场提交

增加扫描提交数，例如从 `300` 改成 `1000` 或 `5000`。

还需要确认：

- 场次 ID 是否正确；
- `handle` 是否正确；
- 该账号是否正式参加过比赛。

双击版默认只导出 `CONTESTANT` 提交。赛后 Practice 提交不会被导出。

## 6. 想导出 Practice 提交

使用命令行版本，或编辑 `cf_export_click.py`，删除以下两个参数：

```python
"--participant-type",
"CONTESTANT",
```

## 7. 输出目录被覆盖

双击版默认启用 `--overwrite`。

这意味着再次导出同一个用户、同一场次时，会删除并重建：

```text
cf_export_用户名_场次ID
```

如需保留旧版本，先手动重命名旧目录或 ZIP。

---

# 五、命令行版本

配置文件只用于双击版。原有命令行版仍然可用。

快速版：

```powershell
python cf_export_fast.py --handle Whalica --count 300 --contest-id 2248 --zip
```

暂停版：

```powershell
python cf_export_pause.py --handle Whalica --count 300 --contest-id 2248 --zip
```

命令行版默认从环境变量读取：

```text
CF_API_KEY
CF_API_SECRET
```

也可以通过 `--api-key` 和 `--api-secret` 提供，但不推荐，因为可能进入终端历史记录。

查看完整参数：

```powershell
python cf_export_fast.py --help
```

---

# 六、安全说明

`cf_config.ini` 会以明文保存 API Secret。

因此：

1. 不要将填写后的配置文件发给别人；
2. 不要上传到 GitHub、网盘公开链接或群文件；
3. 发送工具给别人前，将配置文件恢复为占位内容；
4. Secret 泄露后，立即去 Codeforces API 页面撤销并重新生成；
5. 导出的源码也可能包含模板、注释和未公开思路，分享前先检查。
