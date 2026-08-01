# AtCoder 提交记录与源码批量导出工具

本工具用于批量导出本人某场 AtCoder 比赛的提交记录和完整源码。

导出内容包括：

- AC、WA、CE、TLE 等全部提交；
- 每份提交的完整源码和注释；
- 提交 ID、提交时间、比赛内相对时间；
- 题目、语言、得分、代码长度；
- 运行时间与内存；
- 原题和原提交链接；
- 汇总表 `manifest.csv`；
- 元数据 `submissions.json`；
- 自动生成 ZIP。

---

# 一、为什么使用 REVEL_SESSION

AtCoder 没有提供与 Codeforces `includeSources` 类似的官方源码 API。

本工具不保存 AtCoder 密码，也不自动绕过登录验证码，而是使用你已经在浏览器中登录后产生的：

```text
REVEL_SESSION
```

它相当于当前浏览器登录会话。工具通过：

```text
/contests/比赛ID/submissions/me
```

读取当前账号自己的提交，再逐份读取源码。

---

# 二、目录内容

```text
atcoder_submission_exporter/
├─ 开始导出_AtCoder.bat      推荐：直接双击
├─ atcoder_config.ini        保存用户名和 REVEL_SESSION
├─ atcoder_export_click.py   双击模式入口
├─ atcoder_export_core.py    共用核心
├─ atcoder_export_fast.py    命令行快速版
├─ atcoder_export_pause.py   命令行暂停版
├─ run_fast.bat              快速版包装
├─ run_pause.bat             暂停版包装
└─ README.md                 本教程
```

不要只移动 `.bat`。这些文件必须位于同一目录。

需要桌面入口时，应创建 `.bat` 的快捷方式。

---

# 三、从零开始使用

## 第 1 步：安装 Python

需要 Python 3.10 或更高版本。

在 Windows 安装 Python 时勾选：

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

本工具只使用 Python 标准库，不需要执行 `pip install`。

---

## 第 2 步：在浏览器登录 AtCoder

在 Chrome 或 Edge 中打开：

```text
https://atcoder.jp/login
```

正常完成登录。

不要把 AtCoder 密码写进配置文件。

---

## 第 3 步：复制 REVEL_SESSION

以下以 Chrome / Edge 为例。

1. 保持 AtCoder 登录状态。
2. 打开 `https://atcoder.jp/`。
3. 按 `F12` 打开开发者工具。
4. 切换到：

```text
Application
```

中文界面可能显示为：

```text
应用
```

5. 左侧展开：

```text
Storage
└─ Cookies
   └─ https://atcoder.jp
```

6. 在右侧 Cookie 表中找到：

```text
REVEL_SESSION
```

7. 双击该行的 `Value`，完整复制其值。

如果没有看到 `Application`：

- 点击开发者工具顶部的 `>>`；
- 从隐藏标签中选择 `Application`。

注意复制的是 `Value`，不是 Cookie 名称，也不要复制整行。

---

## 第 4 步：填写配置文件

用记事本打开同目录下：

```text
atcoder_config.ini
```

初始内容：

```ini
[account]
handle=Whalica
revel_session=请填写你的_REVEL_SESSION

[settings]
request_interval=1.0
```

修改为：

```ini
[account]
handle=Whalica
revel_session=这里粘贴完整的Cookie值

[settings]
request_interval=1.0
```

要求：

- 不要删除 `[account]` 和 `[settings]`；
- `handle` 填 AtCoder 用户名；
- `revel_session` 不要加引号；
- 不要在值前后添加空格；
- `request_interval` 建议保持 `1.0` 或更大。

---

## 第 5 步：双击启动

双击：

```text
开始导出_AtCoder.bat
```

程序会询问：

```text
请输入比赛 ID（例如 abc469）:
请输入最多导出的提交数 [200]（0 表示全部）:
```

例如：

```text
请输入比赛 ID（例如 abc469）: abc469
请输入最多导出的提交数 [200]（0 表示全部）:
```

第二项直接按 Enter 使用默认值 `200`。

## 比赛 ID 怎么找

比赛链接例如：

```text
https://atcoder.jp/contests/abc469
```

比赛 ID 就是：

```text
abc469
```

它不一定是纯数字，常见形式包括：

```text
abc469
arc200
agc070
ahc069
typical90
practice
```

## “最多导出的提交数”是什么意思

它是该场比赛最多导出多少份本人提交：

- `200`：最多导出 200 份；
- `20`：最多导出最近 20 份；
- `0`：导出该场全部本人提交。

列表按 AtCoder 页面从新到旧读取，导出文件最终会按每题从早到晚排序。

---

# 四、查看输出

例如导出 `abc469`，会在工具目录生成：

```text
atcoder_export_Whalica_abc469/
atcoder_export_Whalica_abc469.zip
```

目录结构类似：

