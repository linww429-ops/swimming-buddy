# Swimming Buddy｜泳搭子

把泳训截图和当天体感，变成一张今日战报和一句现场锐评。

![Swimming Buddy演示战报：全部数据为虚构](docs/demo-phone.png)

当前候选版本：`1.2.15-rc.1+fresh-quips.20261108`。可先用随包合成数据体验；正式运动记录需另行提供。

## 能做什么

- 由AI助手读取手表或App截图中清晰的距离、用时、配速、心率、划数和分段，保留原值、范围与来源。
- 生成手机PNG、高清PNG和数据报告，包含五维娱乐评分、动物装饰与完整百米成绩参考。
- 根据当天具体数据和本人实际体感，现场写一句不超过45字的锐评。不会从固定句库抽一句再换距离。
- 本人确认身份并授权保存后，可维护包外私有台账；首次体验、他人数据或演示采用不保存方式。

## 怎样使用

它是一套配合Codex等支持Skills的AI助手使用的技能，不是独立手机App。脚本负责校验和绘图；看图、追问体感与创作文案由宿主AI完成，没有独立OCR服务，也不会自行调用文案生成API。

需要Python 3.10或以上及Pillow 12.3.0。已实际验证的本机组合为macOS、Python 3.14.6、Pillow 12.3.0；未把这次验证扩展成全部平台或全部最低版本均通过。

下载解压技能包后，在技能目录中准备依赖并安装：

```bash
python -m pip install -r requirements.txt
python scripts/install.py
```

安装器默认写入`$CODEX_HOME/skills/swimming-buddy`，没有CODEX_HOME时使用`~/.codex/skills/swimming-buddy`。已有同名技能时先比较、备份，安装器会拒绝直接覆盖未知修改。Windows、Linux或自定义宿主的发现/加载方式以其实际环境为准，不承诺自动触发。

在Codex中调用：

```text
$swimming-buddy
帮我看看这次游泳，生成今日战报。
我今天前面比较轻松，后半程胳膊有点酸，最后50米冲了一下。
先体验，不保存。
```

同时上传运动概览和分段截图即可。没有提供体感时会先问一句；明确跳过后只据已有数据写，不补造感受。成人百米参考首次需要时询问组别，不从姓名或图像猜测。职业或兴趣偏好可以不填。

## 先看一个演示

图中是虚构的1000米自由泳、21分40秒。模拟体感为前300米轻松、600米后胳膊酸、最后50米主动加速。现场点评是：

> 胳膊600米就想散会，你却让它在最后50米返场。

[高清示例](docs/demo-full.png)和[完整合成输入](docs/demo-input.json)均随包提供。示例没有使用任何人的真实运动记录，也没有写入私有台账。

## 本地演示与校验

```bash
python -B scripts/run.py --input docs/demo-input.json --ledger ./private-ledger --output ./demo-output --no-save
python -B scripts/verify_package.py
python -B -m unittest discover -s scripts -p "test*.py"
```

真实调用前，由宿主按[输入规范](references/input.md)整理截图，并按[现场文案规范](references/persona.md)填写现场创作的`quip`；用户不需要手工编JSON。缺文案或近期重复时，程序提示宿主补写/重写，不自动回退模板。明确不适时使用现场关怀语，不拿不适开玩笑。

## 数据与评价

看不清的原始数值保持未知。平均配速不冒充最快完整100米，不能跨泳姿、池长或设备计数口径随意比较。五维星级与“牛马指数”是娱乐评价，不是科学体能测定或医学判断。宿主AI处理截图时适用其自身的数据处理规则，不能把本地绘图误称为整个工作流完全离线。

不要把真实台账、未脱敏截图、头像、姓名或健康记录提交到公开仓库/Issue；本仓库只带合成样例。

## 许可

项目原创代码、文档、文案和动物装饰采用[MIT](LICENSE)。字体保持OFL-1.1，详见[来源与许可](LICENSING.md)及[第三方说明](THIRD_PARTY_NOTICES.md)。

## English

Swimming Buddy is a host-assisted skill that turns readable pool-swimming screenshots and self-reported feelings into a report card and one freshly written humorous line. The Python scripts validate inputs and render PNGs; the host assistant reads images and writes the line. It is not a standalone mobile app or an independent OCR service.

All distributed examples are synthetic. Local health records are separate from the skill package and require explicit consent before saving. Scores are for entertainment. Original project content is MIT-licensed; the bundled Noto font retains its OFL license.
