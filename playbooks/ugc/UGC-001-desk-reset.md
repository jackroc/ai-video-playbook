# UGC-001 · 桌面整理的生活演示

- 生成验证：**待验证，未生成成片**
- 带货效果：未测
- 创建日期：2026-11-03
- 类型：UGC / 生活演示 / 痛点到解决
- 假设商品：槽式桌面理线器；必须按具体实物改写结构与用法
- 设计：约 24 秒，4 镜各约 6 秒，竖屏；时长按实际平台能力拆分
- 模型 / 参数 / 任务 ID / 实验 / 成片：尚未选择或产生

## 创意与适用边界

主角每次起身都把充电线带落桌边，使用理线器整理后，可以直接找到线头。商品用法在近景中呈现，口播只描述当下可见体验，不虚构长期使用评价。

适合能在单次动作里看懂用途的小型收纳件。如果实物不能固定线头、需要复杂安装，先重写演示动作。

## 准备素材

- `PRODUCT_REF`：实物同一变体的正面、侧面及实际使用图，补齐尺寸和可放置方式。
- `ACTOR_REF`：可使用的成人角色图，固定身份、发型、灰色上衣。
- `DESK_REF`：同一张木色桌面、两根线和笔记本的布局图。
- 以上是占位符，必须在生成界面或 API 中绑定真实素材。没有素材前不可直接提交。

## 分镜与完整提示词

共享条件：四镜为同一成人、同一桌面与光线。每次生成都附同一组素材；商品始终为实物变体。下面的中文创作说明已经转成英文画面提示词，不代表英文效果优于中文。

### 镜头 1：问题已经发生，约 6 秒

```text
Vertical smartphone-style video, medium close view of the desk in DESK_REF,
soft window light, slight natural handheld movement. Match the adult in
ACTOR_REF, with the same gray shirt and hairstyle. The adult reaches toward
one loose charging cable near the desk edge, misses the cable end, then looks
down as it slips below the edge. A brief restrained look of annoyance, no
exaggerated acting. One clear action, physically continuous motion. End with
the adult looking at the desk edge. No generated captions or extra products.
No dialogue; record quiet room tone if audio generation is available.
```

后期画外音：`“Why is this cable always down there?”`

### 镜头 2：商品进入动作，约 6 秒

```text
Vertical close-up, fixed camera, the same desk and soft window light as
DESK_REF. Show the exact cable organizer from PRODUCT_REF at its documented
real size. It is already installed according to the product's real instructions.
One adult right hand places one charging cable into one visible slot using
the real demonstrated mechanism, then releases it. The cable stays visibly
in the slot. Keep product color, shape and slot count consistent with the
reference. Do not morph the product or invent a locking mechanism. End with
the hand withdrawn and the product unobstructed. No captions or dialogue.
```

### 镜头 3：结果可见，约 6 秒

```text
Vertical desk-level close-up, same desk layout and lighting. The exact
PRODUCT_REF organizer holds the same cable in the position established in
the previous shot. The adult's right hand reaches into frame and takes the
cable end in one simple motion, demonstrating access according to the real
product behavior. Keep contact and cable movement physically continuous.
Hold the final result briefly. Fixed camera, natural room tone, no dialogue,
no captions, no new cables, no changes to the product.
```

后期画外音：`“Okay. Now I can actually find it.”`

### 镜头 4：生活收尾，约 6 秒

```text
Vertical medium view of the same adult and desk. Match ACTOR_REF and the gray
shirt. The cable organizer remains clearly visible at the actual scale shown
in PRODUCT_REF. The adult sits back, looks once at the organized cable, then
returns to the laptop with a small satisfied smile. One gentle handheld
camera drift, no dramatic commercial lighting. End on the settled desk.
No dialogue or generated text. Preserve product and desk continuity.
```

后期 CTA 可选：`“Check the size and cable fit before you pick one.”` 按真实销售渠道改写。

## 生成与后期计划

先测镜头 2 的手部接触，确认能用再生成其余镜头。四镜独立生成，后期剪为约 24 秒。配音与字幕后期添加；如改为同步口播，另建口型实验。需要精确商品字样时使用真实图合成，并在实验中记录。

## 待测试问题

手是否穿模？线是否真的留在槽内？前后桌面是否一致？商品是否足够清楚？能否在没有口播的情况下看懂用途？按 [验收规则](../../docs/evaluation.md) 实测后更新状态。