```text
atcoder_export_Whalica_abc469/
├─ A/
│  └─ 01_提交ID_AC_at-00-05-18.cpp
├─ B/
│  ├─ 01_提交ID_WA_at-00-22-40.cpp
│  └─ 02_提交ID_AC_at-00-27-11.cpp
├─ D/
│  ├─ 01_提交ID_WA_at-01-15-03.cpp
│  └─ 02_提交ID_AC_at-01-31-20.cpp
├─ manifest.csv
├─ submissions.json
└─ README.md
```

如果无法读取比赛开始时间，文件名中的相对时间会显示：

```text
at-unknown
```

但 `manifest.csv` 中仍会保存实际提交时间。

---

# 五、双击版默认行为

双击版会：

- 只读取当前登录账号自己的 `/submissions/me`；
- 导出该场全部 verdict；
- 自动生成 ZIP；
- 再次运行同一场时覆盖旧目录和 ZIP；
- 每次请求之间至少等待配置的间隔；
- 成功或报错后暂停，不会闪退。

---

# 六、常见错误

## 1. 提示找不到 Python

重新安装 Python，并勾选：

```text
Add Python to PATH
```

也可以先测试：

```powershell
py --version
```

## 2. 提示找不到 `atcoder_config.ini`

确认以下文件在同一目录：

```text
开始导出_AtCoder.bat
atcoder_export_click.py
atcoder_export_core.py
atcoder_config.ini
```

## 3. 提示填写 `revel_session`

配置文件仍然保留了占位文字。重新复制 Cookie 值并粘贴。

## 4. 被重定向到登录页

通常说明：

- REVEL_SESSION 已过期；
- Cookie 没有完整复制；
- 浏览器退出登录；
- AtCoder 主动刷新了会话。

重新登录 AtCoder，再按教程复制新的 REVEL_SESSION。

## 5. 用户名与 Cookie 账号不一致

程序会比较：

- 配置文件中的 `handle`；
- `/submissions/me` 页面中的提交用户。

两者不一致时会停止，避免把错误账号的数据导出到错误目录。

## 6. HTTP 403 或 429

可能原因：

- AtCoder 暂时限制了自动访问；
- 请求间隔过低；
- Cookie 失效；
- 网络环境触发了防护。

处理方法：

1. 保持 `request_interval=1.0` 或改为 `2.0`；
2. 等待网站恢复正常后重新运行；
3. 重新复制 REVEL_SESSION；
4. 用浏览器确认该提交页面能够正常打开。

## 7. 找不到比赛提交

检查：

- 比赛 ID 是否正确；
- Cookie 对应账号是否正确；
- 当前账号是否在该场有提交；
- 是否输入了错误的比赛简称。

## 8. 找不到源码

可能是：

- REVEL_SESSION 没有查看该源码的权限；
- Cookie 已过期；
- AtCoder 页面结构发生变化；
- 该提交的源码可见性受到限制。

先在浏览器中打开该提交详情，确认本人能看到源码。

## 9. 程序运行较慢

程序需要逐份访问提交详情页才能取得源码，因此请求数大致为：

```text
提交列表页数 + 提交数量 + 1
```

不建议把 `request_interval` 调得很低，以免触发网站限制。

---

# 七、命令行版本

双击版使用 `atcoder_config.ini`。

命令行快速版示例：

```powershell
python atcoder_export_fast.py `
  --handle Whalica `
  --contest-id abc469 `
  --revel-session "你的Cookie值" `
  --max-submissions 200 `
  --zip
```

暂停版：

```powershell
python atcoder_export_pause.py `
  --handle Whalica `
  --contest-id abc469 `
  --revel-session "你的Cookie值" `
  --max-submissions 200 `
  --zip
```

查看参数：

```powershell
python atcoder_export_fast.py --help
```

## 只导出 AC

```powershell
python atcoder_export_fast.py `
  --handle Whalica `
  --contest-id abc469 `
  --revel-session "你的Cookie值" `
  --status AC `
  --zip
```

## 同时导出 AC 和 WA

```powershell
python atcoder_export_fast.py `
  --handle Whalica `
  --contest-id abc469 `
  --revel-session "你的Cookie值" `
  --status AC `
  --status WA `
  --zip
```

## 覆盖已有结果

添加：

```text
--overwrite
```

## 调整请求间隔

```text
--request-interval 2.0
```

---

# 八、安全说明

`REVEL_SESSION` 是登录会话凭证，敏感程度接近密码。

必须注意：

1. 不要把填写后的 `atcoder_config.ini` 发给别人；
2. 不要上传到 GitHub、公开网盘或群文件；
3. 发送工具前恢复配置文件中的占位文字；
4. Cookie 泄露后，立即退出 AtCoder 登录并重新登录；
5. 不要在直播、截图或录屏中展示开发者工具里的 Cookie；
6. 导出的源码可能包含个人模板、注释和未公开思路，分享前先检查。

---

# 九、比赛规则提醒

不要在正在进行的 AtCoder 比赛中，把题面或赛时代码交给生成式 AI 分析。

本工具定位为个人赛后归档和复盘工具。建议在比赛结束后使用。
