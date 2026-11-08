# 输入JSON与字段 · 1.2.2

封套必需person_id、record；正式本人保存需owner_confirmed=true。可选history仅用于mode=demo的合成no-save校验；recent_presentations仅临时展示选择；dimensions是宿主逐轴娱乐估值起点；feedback分开保存主观来源。

feedback可含pre_session_intent、post_session_feeling、post_session_final_phase_feeling、subjective_effort（数字1–5）、discomfort（true/false/null，仅用户明确报告）。不把游前“轻松”当游后体感，不把疲劳自动当不适。明确游后反馈优先于宿主估值；数字投入仅改投入轴。

完整record参见record.schema.json。真实记录mode=real，person_id与封套一致，未知discomfort=null；intent不清用unspecified；泳训日期从截图/用户确认，不用上传日。无总用时不补elapsed_s，无分段用segments=null。

metrics每项保留id/key/qualifier/label/raw_value/raw_unit/value/unit/time_basis/status/source，可选scope保存原范围（如session、segment:2、每趟）。id包含来源区分，跨图相同id原文冲突会停止，不默默择优。缺值status=missing/uncertain且value=null，原字符仍保留；未知字段用扩展key。

距离/池长规范为米，只在原单位明确时转换（1yd=0.9144m），原码制值/单位仍显示。pool_length_m允许明确的小数池长。pace.unit可为s/100m、s/100yd或s/unknown，分母未知不按品牌补；time_basis另区分active/elapsed/unspecified，不混同分母距离。热量规范kcal只在原单位确实时转换；activity/total/unspecified不混。

scope不是装饰标签：分段值不能覆盖全程；报告保留每条原范围，「本次参数」只选全程值及满足合规条件的全程聚合值，最多六项。单双臂计数需实际证据，以swolf_basis或其它扩展指标保留，否则SWOLF不用于经济性对照。

固定参数顺序为总热量、活动热量、平均心率、总划水次数、平均划频、平均SWOLF；缺项前移，其余确认的全程设备指标补位。六个卡位的几何与字号不随设备或字段数量变化；长标签省略、长数值显示「详见报告」，原文与完整范围仍留在report。

核心缺失可只给mode与metrics，脚本仍出固定「今日战报」布局、report保留原文，partial不正式入账。没有任何可读泳训参数时轻问核对；过长文字需附页，不能缩成不可读小字。目录在技能包之外，归属于该人；未授权他人用no-save不读取私有历史。

没有默认真实数据。synthetic.json及examples目录均明显合成，所有业务演示带--no-save。
# 1.2 附加输入

`adult_group` 仅接受本人明确的 `male`/`female`；不确定时省略并在聊天首次询问。同一 `person_id` 的已存组别沿用；本人主动更正时同时给 `adult_group_correction: true`。单次 `--no-save` 的答案只影响当次卡，不写档案。

`fastest_100m` 可为 `{"seconds": 100, "stroke": "freestyle", "source": "screenshot"}` 或 `source: "user_confirmed"`。必须是真正完整100米用时，泳姿字段与全程记录一致；混合泳可明确写mixed；每条原始来源写入 record.metrics。若实有100米分段且距离/用时明确，也可自动取最快完整100米。平均配速、最佳瞬时速度、50米分段不可替代。未知时省略，卡面不显示缺项说明；无可判海豚评级时不显示图标或文字。

