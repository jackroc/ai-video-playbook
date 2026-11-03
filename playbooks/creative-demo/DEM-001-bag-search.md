# DEM-001 · 包内寻宝

- 生成验证：**待验证，未生成成片**
- 带货效果：未测
- 创建日期：2026-11-03
- 类型：创意商品演示 / 夸张表演 / 对照
- 假设商品：放入同一手提包的分格收纳袋，具有可见钥匙口袋
- 设计：约 24 秒，4 镜各约 6 秒，竖屏
- 模型 / 参数 / 任务 ID / 实验 / 成片：尚未选择或产生

## 一句话概念

找钥匙像执行探险任务 → 切到真实收纳袋布局 → 同一把钥匙有固定位置 → 主角一本正经宣布任务完成。

夸张来自主角戴着头灯的表演，商品功能镜头按实际空间、容量和口袋结构演示。对照只表现这个设定中的布局差异，不声称普遍节省多少时间。

## 素材准备

- `ACTOR_REF`：可用的成人角色图，米色外套。
- `BAG_REF`：同一个手提包，正面与俯视图，真实尺寸。
- `PRODUCT_REF`：收纳袋具体变体、尺寸、口袋布局和放入该包的实拍。
- `LAYOUT_REF`：收纳袋中同一把钥匙、钱包和纸巾的真实摆放；钥匙位于开口口袋。
- 输入素材尚未提供；先确认商品确实能放入包内，再执行示例。占位符需绑定真实素材。

## 分镜与提示词

### 镜头 1：把小事拍成任务，约 6 秒

```text
Vertical smartphone medium shot, the adult in ACTOR_REF wearing a beige
jacket and a small headlamp, standing beside the exact handbag in BAG_REF.
Everyday apartment hallway, soft indoor light. With comically intense focus,
the adult leans toward the open bag and peers inside as if beginning a major
expedition. One slow lean, then a still concentrated expression. Do not put
the person's head inside the bag. Realistic proportions, no text or dialogue.
```

后期配音：`“Mission: find my keys.”`

### 镜头 2：无用搜索的反应，约 6 秒

```text
Vertical close shot of the same adult beside the same open handbag.
Match the beige jacket, headlamp and hallway. The adult pauses with one
hand hovering above the bag opening, looks off-camera with exaggerated
seriousness, and exhales once. Keep the bag stationary and its shape fixed.
The humor is only the facial reaction, not changing bag dimensions or
infinite objects. Static camera. No captions or dialogue.
```

后期配音：`“We may need backup.”`

### 镜头 3：商品成为解法，约 6 秒

```text
Vertical top-down fixed close-up of the exact handbag in BAG_REF containing
the exact organizer from PRODUCT_REF, arranged as in LAYOUT_REF. Keep actual
bag and organizer dimensions, pocket count, color and material unchanged.
The same key set is plainly visible in its designated open pocket. An adult
right hand reaches in, grasps the key ring, and lifts it clear in one simple,
physically continuous movement. The organizer stays in place. No automatic
sorting or invented compartments. End with keys just above the bag opening.
No dialogue or generated text.
```

### 镜头 4：回扣任务，约 6 秒

```text
Vertical medium shot of the adult in ACTOR_REF in the same apartment hallway,
same beige jacket and headlamp. The open bag rests on the table with the
PRODUCT_REF organizer visible at its real scale. The adult holds the same
keys, gives one solemn thumbs-up with the free hand, then relaxes into a
small smile. Keep keys, bag and organizer consistent. Light handheld camera,
no generated captions or dialogue. End on a settled pose.
```

后期配音：`“Mission complete.”` CTA 可补：`“Check the measurements for your bag.”`

## 制作计划与待测点

先测试俯拍取钥匙动作。无法稳定保持口袋布局时，采用真实商品镜头作为功能演示，并记录混合制作步骤。检查钥匙是否穿模、包是否变大、商品是否可辨认、夸张表演是否拖慢卖点出现。所有假设需用实验验证。
