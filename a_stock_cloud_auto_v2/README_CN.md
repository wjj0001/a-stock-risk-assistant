# A股云端自动行情 + 微信提醒版 v2

这个版本适合你：Mac 不用安装 Python，网页放在云端，GitHub Actions 自动抓取 A 股行情，计算风险，并通过 PushPlus 推送到微信。

## 已内置股票

持仓：
- 603019 中科曙光，成本 99.817，数量 100
- 001270 铖昌科技，成本 163.23，数量 300
- 600584 长电科技，成本 96.278，数量 100

关注：
- 002463 沪电股份
- 002636 金安国纪
- 000636 风华高科
- 002896 中大力德
- 603538 美诺华

## 你需要准备

1. GitHub 账号：https://github.com
2. PushPlus token：https://www.pushplus.plus

如果暂时没有 PushPlus token，网页自动行情仍可用，只是不会微信推送。

## 部署步骤

### 1. 新建 GitHub 仓库

登录 GitHub，点击右上角 `+` → `New repository`。

建议仓库名：

```text
a-stock-risk-assistant
```

选择 Public 或 Private 都可以。为了 GitHub Pages 简单，建议先用 Public。

### 2. 上传本项目所有文件

把压缩包解压后，将里面的文件全部上传到仓库根目录：

```text
index.html
portfolio.json
requirements.txt
scripts/update_data.py
.github/workflows/update.yml
```

注意：`.github` 文件夹也要上传。

### 3. 打开 GitHub Pages

进入仓库：

`Settings` → `Pages`

Source 选择：

```text
Deploy from a branch
```

Branch 选择：

```text
main / root
```

保存后，GitHub 会给你一个网址，例如：

```text
https://你的用户名.github.io/a-stock-risk-assistant/
```

### 4. 手动运行一次自动行情

进入仓库：

`Actions` → `update-a-share-data` → `Run workflow`

等待 1-3 分钟。运行成功后，会生成：

```text
data/latest.json
data/report.txt
```

然后打开你的 GitHub Pages 网页，就能看到自动行情结果。

### 5. 设置微信提醒

在 PushPlus 官网拿到 token 后：

进入 GitHub 仓库：

`Settings` → `Secrets and variables` → `Actions` → `New repository secret`

Name 填：

```text
PUSHPLUS_TOKEN
```

Secret 填你的 PushPlus token。

保存后，以后 GitHub Actions 每次运行都会推送微信提醒。

## 自动更新时间

默认每天交易日运行两次：

- 中国时间 15:45：收盘后更新
- 中国时间 20:00：晚上复查提醒

配置文件在：

```text
.github/workflows/update.yml
```

## 修改股票

修改：

```text
portfolio.json
```

格式示例：

```json
{"code":"600519","name":"贵州茅台","type":"持仓","cost":1500,"quantity":100}
```

关注股的 cost 和 quantity 可以写 null。

## 重要说明

- 本工具不接券商账户，不会自动交易。
- 数据来自 AkShare 的公开行情接口，偶尔可能失败，重新运行 Actions 即可。
- 输出仅用于个人风险观察，不构成投资建议。