完整分段可再写 `segment_index`（保留原始趟号，局部缺失不重排）、`stroke_count`、`stroke_count_basis`（`arm_strokes`/`cycles`/`unknown`）、`stroke`、`pool_length_m`、`includes_rest`。只在不重叠、全程覆盖、活动时间一致、每段泳姿明确且同池长/单臂计数定义时合计划水数和平均划频。平均SWOLF仅在每段都是完整趟、活动用时与划水定义均已知时算 `Σ(分段活动秒数+对应划水次数)/Σ完整趟数`；不能反推出各趟SWOLF。原指标与计算结果冲突则保留原值并警告。源字段全部留在报告，本次参数卡最多六项；能量kJ/kcal不混算。[Garmin官方说明](https://developer.garmin.com/connect-iq/api-docs/Toybox/Activity/Info.html)以每趟秒数加每趟划水数定义SWOLF，其设备划数口径不能套用其它品牌。

热量保留截图原值、精度、单位与活动/总量口径；仅确认的 `kcal` 与 `kJ` 可按 `1 kcal = 4.184 kJ` 单次换算，卡片四舍五入整数展示 `XX千卡/XXkJ`，一条能量占一个参数项。截图只写 `Calories` 或 `cal` 时先确认是不是营养千卡，不擅自按kcal处理或误除/乘1000。活动热量与总热量分别显示，不推算缺项。

他人记录仅在获得本人长期保存授权、独立身份和私有目录后入账；其他情况用 `--no-save`。他人的一次组别确认不授予长期保存健康历史权限。

卡面隐藏“（计算）”来源后缀，报告保留原标签及计算依据；距离单位仅在显示层将 m 写为米，配速显示 /100米。

1.2.4卡面格式：SWOLF仅显示数值；热量显示“330 千卡 / 1381 kJ”，数字与单位、斜杠两侧各留一个空格。

1.2.5泳姿：混合泳保留每段泳姿，默认不评级；仅本次明确要求时在封套设置 dolphin_mixed_reference: "freestyle"，才按成人自由泳男女阈值作娱乐参考，报告标明此依据。仰泳/蝶泳单项等级留待核实标准；未知泳姿保持未知。混合泳的全程划水/SWOLF汇总需每段泳姿、单臂计数口径、同池长、完整活动时段均明确，汇总不作单一泳姿效率评价；周期计数或未知口径保留设备原值。

1.2.8：feedback可新增post_session_breathing、post_session_rhythm，保留本人游后原话；由评分脚本读取。缺最快/组别仍交付固定模板卡，省略海豚评级，后续补充。

1.2.10：原始参数不得编造；有有效运动数据时，dimensions可记录当次合理推测或用户明确评价，内部保留来源。Effort仅展示为运动强度评级，不假称设备自动生成；固定模板完整雷达与牛马栏目保留。



## 1.2.11 逐图核验封套

宿主完整查看全部已提供图片后填写 `image_review`，每项如：
`{"image_id":"libfile_example", "reviewed":true, "regions":["汇总", "分段表", "图表"], "unreadable_regions":["第6趟用时遮挡"]}`。
image_id须覆盖source.library_file_ids且不重复，regions按每图真实区域填写。清单和原始metrics分别保存在报告；未传清单的旧输入兼容运行，但报告标legacy_unattested，不能声称已逐图核验。脚本核对清单覆盖和同口径跨图冲突，无法验证宿主实际看图。看不清的原指标保留uncertain/value=null及原字符；结构化segments只填有明确距离/用时的段，保留原趟号，不能补造被遮挡段。分段表的活动口径/不含休息/连续性须有截图或用户证据。跨图重复观测保留所有原metrics；仅显示去重。
全部有效完整百米统一比较，50米分段按原奇偶趟号固定配对；局部遮挡不使其他有效组失效。报告的verified_pairs、coverage、unverified_lap_indices及fastest_scope限定结论范围。

1.2.14：可选封套hundred_m_context按metric id或segment:N映射person_id/record_id/session_date/stroke/scope(current_session或history)。用于保存宿主识别的来源上下文，字段冲突排除对应证据；省略时仅接受已按record本次范围绑定的完整100米证据，不读取历史记录。原始记录schema不改变。直接历史最佳需保留正确历史scope/标签/日期，不冒写本次complete_100m。统一比较全部有效完整100米证据，不能因直接字段存在而跳过更快配对。未知休息保持未知，明确含休息排除该组。

## 发布候选证据规则
同一 segment_index 冲突观测保留全部并排除该原趟；后补截图分段合并，不覆盖已有观察。直接百米 time_basis=elapsed 或标签/来源明确含休息则排除并记原因。未知休息为 not_reported。dolphin_mixed_reference 仅接受 "freestyle" 或省略，每次单独明确，不从档案继承。


## 本机现场锐评修改（2026-11-08）

运行出卡前，宿主根据本次实际数据和本人游后体感现场创作必填`quip`，最多45字单行。缺失、格式错误或近期重复返回明确错误，先补写/重写再运行，不调用旧52句库或个性化模板。体感未提供先简短询问，用户明确跳过时只据数据写，不伪造体感。明确discomfort=true时现场关怀文案必须同时传`quip_tone: "care"`。详见[现场锐评](persona.md#每次现场创作)。`prepare()`仍可独立校验数据/评分；`execute()`才要求现场文案。合成样例内的quip仅为测试输入，不是业务候选池。
